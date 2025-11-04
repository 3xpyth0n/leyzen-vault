from __future__ import annotations

import hmac
import logging
import os
import re
import sys
from pathlib import Path
from typing import FrozenSet, Iterable, Pattern

from flask import Flask, Response, jsonify, request
import httpx
from werkzeug.exceptions import Forbidden, Unauthorized

# Bootstrap minimal to enable importing common.path_setup
# This must be done before importing common modules
# Standard pattern: Manually add src/ to sys.path, then use bootstrap_entry_point()
# Note: These calculations are necessary before we can import common.constants
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point

# Complete the bootstrap sequence (idempotent)
bootstrap_entry_point()

from common.constants import (
    DOCKER_PROXY_PORT_DEFAULT,
    DOCKER_SOCKET_PATH_DEFAULT,
)

# IMPORTANT: Always use parse_container_names from common.env
# DO NOT reimplement this function inline (see CHANGELOG.md v1.1.0)
# This ensures consistent parsing behavior across all services.
from common.env import parse_container_names


logging.basicConfig(
    level=getattr(
        logging, os.environ.get("DOCKER_PROXY_LOG_LEVEL", "INFO").upper(), logging.INFO
    ),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

EXPECTED_TOKEN: str | None = None
ALLOWED_CONTAINERS: FrozenSet[str] = frozenset()
CLIENT: httpx.Client | None = None

# Docker socket path for Unix domain socket communication
# This can be overridden via DOCKER_SOCKET_PATH environment variable
SOCKET_PATH = os.environ.get("DOCKER_SOCKET_PATH", DOCKER_SOCKET_PATH_DEFAULT)

# Base URL for Docker Engine API communication
# This is hardcoded to "http://docker" because the docker-proxy communicates
# with the Docker Engine via Unix domain socket (UDS), not HTTP. The "http://docker"
# hostname is used by httpx's UDS transport mechanism and doesn't represent
# an actual HTTP endpoint. This value should not be changed as it's required
# for the UDS transport to function correctly.
BASE_URL = "http://docker"

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

ALLOWED_ENDPOINTS: tuple[tuple[str, Pattern[str]], ...] = (
    ("GET", re.compile(r"^containers/(?P<name>[^/]+)/json$")),
    ("GET", re.compile(r"^containers/(?P<name>[^/]+)/stats$")),
    (
        "POST",
        re.compile(r"^containers/(?P<name>[^/]+)/(start|stop|wait|unpause)$"),
    ),
)


def _load_allowed_containers() -> FrozenSet[str]:
    """Load allowed container names from environment variable.

    Uses the shared parse_container_names utility and converts to FrozenSet
    for efficient membership testing.
    """
    raw = os.environ.get("VAULT_WEB_CONTAINERS")
    if not raw:
        logger.error(
            "VAULT_WEB_CONTAINERS must include at least one container identifier"
        )
        raise RuntimeError("VAULT_WEB_CONTAINERS must provide at least one container")

    names = parse_container_names(raw)
    if not names:
        logger.error("Parsed VAULT_WEB_CONTAINERS is empty after tokenization")
        raise RuntimeError("VAULT_WEB_CONTAINERS must provide at least one container")

    # Convert to FrozenSet for efficient membership testing
    allowed = frozenset(names)
    logger.info("Loaded %d allowed container identifiers", len(allowed))
    return allowed


def _ensure_configured() -> None:
    if EXPECTED_TOKEN is None or not ALLOWED_CONTAINERS or CLIENT is None:
        stored_error = app.config.get("CONFIGURATION_ERROR")
        if isinstance(stored_error, Exception):
            raise RuntimeError(str(stored_error)) from stored_error

        raise RuntimeError(
            "Docker proxy is not configured; ensure DOCKER_PROXY_TOKEN and "
            "VAULT_WEB_CONTAINERS are set."
        )


def _configure_runtime() -> None:
    global EXPECTED_TOKEN, ALLOWED_CONTAINERS, CLIENT

    token = os.environ.get("DOCKER_PROXY_TOKEN")
    if not token:
        raise RuntimeError("DOCKER_PROXY_TOKEN must be provided")

    allowed = _load_allowed_containers()

    timeout = float(os.environ.get("DOCKER_PROXY_TIMEOUT", "30"))
    transport = httpx.HTTPTransport(uds=SOCKET_PATH)
    client = httpx.Client(
        base_url=BASE_URL, transport=transport, timeout=httpx.Timeout(timeout)
    )

    EXPECTED_TOKEN = token
    ALLOWED_CONTAINERS = allowed
    CLIENT = client


class ProxyUnauthorized(Unauthorized):
    description = "Missing or invalid Authorization header"


class ProxyForbidden(Forbidden):
    description = "Invalid bearer token"


class ProxyRequestForbidden(Forbidden):
    description = "Operation not allowed via proxy"


@app.errorhandler(ProxyUnauthorized)
def handle_unauthorized(error: ProxyUnauthorized):
    logger.warning(
        "Denied request without valid Authorization header from %s", request.remote_addr
    )
    return jsonify({"error": error.description}), 401


@app.errorhandler(ProxyForbidden)
def handle_forbidden(error: ProxyForbidden):
    logger.warning("Denied request with incorrect token from %s", request.remote_addr)
    return jsonify({"error": error.description}), 403


@app.errorhandler(ProxyRequestForbidden)
def handle_request_forbidden(error: ProxyRequestForbidden):
    logger.warning(
        "Denied disallowed Docker API request %s %s from %s",
        request.method,
        request.full_path,
        request.remote_addr,
    )
    return jsonify({"error": error.description}), 403


def _validate_token() -> None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ProxyUnauthorized()

    provided_token = auth_header[len("Bearer ") :].strip()
    assert EXPECTED_TOKEN is not None
    if not provided_token or not hmac.compare_digest(provided_token, EXPECTED_TOKEN):
        raise ProxyForbidden()


def _filtered_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lower_key = key.lower()
        if (
            lower_key in HOP_BY_HOP_HEADERS
            or lower_key == "authorization"
            or lower_key == "host"
        ):
            continue
        headers[key] = value
    return headers


def _stream_response(upstream_response: httpx.Response) -> Iterable[bytes]:
    try:
        for chunk in upstream_response.iter_bytes():
            if chunk:
                yield chunk
    finally:
        upstream_response.close()


@app.route("/healthz", methods=["GET"])
def healthcheck() -> tuple[str, int]:
    try:
        _ensure_configured()
    except RuntimeError as error:
        return str(error), 503

    return "ok", 200


@app.route(
    "/",
    defaults={"path": ""},
    methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "HEAD",
    ],
)
@app.route(
    "/<path:path>",
    methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "HEAD",
    ],
)
def proxy(path: str) -> Response:
    try:
        _ensure_configured()
    except RuntimeError as error:
        return (
            jsonify({"error": str(error)}),
            503,
        )

    _validate_token()
    normalized_path = request.path.lstrip("/")

    container_name: str | None = None
    for allowed_method, pattern in ALLOWED_ENDPOINTS:
        if request.method != allowed_method:
            continue

        match = pattern.fullmatch(normalized_path)
        if match:
            container_name = match.groupdict().get("name")
            break
    else:
        raise ProxyRequestForbidden()

    if container_name and container_name not in ALLOWED_CONTAINERS:
        logger.warning(
            "Denied request for container %s outside allowed list from %s",
            container_name,
            request.remote_addr,
        )
        raise ProxyRequestForbidden()

    upstream_path = request.path or "/"
    upstream_url = f"{BASE_URL}{upstream_path}"
    logger.debug(
        "Forwarding %s request for %s to docker socket", request.method, upstream_url
    )

    headers = _filtered_headers()
    body = request.get_data()
    content = body if body else b""
    headers.setdefault("Content-Length", str(len(content)))

    params = list(request.args.items(multi=True))

    proxy_client = CLIENT
    assert proxy_client is not None

    try:
        prepared_request = proxy_client.build_request(
            method=request.method,
            url=upstream_path,
            headers=headers,
            params=params,
            content=content,
        )
        upstream_response = proxy_client.send(prepared_request, stream=True)
    except httpx.RequestError as exc:
        logger.error("Failed to reach docker socket: %s", exc)
        return jsonify({"error": "Docker socket unreachable"}), 502

    excluded_headers = {"content-length"}
    headers = [
        (key, value)
        for key, value in upstream_response.headers.items()
        if key.lower() not in excluded_headers
    ]

    if request.method == "HEAD":
        response = Response(status=upstream_response.status_code, headers=headers)
        upstream_response.close()
        return response

    return Response(
        _stream_response(upstream_response),
        status=upstream_response.status_code,
        headers=headers,
    )


try:
    _configure_runtime()
except RuntimeError as exc:
    logger.error("Docker proxy configuration error: %s", exc)
    app.config["CONFIGURATION_ERROR"] = exc
else:
    app.config["CONFIGURATION_ERROR"] = None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DOCKER_PROXY_PORT_DEFAULT)
