"""Compose manifest builder for Leyzen Vault."""

from __future__ import annotations

# ruff: noqa: E402

import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Mapping, cast

# Bootstrap minimal to enable importing common.path_setup
# This must be done before importing common modules
# Standard pattern: Manually add src/ to sys.path, then use bootstrap_entry_point()
# Note: This local calculation is ONLY needed for the initial bootstrap before
# common.constants can be imported. After bootstrap, use SRC_DIR from common.constants.
# The calculation is necessary to avoid circular import dependencies.
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point

# Complete the bootstrap sequence (idempotent)
bootstrap_entry_point()

from compose.base_stack import (
    BASE_NETWORKS,
    BASE_VOLUMES,
    build_base_services,
    validate_ssl_certificates,
)
from compose.haproxy_config import render_haproxy_config, resolve_backend_port
from common.constants import HAPROXY_CONFIG_PATH, REPO_ROOT
from common.env import load_env_with_override, parse_container_names
from vault_plugins import VaultServicePlugin
from vault_plugins.registry import get_active_plugin

OUTPUT_FILE = REPO_ROOT / "docker-compose.yml"


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
    plugin_services = OrderedDict(
        cast(Mapping[str, object], plugin_data.get("services", {}))
    )
    plugin_volumes = OrderedDict(
        cast(Mapping[str, object], plugin_data.get("volumes", {}))
    )
    plugin_networks = OrderedDict(
        cast(Mapping[str, object], plugin_data.get("networks", {}))
    )

    if web_containers is None or web_container_string is None:
        web_containers, web_container_string = resolve_web_containers(
            env, active_plugin
        )

    base_services = build_base_services(env, web_containers, web_container_string)

    services: OrderedDict[str, dict] = OrderedDict()
    for dependency in active_plugin.dependencies:
        if dependency in plugin_services and dependency not in services:
            services[dependency] = cast(dict, plugin_services[dependency])

    for name, definition in plugin_services.items():
        if name not in services:
            services[name] = cast(dict, definition)

    for name, definition in base_services.items():
        services[name] = definition

    volumes: OrderedDict[str, dict[str, object]] = OrderedDict()
    for collection in (plugin_volumes, BASE_VOLUMES):
        for name, definition in collection.items():
            volumes[name] = cast(dict[str, object], definition)

    networks: OrderedDict[str, dict[str, object]] = OrderedDict()
    for collection in (plugin_networks, BASE_NETWORKS):
        for name, definition in collection.items():
            networks[name] = cast(dict[str, object], definition)

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
    from common.constants import REPO_ROOT

    env: dict[str, str] = load_env_with_override(REPO_ROOT)
    env.update(os.environ)

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

    # Read HTTPS configuration from environment
    enable_https_raw = env.get("VAULT_ENABLE_HTTPS", "").strip().lower()
    enable_https = enable_https_raw in ("true", "1", "yes", "on")
    ssl_cert_path = env.get("VAULT_SSL_CERT_PATH", "").strip() or None
    ssl_key_path = env.get("VAULT_SSL_KEY_PATH", "").strip() or None

    # Read HTTP and HTTPS port configuration
    http_port_raw = env.get("VAULT_HTTP_PORT", "").strip()
    https_port_raw = env.get("VAULT_HTTPS_PORT", "").strip()
    try:
        http_port = int(http_port_raw) if http_port_raw else 8080
        http_port = max(1, min(65535, http_port))
    except ValueError:
        http_port = 8080
    try:
        https_port = int(https_port_raw) if https_port_raw else 8443
        https_port = max(1, min(65535, https_port))
    except ValueError:
        https_port = 8443

    print(f"[haproxy] HTTP port: {http_port}:80")
    if enable_https:
        print(f"[haproxy] HTTPS port: {https_port}:443")

    # Validate SSL certificates if HTTPS is enabled
    if enable_https:
        is_valid, warnings = validate_ssl_certificates(
            enable_https, ssl_cert_path, ssl_key_path, REPO_ROOT
        )
        if not is_valid:
            print("\n[warning] HTTPS is enabled but certificate validation failed:")
            for warning in warnings:
                print(f"         {warning}")
            print("         HAProxy will start but HTTPS may not work correctly.\n")
        else:
            print("[haproxy] HTTPS: enabled")
            if ssl_cert_path:
                print(f"[haproxy] SSL certificate: {ssl_cert_path}")
            if ssl_key_path:
                print(f"[haproxy] SSL key: {ssl_key_path}")
    else:
        print("[haproxy] HTTPS: disabled")

    # Prepare container paths for SSL certificates (these are the paths inside the container)
    ssl_cert_path_container: str | None = None
    ssl_key_path_container: str | None = None
    if enable_https and ssl_cert_path:
        # Use the container path where the certificate will be mounted
        ssl_cert_path_container = "/usr/local/etc/haproxy/ssl/cert.pem"
        if ssl_key_path:
            ssl_key_path_container = "/usr/local/etc/haproxy/ssl/key.pem"

    # Generate HAProxy configuration with HTTPS support
    haproxy_config = render_haproxy_config(
        plugin,
        web_containers,
        backend_port,
        enable_https=enable_https,
        ssl_cert_path=ssl_cert_path_container,
        ssl_key_path=ssl_key_path_container,
    )
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

    write_manifest(manifest, OUTPUT_FILE)
    print(f"[compose] Wrote {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
