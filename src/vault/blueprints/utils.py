"""Shared utilities for vault blueprints."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import current_app, request, session, url_for

from common.utils import get_client_ip as _get_client_ip_base
from ..config import VaultSettings

F = TypeVar("F", bound=Callable[..., object])


def _settings() -> VaultSettings:
    """Get application settings from Flask config.

    This function wraps access to current_app.config["VAULT_SETTINGS"] to provide
    type safety and consistency. The VaultSettings type is specific to the Vault
    application and includes settings like SMTP configuration, file upload limits,
    and vault-specific security settings.

    Returns:
        VaultSettings instance with all vault application configuration

    Note:
        This function returns VaultSettings, which is different from the Settings
        type used in the Orchestrator. See docs/AUTHENTICATION.md for details on
        the differences between vault and orchestrator settings.
    """
    return current_app.config["VAULT_SETTINGS"]


def get_client_ip() -> str | None:
    """Extract the real client IP address from request headers.

    This function wraps the common get_client_ip function to automatically use
    the proxy_trust_count from VaultSettings. This ensures that IP extraction
    respects the configured proxy setup without requiring callers to pass the
    proxy_trust_count parameter explicitly.

    Respects proxy trust count configuration to determine the correct
    IP address when behind a reverse proxy.

    Returns:
        Client IP address as string, or None if cannot be determined

    Note:
        This wrapper is necessary because the common get_client_ip function
        requires proxy_trust_count to be passed explicitly, but we want to
        automatically use the value from VaultSettings for consistency.
    """
    settings = _settings()
    return _get_client_ip_base(proxy_trust_count=settings.proxy_trust_count)


def login_required(view: F) -> F:
    """Decorator to require authentication for a view.

    Returns 401 JSON error for unauthenticated requests.
    All frontend routing is handled by Vue.js, so no redirects to Flask templates.
    """

    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            # Always return JSON error - Vue Router will handle redirects
            from flask import jsonify

            return jsonify({"error": "Not authenticated"}), 401
        return view(*args, **kwargs)

    return decorated  # type: ignore[return-value]


def get_current_user_id() -> str | None:
    """Get current user ID from session."""
    return session.get("user_id")


def safe_error_response(
    error_type: str, status_code: int = 500, log_details: str | None = None
) -> tuple[dict, int]:
    """Generate a safe error response without exposing internal details.

    Args:
        error_type: Type of error (e.g., "internal_error", "not_found", "validation_error")
        status_code: HTTP status code
        log_details: Optional detailed error message for logging (not exposed to client)

    Returns:
        Tuple of (error dict, status code)
    """
    # Log detailed error internally (in debug mode only)
    if log_details:
        current_app.logger.debug(f"Error {error_type}: {log_details}")

    # Map error types to user-friendly messages
    error_messages = {
        "internal_error": "An internal error occurred. Please try again later.",
        "not_found": "The requested resource was not found.",
        "validation_error": "The request data is invalid.",
        "authentication_error": "Authentication required.",
        "authorization_error": "You do not have permission to perform this action.",
        "rate_limit_error": "Too many requests. Please try again later.",
        "file_not_found": "The requested file was not found.",
        "database_error": "A database error occurred. Please try again later.",
    }

    message = error_messages.get(error_type, "An error occurred.")
    return {"error": message}, status_code


__all__ = [
    "_settings",
    "get_client_ip",
    "login_required",
    "get_current_user_id",
    "safe_error_response",
]
