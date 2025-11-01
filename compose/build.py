"""Compose manifest builder for Leyzen Vault."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Mapping

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from compose.base_stack import BASE_NETWORKS, BASE_VOLUMES, build_base_services
from vault_plugins import VaultServicePlugin
from vault_plugins.registry import get_active_plugin

OUTPUT_FILE = Path("docker-compose.generated.yml")


def _read_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        data[key] = value
    return data


def load_environment() -> dict[str, str]:
    """Merge .env values with the current environment."""

    env_path = Path(".env")
    env: dict[str, str] = _read_env_file(env_path)
    env.update(os.environ)
    return env


def _parse_container_names(value: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[,\s]+", value):
        entry = token.strip()
        if not entry or entry in seen:
            continue
        names.append(entry)
        seen.add(entry)
    return names


def _ensure_web_containers(
    env: Mapping[str, str], plugin: VaultServicePlugin
) -> tuple[list[str], str]:
    env_value = env.get("VAULT_WEB_CONTAINERS", "").strip()
    if env_value:
        names = _parse_container_names(env_value)
        if names:
            return names, env_value

    names = list(plugin.get_containers())
    if not names:
        raise RuntimeError(
            "Active plugin returned no web containers; set VAULT_WEB_CONTAINERS manually"
        )
    return names, ",".join(names)


def build_compose_manifest(
    env: Mapping[str, str], plugin: VaultServicePlugin | None = None
) -> OrderedDict[str, object]:
    """Construct the docker-compose manifest for the active plugin."""

    if plugin is None:
        active_plugin = get_active_plugin(env)
    else:
        active_plugin = plugin
        active_plugin.setup(env)
    plugin_data = active_plugin.build_compose(env)
    plugin_services = OrderedDict(plugin_data.get("services", {}))
    plugin_volumes = OrderedDict(plugin_data.get("volumes", {}))
    plugin_networks = OrderedDict(plugin_data.get("networks", {}))

    web_containers, web_container_string = _ensure_web_containers(env, active_plugin)

    base_services = build_base_services(env, web_containers, web_container_string)

    services: OrderedDict[str, dict] = OrderedDict()
    for dependency in active_plugin.dependencies:
        if dependency in plugin_services and dependency not in services:
            services[dependency] = plugin_services[dependency]

    for name, definition in plugin_services.items():
        if name not in services:
            services[name] = definition

    for name, definition in base_services.items():
        services[name] = definition

    volumes: OrderedDict[str, dict] = OrderedDict()
    for collection in (plugin_volumes, BASE_VOLUMES):
        for name, definition in collection.items():
            volumes[name] = definition

    networks: OrderedDict[str, dict] = OrderedDict()
    for collection in (plugin_networks, BASE_NETWORKS):
        for name, definition in collection.items():
            networks[name] = definition

    manifest: OrderedDict[str, object] = OrderedDict()
    manifest["services"] = services
    if volumes:
        manifest["volumes"] = volumes
    if networks:
        manifest["networks"] = networks

    return manifest


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _dump_list(items: list | tuple, indent: int) -> list[str]:
    indent_str = "  " * indent
    if not items:
        return [f"{indent_str}[]"]

    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            if not item:
                lines.append(f"{indent_str}- {{}}")
            else:
                lines.append(f"{indent_str}-")
                lines.extend(_dump_dict(item, indent + 1))
        elif isinstance(item, (list, tuple)):
            if not item:
                lines.append(f"{indent_str}- []")
            else:
                lines.append(f"{indent_str}-")
                lines.extend(_dump_list(list(item), indent + 1))
        else:
            lines.append(f"{indent_str}- {_format_scalar(item)}")
    return lines


def _dump_dict(data: Mapping[str, object], indent: int) -> list[str]:
    indent_str = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            if not value:
                lines.append(f"{indent_str}{key}: {{}}")
            else:
                lines.append(f"{indent_str}{key}:")
                lines.extend(_dump_dict(value, indent + 1))
        elif isinstance(value, (list, tuple)):
            if not value:
                lines.append(f"{indent_str}{key}: []")
            else:
                lines.append(f"{indent_str}{key}:")
                lines.extend(_dump_list(list(value), indent + 1))
        else:
            lines.append(f"{indent_str}{key}: {_format_scalar(value)}")
    return lines


def dump_yaml(data: Mapping[str, object]) -> str:
    """Serialize the manifest to a deterministic YAML string."""

    lines = _dump_dict(data, 0)
    return "\n".join(lines) + "\n"


def write_manifest(manifest: Mapping[str, object], path: Path = OUTPUT_FILE) -> None:
    yaml = dump_yaml(manifest)
    path.write_text(yaml)


def main() -> None:
    env = load_environment()
    plugin = get_active_plugin(env)
    print(f"[compose] Active service plugin: {plugin.name}")
    replicas = env.get("VAULT_WEB_REPLICAS", "").strip()
    print(f"[compose] Number of replicas chosen: {replicas}")
    manifest = build_compose_manifest(env, plugin)
    write_manifest(manifest, OUTPUT_FILE)
    print(f"[compose] Wrote {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
