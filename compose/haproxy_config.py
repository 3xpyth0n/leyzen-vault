"""HAProxy configuration helpers for Leyzen Vault."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from vault_plugins import VaultServicePlugin

HAPROXY_CONFIG_PATH = Path("haproxy") / "haproxy.cfg"


def resolve_backend_port(env: Mapping[str, str], plugin: VaultServicePlugin) -> int:
    """Return the backend port for the active plugin."""

    override = env.get("VAULT_WEB_PORT", "").strip()
    if override:
        try:
            port = int(override)
        except ValueError:
            port = None
        else:
            if 1 <= port <= 65535:
                return port
    plugin_port = getattr(plugin, "web_port", 80)
    try:
        port = int(plugin_port)
    except (TypeError, ValueError):
        return 80
    return port if 1 <= port <= 65535 else 80


def _format_backend_servers(containers: Sequence[str], port: int) -> list[str]:
    lines: list[str] = []
    for name in containers:
        lines.append(f"    server {name} {name}:{port} check")
    if not lines:
        lines.append("    # No backend servers configured")
    return lines


def render_haproxy_config(
    plugin: VaultServicePlugin, containers: Sequence[str], port: int
) -> str:
    """Return the HAProxy configuration for the supplied plugin."""

    backend_name = f"{plugin.name}_backend"
    server_lines = _format_backend_servers(containers, port)
    lines = [
        "global",
        "    log stdout format raw local0",
        "    maxconn 4096",
        "",
        "resolvers docker",
        "    nameserver dns1 127.0.0.11:53",
        "    resolve_retries       3",
        "    timeout resolve        1s",
        "    timeout retry          1s",
        "    hold valid            10s",
        "",
        "defaults",
        "    log     global",
        "    mode    http",
        "    option  httplog",
        "    option  dontlog-normal",
        "    option  dontlognull",
        "    default-server init-addr none resolvers docker",
        "    timeout connect 5s",
        "    timeout client  50s",
        "    timeout server  50s",
        "",
        "http-errors myerrors",
        "    errorfile 503 /usr/local/etc/haproxy/503.http",
        "    errorfile 404 /usr/local/etc/haproxy/404.http",
        "",
        "frontend http_front",
        "    bind *:80",
        "    errorfiles myerrors",
        "    http-response return status 404 errorfile /usr/local/etc/haproxy/404.http if { status 404 }",
        "    http-request set-header X-Forwarded-Proto https if { ssl_fc }",
        '    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains" if { ssl_fc }',
        "",
        "    acl path_orchestrator path_beg /orchestrator",
        "    use_backend orchestrator_backend if path_orchestrator",
        "",
        f"    default_backend {backend_name}",
        "",
        f"backend {backend_name}",
        "    balance roundrobin",
        "    option http-server-close",
        "    option forwardfor header X-Forwarded-For if-none",
        "    default-server resolvers docker init-addr none check",
    ]
    lines.extend(server_lines)
    lines.extend(
        [
            "",
            "backend orchestrator_backend",
            "    option http-server-close",
            "    option forwardfor header X-Forwarded-For if-none",
            "    default-server resolvers docker init-addr none check",
            "    server orchestrator orchestrator:80",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["HAPROXY_CONFIG_PATH", "render_haproxy_config", "resolve_backend_port"]
