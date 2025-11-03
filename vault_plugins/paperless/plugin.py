"""Paperless plugin for Leyzen Vault."""

from __future__ import annotations

from collections import OrderedDict
from urllib.parse import urlparse
from typing import Mapping

from .. import VaultServicePlugin


class PaperlessPlugin(VaultServicePlugin):
    """Deploy the Paperless-ngx document management stack."""

    name = "paperless"
    replicas = 2
    min_replicas = 2
    dependencies: tuple[str, ...] = ("paperless_postgres", "paperless_redis")
    web_port = 8000

    def setup(self, env: Mapping[str, str]) -> None:
        super().setup(env)
        raw_url = env.get("PAPERLESS_URL", "").strip()
        if raw_url:
            parsed = urlparse(raw_url)
            if parsed.hostname:
                self._healthcheck_host = parsed.hostname

    def build_compose(self, env: Mapping[str, str]) -> Mapping[str, object]:
        self.setup(env)
        postgres_service = {
            "image": env.get("PAPERLESS_POSTGRES_IMAGE", "postgres:15-alpine"),
            "container_name": "paperless_postgres",
            "restart": "unless-stopped",
            "environment": {
                "POSTGRES_DB": env.get("PAPERLESS_DBNAME", "paperless"),
                "POSTGRES_USER": env.get("PAPERLESS_DBUSER", "paperless"),
                # Always use environment variable references to avoid hardcoding secrets
                "POSTGRES_PASSWORD": "${PAPERLESS_DBPASS:?Set PAPERLESS_DBPASS in .env}",
            },
            "volumes": ["paperless-postgres:/var/lib/postgresql/data"],
            "healthcheck": {
                "test": [
                    "CMD-SHELL",
                    "pg_isready -U ${PAPERLESS_DBUSER:-paperless} -d ${PAPERLESS_DBNAME:-paperless}",
                ],
                "interval": "5s",
                "timeout": "5s",
                "retries": 10,
            },
            "networks": ["vault-net"],
        }

        redis_service = {
            "image": env.get("PAPERLESS_REDIS_IMAGE", "redis:7-alpine"),
            "container_name": "paperless_redis",
            "restart": "unless-stopped",
            "command": ["redis-server", "--appendonly", "yes"],
            "volumes": ["paperless-redis:/data"],
            "healthcheck": {
                "test": ["CMD", "redis-cli", "ping"],
                "interval": "5s",
                "timeout": "5s",
                "retries": 10,
            },
            "networks": ["vault-net"],
        }

        paperless_env = {
            "PAPERLESS_REDIS": env.get(
                "PAPERLESS_REDIS",
                "redis://paperless_redis:6379/0",
            ),
            "PAPERLESS_DBHOST": env.get("PAPERLESS_DBHOST", "paperless_postgres"),
            "PAPERLESS_DBNAME": env.get("PAPERLESS_DBNAME", "paperless"),
            "PAPERLESS_DBUSER": env.get("PAPERLESS_DBUSER", "paperless"),
            # Always use environment variable references to avoid hardcoding secrets
            "PAPERLESS_DBPASS": "${PAPERLESS_DBPASS:?Set PAPERLESS_DBPASS in .env}",
            "PAPERLESS_SECRET_KEY": "${PAPERLESS_SECRET_KEY:?Set PAPERLESS_SECRET_KEY in .env}",
            "PAPERLESS_TIME_ZONE": env.get("TIMEZONE", "UTC"),
            "PAPERLESS_URL": env.get("PAPERLESS_URL", "http://localhost:8080"),
        }

        base_web_service = {
            "image": env.get(
                "PAPERLESS_IMAGE", "ghcr.io/paperless-ngx/paperless-ngx:latest"
            ),
            "restart": "unless-stopped",
            "env_file": [".env"],
            "environment": paperless_env,
            "depends_on": {
                "paperless_postgres": {"condition": "service_healthy"},
                "paperless_redis": {"condition": "service_started"},
            },
            "healthcheck": {
                "test": ["CMD-SHELL", "curl -f http://localhost:8000/ || exit 1"],
                "interval": "1s",
                "timeout": "5s",
                "retries": 10,
            },
            "volumes": [
                "paperless-data:/usr/src/paperless/data",
                "paperless-media:/usr/src/paperless/media",
                "paperless-export:/usr/src/paperless/export",
            ],
            "networks": ["vault-net"],
        }

        services = OrderedDict(
            (
                ("paperless_postgres", postgres_service),
                ("paperless_redis", redis_service),
            )
        )

        for name in self.get_containers():
            service_def = base_web_service.copy()
            service_def["container_name"] = name
            services[name] = service_def

        volumes = OrderedDict(
            (
                ("paperless-postgres", {}),
                ("paperless-redis", {}),
                ("paperless-data", {}),
                ("paperless-media", {}),
                ("paperless-export", {}),
            )
        )

        return {
            "services": services,
            "volumes": volumes,
        }


__all__ = ["PaperlessPlugin"]
