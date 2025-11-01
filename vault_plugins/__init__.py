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

    def __init__(self) -> None:
        if not self.name:
            raise ValueError("Plugins must define a non-empty 'name' attribute")
        self._active_replicas = max(self.min_replicas, self.replicas)

    def setup(self, env: Mapping[str, str]) -> None:
        """Perform optional pre-initialization steps.

        Sub-classes may override this hook to bootstrap volumes or any
        additional resources prior to Compose generation. The default
        implementation resolves the replica count from ``VAULT_WEB_REPLICAS``.
        """

        self._active_replicas = self._resolve_replica_count(env)

    def _resolve_replica_count(self, env: Mapping[str, str]) -> int:
        override = env.get("VAULT_WEB_REPLICAS", "").strip()
        base = max(self.min_replicas, self.replicas)
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

    def get_containers(self) -> Sequence[str]:
        """Return the names of web-facing containers managed by the plugin."""

        return [f"{self.name}_web{i+1}" for i in range(self.active_replicas)]

    @abstractmethod
    def build_compose(self, env: Mapping[str, str]) -> Mapping[str, object]:
        """Return docker-compose service fragments for this plugin."""


__all__ = ["VaultServicePlugin"]
