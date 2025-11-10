"""Shared utilities for orchestrator blueprints."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import current_app, redirect, request, session, url_for

from common.utils import get_client_ip as _get_client_ip_base
from ..config import Settings

F = TypeVar("F", bound=Callable[..., object])


def _settings() -> Settings:
    """Get application settings from Flask config.

    This is the standard way to access settings across all blueprints.
    Use this function instead of accessing current_app.config["SETTINGS"] directly.

    The Settings type is specific to the Orchestrator application and includes
    settings like rotation intervals, Docker proxy configuration, and orchestrator-specific
    security settings.

    Returns:
        Settings instance with all orchestrator application configuration

    Note:
        This function returns Settings, which is different from the VaultSettings
        type used in the Vault application. See docs/AUTHENTICATION.md for details
        on the differences between vault and orchestrator settings.
    """
    return current_app.config["SETTINGS"]


def get_client_ip() -> str | None:
    """Extract the real client IP address from request headers.

    This function wraps the common get_client_ip function to automatically use
    the proxy_trust_count from Settings. This ensures that IP extraction respects
    the configured proxy setup without requiring callers to pass the proxy_trust_count
    parameter explicitly.

    Respects proxy trust count configuration to determine the correct
    IP address when behind a reverse proxy.

    Returns:
        Client IP address as string, or None if cannot be determined

    Note:
        This wrapper is necessary because the common get_client_ip function
        requires proxy_trust_count to be passed explicitly, but we want to
        automatically use the value from Settings for consistency.
    """
    settings = _settings()
    return _get_client_ip_base(proxy_trust_count=settings.proxy_trust_count)


def login_required(view: F) -> F:
    """Decorator to require authentication for a view.

    Redirects unauthenticated users to the login page with a next parameter.
    """

    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return decorated  # type: ignore[return-value]


__all__ = ["_settings", "get_client_ip", "login_required"]
