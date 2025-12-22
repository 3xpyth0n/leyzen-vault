"""RBAC middleware for Leyzen Vault."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import jsonify

from vault.database.schema import GlobalRole
from vault.middleware.jwt_auth import get_current_user

F = TypeVar("F", bound=Callable)


def require_role(required_role: GlobalRole | str):
    """Decorator to require a specific global role.

    Usage:
        @require_role(GlobalRole.ADMIN)
        @jwt_required
        def admin_route():
            ...
    """
    if isinstance(required_role, str):
        required_role = GlobalRole(required_role)

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401

            # Check role hierarchy
            role_hierarchy = {
                GlobalRole.USER: 1,
                GlobalRole.ADMIN: 2,
                GlobalRole.SUPERADMIN: 3,
            }

            user_level = role_hierarchy.get(user.global_role, 0)
            required_level = role_hierarchy.get(required_role, 999)

            if user_level < required_level:
                return jsonify({"error": "Insufficient permissions"}), 403

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator


def require_permission(permission_type: str):
    """Decorator to require ownership of a resource (legacy, checks ownership only).

    Usage:
        @require_permission("read")
        @jwt_required
        def read_resource(resource_id):
            ...
    """

    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401

            # Extract resource_id from route parameters
            resource_id = (
                kwargs.get("resource_id")
                or kwargs.get("file_id")
                or kwargs.get("vaultspace_id")
            )
            if not resource_id:
                from flask import request

                resource_id = request.args.get("resource_id") or (
                    request.json.get("resource_id") if request.is_json else None
                )

            if not resource_id:
                return jsonify({"error": "Resource ID required"}), 400

            # Check ownership (for files)
            from vault.database.schema import File, db

            file_obj = db.session.query(File).filter_by(id=resource_id).first()
            if not file_obj or file_obj.owner_user_id != user.id:
                return jsonify({"error": "Permission denied"}), 403

            return f(*args, **kwargs)

        return decorated_function  # type: ignore

    return decorator
