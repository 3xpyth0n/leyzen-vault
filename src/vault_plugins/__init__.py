"""Service plugin framework for Leyzen Vault."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence


class VaultServicePlugin(ABC):
    """Base class for orchestrator service stack plugins."""

    #: Unique identifier for the plugin. Used as configuration selector.
    name: str = ""

    #: Number of user-facing web replicas this plugin exposes by default.
    replicas: int = 1

    #: Minimum number of replicas this plugin supports.
    min_replicas: int = 1

    #: Optional service names that should be started before the base stack.
    dependencies: Sequence[str] = ()

    #: Default port exposed by the plugin's web-facing replicas.
    web_port: int = 80

    #: HTTP health-check path issued by HAProxy. Plugins can override this
    #: class attribute or mutate the resolved value during ``setup``.
    healthcheck_path: str = "/"

    #: Host header used for HAProxy health checks. Defaults to ``localhost``
    #: which works for the bundled plugins; override when the backend enforces
    #: a different host allowlist.
    healthcheck_host: str = "localhost"

    def __init__(self) -> None:
        if not self.name:
            raise ValueError("Plugins must define a non-empty 'name' attribute")
        self._active_replicas = self.min_replicas
        self._healthcheck_path = self._sanitize_healthcheck_path(self.healthcheck_path)
        self._healthcheck_host = self.healthcheck_host.strip() or "localhost"

    def setup(self, env: Mapping[str, str]) -> None:
        """Perform optional pre-initialization steps.

        Sub-classes may override this hook to bootstrap volumes or any
        additional resources prior to Compose generation. The default
        implementation resolves the replica count from ``VAULT_WEB_REPLICAS``.
        """

        self._active_replicas = self._resolve_replica_count(env)
        self._healthcheck_path = self._resolve_healthcheck_path(env)
        self._healthcheck_host = self._resolve_healthcheck_host(env)

    def _resolve_replica_count(self, env: Mapping[str, str]) -> int:
        override = env.get("VAULT_WEB_REPLICAS", "").strip()
        base = self.min_replicas
        if not override:
            return base

        try:
            requested = int(override)
        except ValueError:
            return base

        return max(self.min_replicas, requested)

    @property
    def active_replicas(self) -> int:
        return max(self.min_replicas, self._active_replicas)

    @property
    def backend_healthcheck_path(self) -> str:
        return self._healthcheck_path

    @property
    def backend_healthcheck_host(self) -> str:
        return self._healthcheck_host

    def get_containers(self) -> Sequence[str]:
        """Return the names of web-facing containers managed by the plugin."""

        return [f"{self.name}_web{i+1}" for i in range(self.active_replicas)]

    def _resolve_healthcheck_path(self, env: Mapping[str, str]) -> str:
        override = env.get("VAULT_WEB_HEALTHCHECK_PATH", "").strip()
        if override:
            candidate = override
        else:
            candidate = self.healthcheck_path
        return self._sanitize_healthcheck_path(candidate)

    def _resolve_healthcheck_host(self, env: Mapping[str, str]) -> str:
        override = env.get("VAULT_WEB_HEALTHCHECK_HOST", "").strip()
        if override:
            return override
        base = getattr(self, "healthcheck_host", "localhost")
        return base.strip() or "localhost"

    @staticmethod
    def _sanitize_healthcheck_path(value: str) -> str:
        candidate = (value or "/").strip()
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        return candidate

    @abstractmethod
    def build_compose(self, env: Mapping[str, str]) -> Mapping[str, object]:
        """Return docker-compose service fragments for this plugin."""


__all__ = ["VaultServicePlugin"]
