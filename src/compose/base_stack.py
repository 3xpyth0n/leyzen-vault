"""Base docker-compose stack for Leyzen Vault."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Mapping, Sequence

from common.constants import REPO_ROOT
from common.env import resolve_env_file_name

BASE_VOLUMES: OrderedDict[str, dict[str, object]] = OrderedDict(
    (("orchestrator-logs", {}),)
)

BASE_NETWORKS: OrderedDict[str, dict[str, object]] = OrderedDict(
    (
        ("vault-net", {"driver": "bridge"}),
        ("control-net", {"driver": "bridge"}),
    )
)


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

    cert_path_str = cert_path.strip()
    cert_file = Path(cert_path_str)
    if not cert_file.is_absolute():
        cert_file = (root_dir / cert_path_str).resolve()
    else:
        cert_file = cert_file.resolve()

    if not cert_file.exists():
        warnings.append(f"SSL certificate file not found: {cert_file}")
        return False, warnings

    if not cert_file.is_file():
        warnings.append(f"SSL certificate path is not a file: {cert_file}")
        return False, warnings

    # If key_path is provided, validate it too
    if key_path and key_path.strip():
        key_path_str = key_path.strip()
        key_file = Path(key_path_str)
        if not key_file.is_absolute():
            key_file = (root_dir / key_path_str).resolve()
        else:
            key_file = key_file.resolve()

        if not key_file.exists():
            warnings.append(f"SSL key file not found: {key_file}")
            return False, warnings

        if not key_file.is_file():
            warnings.append(f"SSL key path is not a file: {key_file}")
            return False, warnings

    return True, warnings


def build_base_services(
    env: Mapping[str, str],
    web_containers: Sequence[str],
    web_container_string: str,
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
        # Resolve certificate paths for validation and Docker Compose
        cert_path_input = ssl_cert_path.strip()
        cert_path_host = Path(cert_path_input)
        if not cert_path_host.is_absolute():
            cert_path_host = (REPO_ROOT / cert_path_host).resolve()
        else:
            cert_path_host = cert_path_host.resolve()

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

        # If key is provided separately, mount it too
        if ssl_key_path:
            key_path_input = ssl_key_path.strip()
            key_path_host = Path(key_path_input)
            if not key_path_host.is_absolute():
                key_path_host = (REPO_ROOT / key_path_host).resolve()
            else:
                key_path_host = key_path_host.resolve()

            # Convert to relative path from repo root for Docker Compose consistency
            try:
                key_path_rel = key_path_host.relative_to(REPO_ROOT)
                key_path_docker = f"./{key_path_rel}"
            except ValueError:
                # Path is outside repo root, use absolute path
                key_path_docker = str(key_path_host)

            key_path_container = "/usr/local/etc/haproxy/ssl/key.pem"
            haproxy_volumes.append(f"{key_path_docker}:{key_path_container}:ro")

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
        "stop_grace_period": "30s",
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
]
