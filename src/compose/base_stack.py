"""Base docker-compose stack for Leyzen Vault."""

from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path
from typing import Mapping, Sequence

from common.constants import REPO_ROOT
from common.env import resolve_env_file_name

BASE_VOLUMES: OrderedDict[str, dict[str, object]] = OrderedDict(
    (("orchestrator-logs", {"name": "leyzen-orchestrator-logs"}),)
)

BASE_NETWORKS: OrderedDict[str, dict[str, object]] = OrderedDict(
    (
        ("vault-net", {"driver": "bridge", "name": "leyzen-vault-net"}),
        ("control-net", {"driver": "bridge", "name": "leyzen-control-net"}),
    )
)

_PEM_CERT_HEADERS = ("-----BEGIN CERTIFICATE-----",)
_PEM_KEY_HEADERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
)
_DEFAULT_PEM_BUNDLE_PATH = REPO_ROOT / "infra" / "haproxy" / "haproxy.pem"


def _resolve_path(path_str: str, root_dir: Path) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        return (root_dir / path).resolve()
    return path.resolve()


def _read_pem_text(path: Path, description: str, warnings: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except OSError as exc:
            warnings.append(f"{description} is not readable ({exc})")
    except OSError as exc:
        warnings.append(f"{description} is not readable ({exc})")
    return None


def _contains_block(text: str, headers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in headers)


def _parse_port(
    env: Mapping[str, str],
    key: str,
    default: int,
    min_value: int = 1,
    max_value: int = 65535,
) -> int:
    """Parse a port number from environment variable with validation.

    Args:
        env: Dictionary containing environment variables.
        key: Environment variable name.
        default: Default value if variable is missing or invalid.
        min_value: Minimum allowed port value (default: 1).
        max_value: Maximum allowed port value (default: 65535).

    Returns:
        Parsed port number, clamped to valid range, or default if parsing fails.
    """
    raw_value = env.get(key, "").strip()
    if not raw_value:
        return default
    try:
        port = int(raw_value)
        port = max(min_value, min(max_value, port))
        return port
    except ValueError:
        return default


def validate_ssl_certificates(
    enable_https: bool,
    cert_path: str | None,
    key_path: str | None,
    root_dir: Path = REPO_ROOT,
) -> tuple[bool, list[str]]:
    """Validate SSL certificate files exist if HTTPS is enabled.

    Args:
        enable_https: Whether HTTPS is enabled.
        cert_path: Path to SSL certificate file (can be absolute or relative to root_dir).
        key_path: Path to SSL key file (optional, can be absolute or relative to root_dir).
        root_dir: Root directory for resolving relative paths.

    Returns:
        Tuple of (is_valid, list_of_warnings). is_valid is True if validation passes,
        False if HTTPS is enabled but certificates are missing or invalid.
        warnings contains human-readable warning messages.
    """
    if not enable_https:
        return True, []

    warnings: list[str] = []

    if not cert_path or not cert_path.strip():
        warnings.append("ENABLE_HTTPS=true but SSL_CERT_PATH is not set")
        return False, warnings

    cert_file = _resolve_path(cert_path.strip(), root_dir)

    if not cert_file.exists():
        warnings.append(f"SSL certificate file not found: {cert_file}")
        return False, warnings

    if not cert_file.is_file():
        warnings.append(f"SSL certificate path is not a file: {cert_file}")
        return False, warnings

    cert_text = _read_pem_text(cert_file, "SSL certificate file", warnings)
    if cert_text is None:
        return False, warnings

    is_valid = True
    if not _contains_block(cert_text, _PEM_CERT_HEADERS):
        warnings.append(
            f"SSL certificate file does not contain a PEM certificate block: {cert_file}"
        )
        is_valid = False

    # If key_path is provided, validate it too
    if key_path and key_path.strip():
        key_file = _resolve_path(key_path.strip(), root_dir)

        if not key_file.exists():
            warnings.append(f"SSL key file not found: {key_file}")
            return False, warnings

        if not key_file.is_file():
            warnings.append(f"SSL key path is not a file: {key_file}")
            return False, warnings

        key_text = _read_pem_text(key_file, "SSL key file", warnings)
        if key_text is None:
            return False, warnings

        if not _contains_block(key_text, _PEM_KEY_HEADERS):
            warnings.append(
                f"SSL key file does not contain a PEM private key block: {key_file}"
            )
            is_valid = False
    else:
        if not _contains_block(cert_text, _PEM_KEY_HEADERS):
            warnings.append(
                "SSL certificate file must contain the private key when SSL_KEY_PATH is not provided"
            )
            is_valid = False

    return is_valid, warnings


def prepare_ssl_certificate_bundle(
    enable_https: bool,
    cert_path: str | None,
    key_path: str | None,
    *,
    root_dir: Path = REPO_ROOT,
    output_path: Path | None = None,
) -> tuple[Path | None, list[str]]:
    """Ensure HAProxy has access to a PEM file that includes the cert and key."""

    if not enable_https or not cert_path:
        return None, []

    warnings: list[str] = []
    cert_file = _resolve_path(cert_path.strip(), root_dir)
    pem_target = output_path or _DEFAULT_PEM_BUNDLE_PATH

    def _write_pem(target: Path, content: str) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content if content.endswith("\n") else f"{content}\n")
        except OSError as exc:
            warnings.append(f"Could not write PEM bundle to {target} ({exc})")
            return False
        try:
            os.chmod(target, 0o644)
        except OSError as exc:
            warnings.append(f"Could not update permissions for {target} ({exc})")
        return True

    if key_path and key_path.strip():
        key_file = _resolve_path(key_path.strip(), root_dir)
        cert_text = _read_pem_text(cert_file, "SSL certificate file", warnings)
        key_text = _read_pem_text(key_file, "SSL key file", warnings)
        if cert_text is None or key_text is None:
            return None, warnings
        combined = cert_text.rstrip() + "\n" + key_text.strip() + "\n"
        if not _write_pem(pem_target, combined):
            return None, warnings
        return pem_target, warnings

    cert_text = _read_pem_text(cert_file, "SSL certificate file", warnings)
    if cert_text is None:
        return None, warnings

    if not _contains_block(cert_text, _PEM_KEY_HEADERS):
        warnings.append(
            "SSL certificate file must contain the private key when SSL_KEY_PATH is not provided"
        )
        return None, warnings

    if cert_file != pem_target:
        if not _write_pem(pem_target, cert_text):
            return None, warnings
        return pem_target, warnings

    return cert_file, warnings


