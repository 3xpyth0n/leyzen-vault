"""Input validation middleware for API endpoints.

This module provides decorators and utilities for consistent input validation
across API endpoints to prevent malformed input and ensure data integrity.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import current_app, jsonify, request

from vault.blueprints.validators import (
    validate_email,
    validate_file_id,
    validate_pagination_params,
    validate_uuid,
    validate_vaultspace_id,
)

F = TypeVar("F", bound=Callable)


def validate_json_request(f: F) -> F:
    """Decorator to validate that request contains valid JSON.

    Usage:
        @validate_json_request
        @jwt_required
        def my_endpoint():
            data = request.get_json()
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        try:
            data = request.get_json()
            if data is None:
                return jsonify({"error": "Request body cannot be empty"}), 400
        except Exception as e:
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                current_app.logger.debug(f"JSON parsing error: {e}")
            return jsonify({"error": "Invalid JSON format"}), 400

        return f(*args, **kwargs)

    return decorated_function  # type: ignore


def validate_uuid_param(param_name: str = "id"):
    """Decorator factory to validate UUID parameters.

    Usage:
        @validate_uuid_param("file_id")
        @jwt_required
        def get_file(file_id: str):
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            param_value = kwargs.get(param_name) or request.args.get(param_name)
            if not param_value:
                return (
                    jsonify({"error": f"{param_name} parameter is required"}),
                    400,
                )

            if not validate_uuid(param_value):
                return (
                    jsonify({"error": f"Invalid {param_name} format (must be UUID)"}),
                    400,
                )

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator


def validate_vaultspace_id_param(param_name: str = "vaultspace_id"):
    """Decorator factory to validate VaultSpace ID parameters.

    Usage:
        @validate_vaultspace_id_param()
        @jwt_required
        def get_vaultspace(vaultspace_id: str):
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            param_value = (
                kwargs.get(param_name)
                or request.args.get(param_name)
                or (request.get_json() or {}).get(param_name)
            )
            if not param_value:
                return (
                    jsonify({"error": f"{param_name} parameter is required"}),
                    400,
                )

            if not validate_vaultspace_id(param_value):
                return (
                    jsonify({"error": f"Invalid {param_name} format (must be UUID)"}),
                    400,
                )

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator


def validate_file_id_param(param_name: str = "file_id"):
    """Decorator factory to validate File ID parameters.

    Usage:
        @validate_file_id_param()
        @jwt_required
        def get_file(file_id: str):
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            param_value = (
                kwargs.get(param_name)
                or request.args.get(param_name)
                or (request.get_json() or {}).get(param_name)
            )
            if not param_value:
                return (
                    jsonify({"error": f"{param_name} parameter is required"}),
                    400,
                )

            if not validate_file_id(param_value):
                return (
                    jsonify({"error": f"Invalid {param_name} format (must be UUID)"}),
                    400,
                )

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator


def validate_pagination(f: F) -> F:
    """Decorator to validate pagination parameters.

    Usage:
        @validate_pagination
        @jwt_required
        def list_items():
            page = request.args.get("page", 1, type=int)
            per_page = request.args.get("per_page", 50, type=int)
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        page = request.args.get("page")
        per_page = request.args.get("per_page")

        page_val, per_page_val, error_msg = validate_pagination_params(
            page, per_page, max_per_page=100
        )

        if error_msg:
            return jsonify({"error": error_msg}), 400

        # Store validated values in request context for use in route handler
        request.validated_page = page_val
        request.validated_per_page = per_page_val

        return f(*args, **kwargs)

    return decorated_function  # type: ignore


def validate_email_param(param_name: str = "email"):
    """Decorator factory to validate email parameters.

    Usage:
        @validate_email_param()
        @jwt_required
        def update_email():
            data = request.get_json()
            email = data.get("email")
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            param_value = (
                kwargs.get(param_name)
                or request.args.get(param_name)
                or (request.get_json() or {}).get(param_name)
            )
            if not param_value:
                return (
                    jsonify({"error": f"{param_name} parameter is required"}),
                    400,
                )

            if not validate_email(param_value):
                return (
                    jsonify({"error": f"Invalid {param_name} format"}),
                    400,
                )

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator


__all__ = [
    "validate_json_request",
    "validate_uuid_param",
    "validate_vaultspace_id_param",
    "validate_file_id_param",
    "validate_pagination",
    "validate_email_param",
]
