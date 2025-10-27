import logging
import os
import sys
import hmac
from typing import Dict, Iterable, Tuple

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


class ProxyUnauthorized(Unauthorized):
    description = "Missing or invalid Authorization header"


class ProxyForbidden(Forbidden):
    description = "Invalid bearer token"


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
    _validate_token()

    upstream_path = f"/{path}" if path else "/"
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