def build_base_services(
    env: Mapping[str, str],
    web_containers: Sequence[str],
    web_container_string: str,
    *,
    ssl_cert_bundle_path: Path | None = None,
) -> OrderedDict[str, dict]:
    """Return the base services for the Leyzen stack.

    Service Dependencies:
    - HAProxy: No dependencies (front-end service, starts first)
    - Docker Proxy: No dependencies (must be healthy before orchestrator starts)
    - Orchestrator: Depends on:
      - All vault web containers (service_started condition)
      - Docker proxy (service_healthy condition)
      - The orchestrator coordinates container rotation and needs access to both
        the vault containers and the docker-proxy to manage container lifecycle

    Service Startup Order:
    1. HAProxy (starts first, no dependencies)
    2. Docker Proxy (starts early, must be healthy for orchestrator)
    3. Vault web containers (start after HAProxy and PostgreSQL are ready)
    4. Orchestrator (starts last, depends on vault containers and docker-proxy)
    """

    # Resolve the environment file name to use in docker-generated.yml
    env_file_name = resolve_env_file_name(REPO_ROOT)

    # Orchestrator dependencies:
    # - All vault web containers must be started (service_started condition)
    # - Docker proxy must be healthy (service_healthy condition) to enable
    #   container lifecycle operations (start/stop/restart)
    orchestrator_depends = OrderedDict(
        (container, {"condition": "service_started"}) for container in web_containers
    )
    orchestrator_depends["docker-proxy"] = {"condition": "service_healthy"}

    # Read HTTPS configuration from environment
    enable_https_raw = env.get("ENABLE_HTTPS", "").strip().lower()
    enable_https = enable_https_raw in ("true", "1", "yes", "on")
    ssl_cert_path = env.get("SSL_CERT_PATH", "").strip() or None
    ssl_key_path = env.get("SSL_KEY_PATH", "").strip() or None

    # Build HAProxy volumes (always include base config files)
    haproxy_volumes = [
        "./infra/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro",
        "./infra/haproxy/404.http:/usr/local/etc/haproxy/404.http:ro",
        "./infra/haproxy/503.http:/usr/local/etc/haproxy/503.http:ro",
    ]

    # Parse HTTP and HTTPS port configuration from environment
    http_port = _parse_port(env, "HTTP_PORT", default=8080)
    https_port = _parse_port(env, "HTTPS_PORT", default=8443)

    # Build HAProxy ports (always include HTTP port)
    haproxy_ports = [f"{http_port}:80"]

    # Add SSL certificate volumes and HTTPS port if HTTPS is enabled
    if enable_https and ssl_cert_path:
        bundle_host_path = ssl_cert_bundle_path
        if bundle_host_path is None:
            bundle_host_path, _ = prepare_ssl_certificate_bundle(
                enable_https, ssl_cert_path, ssl_key_path, root_dir=REPO_ROOT
            )

        cert_path_host = bundle_host_path or _resolve_path(ssl_cert_path, REPO_ROOT)

        # Convert to relative path from repo root for Docker Compose consistency
        # If path is outside repo root, use absolute path
        try:
            cert_path_rel = cert_path_host.relative_to(REPO_ROOT)
            cert_path_docker = f"./{cert_path_rel}"
        except ValueError:
            # Path is outside repo root, use absolute path
            cert_path_docker = str(cert_path_host)

        # Mount certificate in container (use a standard location)
        cert_path_container = "/usr/local/etc/haproxy/ssl/cert.pem"
        haproxy_volumes.append(f"{cert_path_docker}:{cert_path_container}:ro")

        # Add HTTPS port (use configured port or default 8443:443)
        haproxy_ports.append(f"{https_port}:443")

    haproxy = {
        "image": "haproxy:2.8-alpine",
        "container_name": "haproxy",
        "volumes": haproxy_volumes,
        "ports": haproxy_ports,
        "restart": "on-failure",
        "healthcheck": {
            "test": [
                "CMD-SHELL",
                "haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg || exit 1",
            ],
            "interval": "2s",
            "timeout": "5s",
            "retries": 10,
            "start_period": "30s",
        },
        "networks": ["vault-net"],
    }

    pythonpath_entries = ["/app", "/common"]
    extra_pythonpath = env.get("PYTHONPATH", "").strip()
    if extra_pythonpath:
        for entry in extra_pythonpath.split(":"):
            token = entry.strip()
            if token:
                pythonpath_entries.append(token)

    # Preserve order while removing duplicates so the orchestrator always has
    # access to its source tree and shared helper modules.
    deduped_pythonpath: list[str] = []
    seen_pythonpath: set[str] = set()
    for entry in pythonpath_entries:
        if entry and entry not in seen_pythonpath:
            deduped_pythonpath.append(entry)
            seen_pythonpath.add(entry)
    pythonpath = ":".join(deduped_pythonpath)

    docker_proxy = {
        "build": {"context": "./infra/docker-proxy"},
        "container_name": "docker-proxy",
        "restart": "unless-stopped",
        "env_file": [env_file_name],
        "environment": {
            # DOCKER_PROXY_TOKEN is auto-generated from SECRET_KEY if not set
            # Optional override: "DOCKER_PROXY_TOKEN": "${DOCKER_PROXY_TOKEN:-}",
            "DOCKER_PROXY_TIMEOUT": "${DOCKER_PROXY_TIMEOUT:-30}",
            "DOCKER_PROXY_LOG_LEVEL": "${DOCKER_PROXY_LOG_LEVEL:-INFO}",
            "ORCH_WEB_CONTAINERS": web_container_string,
            "PYTHONPATH": pythonpath,
        },
        "healthcheck": {
            "test": ["CMD-SHELL", "curl -f http://localhost:2375/healthz || exit 1"],
            "interval": "2s",
            "timeout": "10s",
            "retries": 10,
            "start_period": "30s",
        },
        "volumes": [
            "/var/run/docker.sock:/var/run/docker.sock:ro",
            "./src/common:/common:ro",
        ],
        "networks": ["control-net"],
    }

    orchestrator = {
        "build": {"context": "./src/orchestrator"},
        "container_name": "orchestrator",
        "image": "leyzen/orchestrator:latest",
        "restart": "on-failure",
        "stop_grace_period": "10s",
        "healthcheck": {
            "test": ["CMD-SHELL", "curl -f http://localhost/orchestrator || exit 1"],
            "interval": "2s",
            "timeout": "5s",
            "retries": 10,
            "start_period": "30s",
        },
        "env_file": [env_file_name],
        "environment": {
            "ORCH_LOG_DIR": "/app/logs",
            "ORCH_WEB_CONTAINERS": web_container_string,
            "PYTHONPATH": pythonpath,
        },
        "volumes": [
            "./src/orchestrator:/app:ro",
            "./src/common:/common:ro",
            "orchestrator-logs:/app/logs",
            "vault-data-source:/data-source:rw",  # Read-write for secure file promotion
        ],
        "depends_on": orchestrator_depends,
        "networks": ["vault-net", "control-net"],
    }

    return OrderedDict(
        (
            ("haproxy", haproxy),
            ("docker-proxy", docker_proxy),
            ("orchestrator", orchestrator),
        )
    )


__all__ = [
    "BASE_VOLUMES",
    "BASE_NETWORKS",
    "build_base_services",
    "validate_ssl_certificates",
    "prepare_ssl_certificate_bundle",
]
