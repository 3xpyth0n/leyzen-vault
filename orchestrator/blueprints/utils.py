"""Shared helpers for orchestrator blueprints."""

from __future__ import annotations

from functools import wraps
from ipaddress import ip_address
from typing import Callable, TypeVar

from flask import current_app, redirect, request, session, url_for

F = TypeVar("F", bound=Callable[..., object])


def get_client_ip() -> str | None:
    settings = current_app.config["SETTINGS"]
    proxy_trust_count = settings.proxy_trust_count

    if proxy_trust_count > 0:
        header_value = request.headers.get("X-Forwarded-For", "")
        if header_value:
            forwarded_ips = [ip.strip() for ip in header_value.split(",") if ip.strip()]
            for candidate in forwarded_ips:
                try:
                    parsed = ip_address(candidate)
                except ValueError:
                    continue

                if not (
                    parsed.is_private
                    or parsed.is_loopback
                    or parsed.is_reserved
                    or parsed.is_link_local
                ):
                    return candidate

            if forwarded_ips:
                return forwarded_ips[0]

    return request.remote_addr


def login_required(view: F) -> F:
    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return decorated  # type: ignore[return-value]


__all__ = ["get_client_ip", "login_required"]
