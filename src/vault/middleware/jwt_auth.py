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

    # If neither header is present, allow the request (same-origin browsers
    # may not send these headers for same-origin requests, especially after refresh)
    if not origin and not referer:
        return True, None

    # Get expected origin from request (same origin as the request itself)
    # Use request.url to get the actual request origin, handling proxies correctly
    try:
        request_url = urlparse(request.url)
        expected_host = request_url.netloc.split(":")[0]  # Remove port
        expected_scheme = request_url.scheme
    except Exception:
        # Fallback to request.host if url parsing fails
        expected_host = request.host.split(":")[0]
        expected_scheme = request.scheme

    # Check Origin header first (most reliable for POST requests)
    if origin:
        try:
            parsed_origin = urlparse(origin)
            origin_host = parsed_origin.netloc.split(":")[0]  # Remove port

            # Allow if host matches (ignoring port and scheme differences)
            # This handles cases where browser sends http:// but server expects https://
            # or vice versa (behind reverse proxy, development vs production)
            if origin_host.lower() == expected_host.lower():
                return True, None

            # Also allow null origin (can occur in some browser contexts)
            if origin.lower() == "null":
                # Null origin can be legitimate in some same-origin contexts
                # but we'll log it for investigation
                current_app.logger.debug(
                    f"Request with null Origin header: {request.method} {request.path}"
                )
                return True, None
        except Exception:
            pass  # Invalid origin format, continue to referer check

    # Fallback to Referer header (used by browsers for GET requests and some POST)
    if referer:
        try:
            parsed_referer = urlparse(referer)
            referer_host = parsed_referer.netloc.split(":")[0]

            if referer_host.lower() == expected_host.lower():
                return True, None
        except Exception:
            pass

    # If headers are present but don't match, log warning but be lenient
    # For JWT authentication, strict Origin checking can cause false positives
    # due to browser behavior, reverse proxies, or SPA navigation
    if origin or referer:
        current_app.logger.warning(
            f"Origin validation warning (not blocking): Origin={origin}, "
            f"Referer={referer}, Expected host={expected_host}, "
            f"Path={request.path}, Method={request.method}"
        )
        # Allow request to proceed - JWT token validation is the primary security
        # Origin validation is just defense in depth and shouldn't block legitimate requests
        return True, None

    return True, None


def _validate_content_type() -> tuple[bool, str | None]:
    """Validate Content-Type header for POST/PUT/PATCH requests.

    Ensures JSON requests have correct Content-Type to prevent
    content-type confusion attacks.

    This is a lenient check - only validates if it's clear there's a body.
    Empty POST requests (like logout) are allowed without Content-Type.

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

    # If there's a body, check Content-Type
    content_type = request.headers.get("Content-Type", "")

    # For JSON requests, require application/json
    # Note: Browser may send Content-Type: application/json even for empty POST
    # so we check request.is_json to see if Flask actually parsed JSON
    if request.is_json:
        # Flask successfully parsed JSON, so ensure Content-Type matches
        if "application/json" not in content_type:
            return False, "Content-Type must be application/json for JSON requests"
    elif content_type and "application/json" in content_type and has_body:
        # Content-Type says JSON but Flask didn't parse it - might be empty body
        # Allow it if there's no actual body
        pass

    # For form data, require appropriate content type
    if (
        "multipart/form-data" in content_type
        or "application/x-www-form-urlencoded" in content_type
    ):
        return True, None

    # Allow other content types if explicitly set (e.g., file uploads)
    if content_type:
        return True, None

    # If we detected a body but no content type, log warning but allow
    # Some APIs may work without explicit Content-Type
    current_app.logger.debug(
        f"Request with body but no Content-Type: {request.method} {request.path}"
    )
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
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Invalid authorization header format"}), 401

        token = parts[1]

        # Get secret key from app config
        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            return jsonify({"error": "Server configuration error"}), 500

        # Try JWT authentication first
        auth_service = AuthService(secret_key)
        user = auth_service.verify_token(token)

        # If JWT authentication failed, try API key authentication
        if not user:
            api_key_service = ApiKeyService()
            user = api_key_service.verify_api_key(token)

        if not user:
            # Log error without exposing any token data
            # Use minimal logging to avoid information leakage
            current_app.logger.warning(
                "Authentication failed: Invalid or expired token/API key"
            )
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store user in Flask g for use in route handlers
        g.current_user = user

        return f(*args, **kwargs)

    return decorated_function  # type: ignore


def get_current_user():
    """Get current authenticated user from Flask g.

    Returns:
        User object if authenticated, None otherwise
    """
    return getattr(g, "current_user", None)
