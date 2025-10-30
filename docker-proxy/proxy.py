import logging
import os
import sys
import hmac
import re
from typing import Dict, FrozenSet, Iterable, Optional, Pattern, Tuple

from flask import Flask, Response, jsonify, request
import httpx
from werkzeug.exceptions import Forbidden, Unauthorized

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

EXPECTED_TOKEN = os.environ.get("DOCKER_PROXY_TOKEN")
if not EXPECTED_TOKEN:
    logger.error("DOCKER_PROXY_TOKEN must be provided")
    raise RuntimeError("DOCKER_PROXY_TOKEN must be provided")

SOCKET_PATH = os.environ.get("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
BASE_URL = "http://docker"

TIMEOUT = float(os.environ.get("DOCKER_PROXY_TIMEOUT", "30"))

transport = httpx.HTTPTransport(uds=SOCKET_PATH)
client = httpx.Client(
    base_url=BASE_URL, transport=transport, timeout=httpx.Timeout(TIMEOUT)
)

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

ALLOWED_ENDPOINTS: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("GET", re.compile(r"^containers/(?P<name>[^/]+)/json$")),
    ("GET", re.compile(r"^containers/(?P<name>[^/]+)/stats$")),
    (
        "POST",
        re.compile(r"^containers/(?P<name>[^/]+)/(start|stop|wait|unpause)$"),
    ),
)


def _parse_container_tokens(raw: str) -> FrozenSet[str]:
    tokens = set()
    for part in re.split(r"[,\s]+", raw):
        name = part.strip()
        if name:
            tokens.add(name)
    return frozenset(tokens)


def _load_allowed_containers() -> FrozenSet[str]:
    raw = os.environ.get("VAULT_WEB_CONTAINERS")
    if not raw:
        logger.error(
            "VAULT_WEB_CONTAINERS must include at least one container identifier"
        )
        raise RuntimeError("VAULT_WEB_CONTAINERS must provide at least one container")

    allowed = _parse_container_tokens(raw)
    if not allowed:
        logger.error("Parsed VAULT_WEB_CONTAINERS is empty after tokenization")
        raise RuntimeError("VAULT_WEB_CONTAINERS must provide at least one container")

    logger.info("Loaded %d allowed container identifiers", len(allowed))
    return allowed


ALLOWED_CONTAINERS: FrozenSet[str] = _load_allowed_containers()


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
    if not provided_token or not hmac.compare_digest(provided_token, EXPECTED_TOKEN):
        raise ProxyForbidden()


def _filtered_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
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
def healthcheck() -> Tuple[str, int]:
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
    logger.debug("TRACE 1: entering proxy()")
    _validate_token()
    logger.debug("TRACE 2: token validated")
    normalized_path = request.path.lstrip("/")
    logger.debug(
        f"TRACE 3: normalized_path = {normalized_path!r}, method = {request.method}"
    )

    container_name: Optional[str] = None
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

    try:
        prepared_request = client.build_request(
            method=request.method,
            url=upstream_path,
            headers=headers,
            params=params,
            content=content,
        )
        upstream_response = client.send(prepared_request, stream=True)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2375)
