"""Filebrowser plugin for Leyzen Vault."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Mapping

from .. import VaultServicePlugin


class FilebrowserPlugin(VaultServicePlugin):
    """Provision Filebrowser replicas for the demo stack."""

    name = "filebrowser"
    replicas = 3
    min_replicas = 2
    dependencies: tuple[str, ...] = ()

    def build_compose(self, env: Mapping[str, str]) -> Mapping[str, object]:
        self.setup(env)
        base_service = {
            "build": {
                "context": "./filebrowser",
                "args": {
                    "FILEBROWSER_VERSION": env.get(
                        "FILEBROWSER_VERSION", "${FILEBROWSER_VERSION:-2.44.2}"
                    ),
                },
            },
            "image": "leyzen/filebrowser:latest",
            "env_file": [".env"],
            "environment": {
                # Always use environment variable references to avoid hardcoding secrets
                "FILEBROWSER_ADMIN_USER": "${FILEBROWSER_ADMIN_USER:?Set FILEBROWSER_ADMIN_USER in .env}",
                "FILEBROWSER_ADMIN_PASSWORD": "${FILEBROWSER_ADMIN_PASSWORD:?Set FILEBROWSER_ADMIN_PASSWORD in .env}",
            },
            "restart": "on-failure",
            "healthcheck": {
                "test": ["CMD-SHELL", "curl -f http://localhost || exit 1"],
                "interval": "1s",
                "timeout": "5s",
                "retries": 10,
            },
            "volumes": [
                "filebrowser-data:/srv",
                "filebrowser-database:/database",
                "filebrowser-config:/config",
            ],
            "depends_on": {
                "haproxy": {"condition": "service_healthy"},
                "docker-proxy": {"condition": "service_healthy"},
            },
            "networks": ["vault-net"],
        }

        services: OrderedDict[str, object] = OrderedDict()
        for container in self.get_containers():
            service_def = deepcopy(base_service)
            service_def["container_name"] = container
            services[container] = service_def

        volumes = OrderedDict(
            (
                ("filebrowser-data", {}),
                ("filebrowser-database", {}),
                ("filebrowser-config", {}),
            )
        )

        return {
            "services": services,
            "volumes": volumes,
        }


__all__ = ["FilebrowserPlugin"]
