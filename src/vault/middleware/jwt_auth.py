"""JWT authentication middleware for Leyzen Vault."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar
from urllib.parse import urlparse

from flask import current_app, g, jsonify, request

from vault.services.api_key_service import ApiKeyService
from vault.services.auth_service import AuthService

F = TypeVar("F", bound=Callable)


def _validate_origin() -> tuple[bool, str | None]:
    """Validate Origin or Referer header for same-origin requests.

    This provides defense in depth against CSRF attacks even without
    CSRF tokens. JWT tokens in Authorization headers are already protected
    by Same-Origin Policy, so this is an additional safety check.

    Only validates if headers are present. If neither header is present,
    allows the request (same-origin browsers may not send these headers).

    For JWT-based authentication, we're more lenient since:
    - JWT tokens can't be read by cross-origin scripts (Same-Origin Policy)
    - JWT tokens must be explicitly sent in headers (not automatic like cookies)
    - This validation is just defense in depth

    Returns:
        (is_valid, error_message) - (True, None) if valid or headers missing
    """
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")

    # Get allowed origins from config (for CORS/SPA support)
    allowed_origins = current_app.config.get("ALLOWED_ORIGINS", [])
    allowed_origins_normalized = current_app.config.get(
        "ALLOWED_ORIGINS_NORMALIZED", set()
    )

    # Get production mode to determine strictness
    is_production = current_app.config.get("IS_PRODUCTION", True)
    # Get development allowed origins (for permissive but still active validation)
    allowed_origins_dev = current_app.config.get("ALLOWED_ORIGINS_DEV", [])

    # SECURITY: In production, require Origin or Referer for state-changing requests
    # GET requests are allowed without headers (same-origin browsers may not send them)
    # POST/PUT/DELETE/PATCH require Origin or Referer in production
    if not origin and not referer:
        if is_production and request.method in ("POST", "PUT", "DELETE", "PATCH"):
            current_app.logger.warning(
                f"Blocked {request.method} request without Origin or Referer header in production: {request.path}"
            )
            return (
                False,
                "Origin or Referer header required for state-changing requests in production",
            )
        # In development or for GET requests, allow without headers
        return True, None

    # Get expected origin from request (same origin as the request itself)
    # Use request.url to get the actual request origin, handling proxies correctly
    try:
        request_url = urlparse(request.url)
        expected_host = request_url.netloc.split(":")[0]  # Remove port
        expected_scheme = request_url.scheme
        expected_origin = f"{expected_scheme}://{expected_host}"
    except Exception:
        # Fallback to request.host if url parsing fails
        expected_host = request.host.split(":")[0]
        expected_scheme = request.scheme
        expected_origin = f"{expected_scheme}://{expected_host}"

    # Normalize expected origin for comparison
    expected_origin_normalized = f"{expected_scheme.lower()}://{expected_host.lower()}"

    # Check Origin header first (most reliable for POST requests)
    if origin:
        try:
            parsed_origin = urlparse(origin)
            origin_host = parsed_origin.netloc.split(":")[0]  # Remove port
            origin_normalized = (
                f"{parsed_origin.scheme.lower()}://{origin_host.lower()}"
            )

            # SECURITY: Block null origin (used in CSRF attacks)
            # Never allow null origin, even in development
            if origin.lower() == "null":
                current_app.logger.warning(
                    f"Blocked request with null Origin header: {request.method} {request.path}"
                )
                return False, "Null origin not allowed"

            # Check against allowed origins list first (exact match)
            if origin in allowed_origins:
                return True, None

            # Check normalized allowed origins
            if origin_normalized in allowed_origins_normalized:
                return True, None

            # Allow if host matches (ignoring port and scheme differences)
            # This handles cases where browser sends http:// but server expects https://
            # or vice versa (behind reverse proxy, development vs production)
            if origin_host.lower() == expected_host.lower():
                return True, None

            # In development: permissive but always active validation
            # SECURITY: Never allow localhost/127.0.0.1 in production, even if misconfigured
            if not is_production:
                # Only allow localhost in development mode
                if origin and ("localhost" in origin.lower() or "127.0.0.1" in origin):
                    return True, None
                # Check against development allowed origins
                if origin in allowed_origins_dev:
                    return True, None
                # Log warning but still validate
                import warnings

                warnings.warn(
                    f"Origin validation failed in dev mode: Origin={origin}, "
                    f"Expected host={expected_host}. Validation is permissive but active."
                )
                current_app.logger.warning(
                    f"Origin validation failed in dev mode (permissive): Origin={origin}, "
                    f"Expected host={expected_host}, Path={request.path}, Method={request.method}"
                )
                # In dev, we can be more permissive but still log
                return True, None  # Permissive but logged
            else:
                # In production: never allow localhost or 127.0.0.1, even if they match
                # This prevents misconfiguration from allowing insecure origins
                if origin and ("localhost" in origin.lower() or "127.0.0.1" in origin):
                    current_app.logger.error(
                        f"SECURITY: Blocked request with localhost/127.0.0.1 origin in production: {origin}"
                    )
                    return False, "Localhost origins are not allowed in production"

            # In production: strict validation
            current_app.logger.warning(
                f"Blocked request with invalid Origin: Origin={origin}, "
                f"Expected host={expected_host}, Path={request.path}, Method={request.method}"
            )
            return False, "Origin not allowed"
        except Exception:
            # Invalid origin format - always block
            current_app.logger.warning(
                f"Blocked request with invalid Origin format: {request.method} {request.path}"
            )
            # In production: always reject invalid origin format
            if is_production:
                current_app.logger.error(
                    f"SECURITY: Blocked request with invalid Origin format in production: {request.method} {request.path}"
                )
                return False, "Invalid origin format"
            # In development, log but allow (permissive)
            import warnings

            warnings.warn(
                f"Invalid origin format in dev mode: {request.method} {request.path}. "
                "Validation is permissive but active."
            )
            # Continue to referer check

    # Fallback to Referer header (used by browsers for GET requests and some POST)
    if referer:
        try:
            parsed_referer = urlparse(referer)
            referer_host = parsed_referer.netloc.split(":")[0]

            if referer_host.lower() == expected_host.lower():
                return True, None
        except Exception:
            pass

    # If headers are present but don't match, validate
    if origin or referer:
        if is_production:
            # In production: strict validation
            current_app.logger.warning(
                f"Blocked request: Origin={origin}, "
                f"Referer={referer}, Expected host={expected_host}, "
                f"Path={request.path}, Method={request.method}"
            )
            return False, "Origin validation failed"
        else:
            # In development: permissive but always active validation
            # SECURITY: Never allow localhost/127.0.0.1 in production
            if not is_production:
                # Only allow localhost in development mode
                if referer and (
                    "localhost" in referer.lower() or "127.0.0.1" in referer
                ):
                    return True, None
                # Log warning but allow (permissive)
                import warnings

                warnings.warn(
                    f"Origin validation failed in dev mode: Origin={origin}, "
                    f"Referer={referer}. Validation is permissive but active."
                )
                current_app.logger.warning(
                    f"Origin validation warning (permissive in dev): Origin={origin}, "
                    f"Referer={referer}, Expected host={expected_host}, "
                    f"Path={request.path}, Method={request.method}"
                )
            else:
                # In production: never allow localhost or 127.0.0.1 in referer
                if referer and (
                    "localhost" in referer.lower() or "127.0.0.1" in referer
                ):
                    current_app.logger.error(
                        f"SECURITY: Blocked request with localhost/127.0.0.1 referer in production: {referer}"
                    )
                    return False, "Localhost origins are not allowed in production"

    return True, None


def _validate_content_type() -> tuple[bool, str | None]:
    """Validate Content-Type header for POST/PUT/PATCH requests.

    Ensures JSON requests have correct Content-Type to prevent
    content-type confusion attacks.

    Returns:
        (is_valid, error_message) - (True, None) if valid
    """
    # Only validate for methods that typically have bodies
    if request.method not in ("POST", "PUT", "PATCH"):
        return True, None

    # Check if request actually has a body
    has_body = False

    # Check Content-Length header
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > 0:
                has_body = True
        except (ValueError, TypeError):
            pass

    # Check Transfer-Encoding header (chunked encoding)
    if request.headers.get("Transfer-Encoding") == "chunked":
        has_body = True

    # If no body detected, allow the request (e.g., empty POST like logout)
    if not has_body:
        return True, None

    # SECURITY: Require Content-Type for all requests with body
    content_type = request.headers.get("Content-Type", "")
    if not content_type:
        current_app.logger.warning(
            f"Request with body but no Content-Type: {request.method} {request.path}"
        )
        return False, "Content-Type header is required for requests with body"

    # For JSON requests, require application/json
    if request.is_json:
        # Flask successfully parsed JSON, so ensure Content-Type matches
        if "application/json" not in content_type:
            return False, "Content-Type must be application/json for JSON requests"

    # For form data, require appropriate content type
    if (
        "multipart/form-data" in content_type
        or "application/x-www-form-urlencoded" in content_type
    ):
        return True, None

    # Allow other content types if explicitly set (e.g., file uploads, text/plain)
    if content_type:
        return True, None

    return True, None


def jwt_required(f: F) -> F:
    """Decorator to require JWT authentication.

    Also performs security validations:
    - Origin/Referer header validation (defense in depth against CSRF)
    - Content-Type validation (prevents content-type confusion)

    Usage:
        @jwt_required
        def my_protected_route():
            user = g.current_user
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validate Origin/Referer headers (defense in depth)
        origin_valid, origin_error = _validate_origin()
        if not origin_valid:
            current_app.logger.warning(f"Origin validation failed: {origin_error}")
            return jsonify({"error": "Request origin validation failed"}), 403

        # Validate Content-Type for requests with body
        content_type_valid, content_type_error = _validate_content_type()
        if not content_type_valid:
            current_app.logger.warning(
                f"Content-Type validation failed: {content_type_error}"
            )
            return jsonify({"error": content_type_error}), 400

        # Validate JWT token
        # Try to get token from Authorization header first (priority for API keys)
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # Extract token from "Bearer <token>"
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

        # Fallback to cookie if Authorization header is not present
        # This supports SSO flows that use HttpOnly cookies
        if not token:
            token = request.cookies.get("jwt_token")

        if not token:
            return jsonify({"error": "Authorization header or cookie missing"}), 401

        # Get secret key from app config
        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            return jsonify({"error": "Server configuration error"}), 500

        # Try JWT authentication first
        settings = current_app.config.get("VAULT_SETTINGS")
        jwt_expiration_hours = settings.jwt_expiration_hours if settings else 120
        auth_service = AuthService(
            secret_key, jwt_expiration_hours=jwt_expiration_hours
        )
        user = auth_service.verify_token(token)

        # If JWT authentication failed, try API key authentication
        if not user:
            secret_key = current_app.config.get("SECRET_KEY", "")
            api_key_service = ApiKeyService(secret_key=secret_key)
            user = api_key_service.verify_api_key(token)

        if not user:
            # Log error without exposing any token data
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store user and token in Flask g for use in route handlers
        g.current_user = user
        g.current_token = token  # Store token for logout/blacklist operations

        return f(*args, **kwargs)

    return decorated_function  # type: ignore


def get_current_user():
    """Get current authenticated user from Flask g.

    Returns:
        User object if authenticated, None otherwise
    """
    return getattr(g, "current_user", None)
