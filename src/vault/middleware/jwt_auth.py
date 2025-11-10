"""JWT authentication middleware for Leyzen Vault."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import current_app, g, jsonify, request

from vault.services.api_key_service import ApiKeyService
from vault.services.auth_service import AuthService

F = TypeVar("F", bound=Callable)


def jwt_required(f: F) -> F:
    """Decorator to require JWT authentication.

    Usage:
        @jwt_required
        def my_protected_route():
            user = g.current_user
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
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
