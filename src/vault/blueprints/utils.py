"""Shared utilities for vault blueprints."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, TypeVar

from flask import current_app, request, session

from common.constants import LOGIN_BLOCK_WINDOW_MINUTES, MAX_LOGIN_ATTEMPTS
from common.utils import get_client_ip as _get_client_ip_base
from ..config import VaultSettings

F = TypeVar("F", bound=Callable[..., object])

# Login attempt tracking for rate limiting
login_attempts: defaultdict[str | None, deque] = defaultdict(
    lambda: deque(maxlen=MAX_LOGIN_ATTEMPTS)
)
BLOCK_WINDOW = timedelta(minutes=LOGIN_BLOCK_WINDOW_MINUTES)


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


def get_browser_fingerprint() -> str:
    """Generate a basic browser fingerprint from request headers.

    This creates a simple fingerprint using User-Agent and other headers
    to help detect bots and distributed attacks. The fingerprint is a hash
    of combined header values.

    Returns:
        Hexadecimal hash string representing the fingerprint
    """
    import hashlib

    # Collect fingerprint components
    components = []

    # User-Agent (most important for fingerprinting)
    user_agent = request.headers.get("User-Agent", "")
    components.append(f"ua:{user_agent}")

    # Accept-Language
    accept_lang = request.headers.get("Accept-Language", "")
    components.append(f"lang:{accept_lang}")

    # Accept-Encoding
    accept_enc = request.headers.get("Accept-Encoding", "")
    components.append(f"enc:{accept_enc}")

    # DNT (Do Not Track) header
    dnt = request.headers.get("DNT", "")
    components.append(f"dnt:{dnt}")

    # Combine all components and hash
    fingerprint_string = "|".join(components)
    fingerprint_hash = hashlib.sha256(fingerprint_string.encode("utf-8")).hexdigest()[
        :16
    ]

    return fingerprint_hash


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


# Error codes for standardized error responses
# Format: ERR_<CATEGORY>_<NUMBER>
# Categories: AUTH, VALID, FILE, RATE, DB, INTERNAL
ERROR_CODES = {
    "ERR_AUTH_001": "Authentication required.",
    "ERR_AUTH_002": "Invalid credentials.",
    "ERR_AUTH_003": "Token expired or invalid.",
    "ERR_AUTH_004": "Two-factor authentication required.",
    "ERR_VALID_001": "The request data is invalid.",
    "ERR_VALID_002": "Missing required field.",
    "ERR_VALID_003": "Invalid format.",
    "ERR_FILE_001": "The requested file was not found.",
    "ERR_FILE_002": "File operation failed.",
    "ERR_FILE_003": "File size exceeds limit.",
    "ERR_RATE_001": "Too many requests. Please try again later.",
    "ERR_RATE_002": "Rate limit exceeded. Please try again later.",
    "ERR_DB_001": "A database error occurred. Please try again later.",
    "ERR_INTERNAL_001": "An internal error occurred. Please try again later.",
    "ERR_NOT_FOUND_001": "The requested resource was not found.",
    "ERR_PERM_001": "You do not have permission to perform this action.",
}


def safe_error_response(
    error_code: str | None = None,
    error_type: str | None = None,
    status_code: int = 500,
    log_details: str | None = None,
) -> tuple[dict, int]:
    """Generate a safe error response without exposing internal details.

    Uses standardized error codes to prevent information leakage while
    providing consistent error messages to clients.

    Args:
        error_code: Standardized error code (e.g., "ERR_AUTH_001")
        error_type: Legacy error type (deprecated, use error_code instead)
        status_code: HTTP status code
        log_details: Optional detailed error message for logging (not exposed to client)

    Returns:
        Tuple of (error dict with code and message, status code)
    """
    # Log detailed error internally (in debug mode only)
    if log_details:
        current_app.logger.debug(f"Error {error_code or error_type}: {log_details}")

    # Use error code if provided, otherwise fall back to error_type
    if error_code and error_code in ERROR_CODES:
        message = ERROR_CODES[error_code]
        code = error_code
    elif error_type:
        # Legacy support: map error types to codes
        type_to_code = {
            "internal_error": "ERR_INTERNAL_001",
            "not_found": "ERR_NOT_FOUND_001",
            "validation_error": "ERR_VALID_001",
            "authentication_error": "ERR_AUTH_001",
            "authorization_error": "ERR_PERM_001",
            "rate_limit_error": "ERR_RATE_001",
            "file_not_found": "ERR_FILE_001",
            "database_error": "ERR_DB_001",
        }
        code = type_to_code.get(error_type, "ERR_INTERNAL_001")
        message = ERROR_CODES.get(code, "An error occurred.")
    else:
        # Default error
        code = "ERR_INTERNAL_001"
        message = ERROR_CODES[code]

    return {"error": message, "error_code": code}, status_code


def register_failed_attempt(
    ip: str | None, attempt_time: datetime | None = None
) -> None:
    """Register a failed login attempt for rate limiting.

    Args:
        ip: Client IP address (or None for unknown IPs)
        attempt_time: Time of the attempt (defaults to current time)
    """
    login_attempts[ip].append(attempt_time or datetime.now(timezone.utc))


__all__ = [
    "_settings",
    "get_client_ip",
    "get_browser_fingerprint",
    "login_required",
    "get_current_user_id",
    "safe_error_response",
    "register_failed_attempt",
]
