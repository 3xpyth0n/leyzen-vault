"""Compose manifest builder for Leyzen Vault."""

from __future__ import annotations

# ruff: noqa: E402

import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Mapping

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from compose.base_stack import BASE_NETWORKS, BASE_VOLUMES, build_base_services
from compose.haproxy_config import (
    HAPROXY_CONFIG_PATH,
    render_haproxy_config,
    resolve_backend_port,
)
from leyzen_common.env import parse_container_names, read_env_file
from vault_plugins import VaultServicePlugin
from vault_plugins.registry import get_active_plugin

OUTPUT_FILE = Path("docker-compose.yml")


def load_environment() -> dict[str, str]:
    """Merge .env values with the current environment."""

    override = os.environ.get("LEYZEN_ENV_FILE", ".env").strip()
    if override:
        env_path = Path(override).expanduser()
        if not env_path.is_absolute():
            env_path = (ROOT_DIR / env_path).resolve()
    else:
        env_path = (ROOT_DIR / ".env").resolve()

    env: dict[str, str] = read_env_file(env_path)
    env.update(os.environ)
    return env


def resolve_web_containers(
    env: Mapping[str, str], plugin: VaultServicePlugin
) -> tuple[list[str], str]:
    env_value = env.get("VAULT_WEB_CONTAINERS", "").strip()
    if env_value:
        names = parse_container_names(env_value)
        if names:
            return names, env_value

    names = list(plugin.get_containers())
    if not names:
        raise RuntimeError(
            "Active plugin returned no web containers; set VAULT_WEB_CONTAINERS manually"
        )
    return names, ",".join(names)


def build_compose_manifest(
    env: Mapping[str, str],
    plugin: VaultServicePlugin | None = None,
    *,
    web_containers: list[str] | None = None,
    web_container_string: str | None = None,
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

    if web_containers is None or web_container_string is None:
        web_containers, web_container_string = resolve_web_containers(
            env, active_plugin
        )

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

    try:
        plugin = get_active_plugin(env)
    except KeyError as e:
        # Extract the invalid name from the message for clarity
        raw_service = env.get("VAULT_SERVICE", "").strip() or "(none)"
        print("\n[error] Invalid service selected in .env")
        print(f"        VAULT_SERVICE = '{raw_service}' is not recognized.")
        print(f"        {e}")
        sys.exit(1)

    print(f"[compose] Active service plugin: {plugin.name}")
    replicas_raw = env.get("VAULT_WEB_REPLICAS", "").strip()
    if replicas_raw:
        print(f"[compose] Number of replicas chosen: {replicas_raw}")
    else:
        print(
            f"[compose] Number of replicas chosen: {plugin.active_replicas} (default)"
        )
    web_containers, web_container_string = resolve_web_containers(env, plugin)
    backend_port = resolve_backend_port(env, plugin)
    haproxy_config = render_haproxy_config(plugin, web_containers, backend_port)
    HAPROXY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    HAPROXY_CONFIG_PATH.write_text(haproxy_config)
    backend_summary = ", ".join(f"{name}:{backend_port}" for name in web_containers)
    print(
        f"[haproxy] Generated config for plugin: {plugin.name} "
        f"({len(web_containers)} replica{'s' if len(web_containers) != 1 else ''})"
    )
    if backend_summary:
        print(f"[haproxy] Backends: {backend_summary}")
    manifest = build_compose_manifest(
        env,
        plugin,
        web_containers=web_containers,
        web_container_string=web_container_string,
    )

    override_env_file = os.environ.get("LEYZEN_ENV_FILE")
    if override_env_file:
        override_path = Path(override_env_file).expanduser().resolve()
        # pour garder la lisibilité dans le compose, on n’écrit que le nom du fichier
        short_name = override_path.name
        print(f"[compose] Overriding env_file entries with: {short_name}")
        for svc_name, svc_def in manifest.get("services", {}).items():
            if "env_file" in svc_def:
                svc_def["env_file"] = [short_name]

    write_manifest(manifest, OUTPUT_FILE)
    print(f"[compose] Wrote {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
