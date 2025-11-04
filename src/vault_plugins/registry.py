"""Plugin discovery utilities for Leyzen Vault services."""

from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
from typing import Mapping, MutableMapping, Type

import vault_plugins
from common.constants import REPO_ROOT
from common.env import load_env_with_override
from . import VaultServicePlugin

_PLUGIN_CACHE: dict[str, Type[VaultServicePlugin]] | None = None


def discover_plugins() -> dict[str, Type[VaultServicePlugin]]:
    """Return a mapping of plugin name to plugin class."""

    global _PLUGIN_CACHE
    if _PLUGIN_CACHE is not None:
        return dict(_PLUGIN_CACHE)

    discovered: dict[str, Type[VaultServicePlugin]] = {}
    package_prefix = vault_plugins.__name__ + "."
    for module_info in pkgutil.walk_packages(vault_plugins.__path__, package_prefix):
        if not module_info.name.endswith(".plugin"):
            continue
        module = importlib.import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, VaultServicePlugin) or obj is VaultServicePlugin:
                continue
            if inspect.isabstract(obj):
                continue
            plugin_name = getattr(obj, "name", "").strip().lower()
            if not plugin_name:
                continue
            discovered[plugin_name] = obj

    _PLUGIN_CACHE = dict(discovered)
    return dict(discovered)


def get_active_plugin(env: Mapping[str, str] | None = None) -> VaultServicePlugin:
    """Instantiate and return the active plugin based on configuration."""

    # Use the shared REPO_ROOT constant from common.constants
    root_dir = REPO_ROOT

    env_mapping: MutableMapping[str, str] = {}
    env_mapping.update(load_env_with_override(root_dir))

    if env is None:
        env_mapping.update(os.environ)
    else:
        env_mapping.update(dict(env))

    plugins = discover_plugins()
    raw_name = env_mapping.get("VAULT_SERVICE", "filebrowser").strip().lower()
    if raw_name not in plugins:
        raise KeyError(
            f"Unknown VAULT_SERVICE '{raw_name}'. Available: {', '.join(sorted(plugins))}"
        )

    plugin_cls = plugins[raw_name]
    plugin = plugin_cls()
    plugin.setup(env_mapping)
    return plugin


__all__ = ["discover_plugins", "get_active_plugin"]
