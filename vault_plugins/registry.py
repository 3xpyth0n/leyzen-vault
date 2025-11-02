"""Plugin discovery utilities for Leyzen Vault services."""

from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Type

import vault_plugins
from leyzen_common.env import read_env_file
from . import VaultServicePlugin

_PLUGIN_CACHE: Dict[str, Type[VaultServicePlugin]] | None = None


def discover_plugins() -> Dict[str, Type[VaultServicePlugin]]:
    """Return a mapping of plugin name to plugin class."""

    global _PLUGIN_CACHE
    if _PLUGIN_CACHE is not None:
        return dict(_PLUGIN_CACHE)

    discovered: Dict[str, Type[VaultServicePlugin]] = {}
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

    env_mapping: MutableMapping[str, str] = {}
    env_path = Path(".env")
    env_mapping.update(read_env_file(env_path))

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
