"""Base docker-compose stack shared by all plugins."""

from __future__ import annotations

from collections import OrderedDict
from typing import Mapping, Sequence

BASE_VOLUMES = OrderedDict((("orchestrator-logs", {}),))

BASE_NETWORKS = OrderedDict(
    (
        ("vault-net", {"driver": "bridge"}),
        ("control-net", {"driver": "bridge"}),
    )
)


def build_base_services(
    env: Mapping[str, str],
    web_containers: Sequence[str],
    web_container_string: str,
) -> OrderedDict[str, dict]:
    """Return the base services for the Leyzen stack."""

    orchestrator_depends = OrderedDict(
        (container, {"condition": "service_started"}) for container in web_containers
    )
    orchestrator_depends["docker-proxy"] = {"condition": "service_healthy"}

    haproxy = {
        "image": "haproxy:2.8-alpine",
        "container_name": "haproxy",
        "volumes": [
            "./infra/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro",
            "./infra/haproxy/404.http:/usr/local/etc/haproxy/404.http:ro",
            "./infra/haproxy/503.http:/usr/local/etc/haproxy/503.http:ro",
        ],
        "ports": ["8080:80"],
        "restart": "on-failure",
        "healthcheck": {
            "test": [
                "CMD-SHELL",
                "haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg || exit 1",
            ],
            "interval": "1s",
            "timeout": "5s",
            "retries": 5,
        },
        "networks": ["vault-net"],
    }

    docker_proxy = {
        "build": {"context": "./infra/docker-proxy"},
        "container_name": "docker-proxy",
        "restart": "unless-stopped",
        "env_file": [".env"],
        "environment": {
            # Always use environment variable references to avoid hardcoding secrets
            "DOCKER_PROXY_TOKEN": "${DOCKER_PROXY_TOKEN:?Set DOCKER_PROXY_TOKEN in .env}",
            "DOCKER_PROXY_TIMEOUT": "${DOCKER_PROXY_TIMEOUT:-30}",
            "DOCKER_PROXY_LOG_LEVEL": "${DOCKER_PROXY_LOG_LEVEL:-INFO}",
            "VAULT_WEB_CONTAINERS": web_container_string,
        },
        "healthcheck": {
            "test": ["CMD-SHELL", "curl -f http://localhost:2375/healthz || exit 1"],
            "interval": "1s",
            "timeout": "10s",
            "retries": 10,
        },
        "volumes": ["/var/run/docker.sock:/var/run/docker.sock:ro"],
        "networks": ["control-net"],
    }

    pythonpath_entries = ["/app", "/vault_plugins", "/common"]
    extra_pythonpath = env.get("PYTHONPATH", "").strip()
    if extra_pythonpath:
        for entry in extra_pythonpath.split(":"):
            token = entry.strip()
            if token:
                pythonpath_entries.append(token)

    # Preserve order while removing duplicates so the orchestrator always has
    # access to its source tree, the external plugin directory, and shared
    # helper modules.
    deduped_pythonpath: list[str] = []
    seen_pythonpath: set[str] = set()
    for entry in pythonpath_entries:
        if entry and entry not in seen_pythonpath:
            deduped_pythonpath.append(entry)
            seen_pythonpath.add(entry)
    pythonpath = ":".join(deduped_pythonpath)

    orchestrator = {
        "build": {"context": "./src/orchestrator"},
        "container_name": "orchestrator",
        "restart": "on-failure",
        "healthcheck": {
            "test": ["CMD-SHELL", "curl -f http://localhost/orchestrator || exit 1"],
            "interval": "1s",
            "timeout": "5s",
            "retries": 10,
        },
        "env_file": [".env"],
        "environment": {
            "VAULT_ORCHESTRATOR_LOG_DIR": "/app/logs",
            "VAULT_WEB_CONTAINERS": web_container_string,
            "PYTHONPATH": pythonpath,
        },
        "volumes": [
            "./src/orchestrator:/app:ro",
            "./src/vault_plugins:/vault_plugins:ro",
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


__all__ = ["BASE_VOLUMES", "BASE_NETWORKS", "build_base_services"]
