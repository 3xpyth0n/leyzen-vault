"""Account management API endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from ..services.audit import AuditService
from ..services.auth_service import AuthService
from ..services.rate_limiter import RateLimiter
from ..utils.password_validator import validate_password_strength
from ..middleware.jwt_auth import jwt_required, get_current_user
from .utils import get_client_ip

account_bp = Blueprint("account", __name__)


def _get_audit() -> AuditService:
    """Get the audit service instance from Flask config."""
    return current_app.config["VAULT_AUDIT"]


def _get_auth_service() -> AuthService:
    """Get AuthService instance."""
    secret_key = current_app.config.get("SECRET_KEY", "")
    return AuthService(secret_key)


def _get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance from Flask config."""
    return current_app.config.get("VAULT_RATE_LIMITER")


# All frontend routes are handled by Vue.js SPA
# Only API routes remain here


@account_bp.route("/api/users/<user_id>", methods=["GET"])
@jwt_required
def get_user(user_id: str):
    """Get user information by ID."""
    from vault.database.schema import User, db

    user_obj = db.session.query(User).filter_by(id=user_id).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    # Return user info (without sensitive data)
    return (
        jsonify(
            {
                "user_id": user_obj.id,
                "username": user_obj.email,  # Use email as username
                "email": user_obj.email,
                "created_at": (
                    user_obj.created_at.isoformat() if user_obj.created_at else None
                ),
            }
        ),
        200,
    )


@account_bp.route("/api/users/search", methods=["GET"])
@jwt_required
def search_users():
    """Search users by username or email."""
    from vault.database.schema import User, db
    from sqlalchemy import or_

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    if len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400

    # Search users by email (username is email in PostgreSQL schema)
    search_pattern = f"%{query}%"
    users = (
        db.session.query(User)
        .filter(
            or_(
                User.email.ilike(search_pattern),
            ),
        )
        .limit(10)
        .all()
    )

    if not users:
        return jsonify({"error": "User not found"}), 404

    # Return first matching user (or could return list)
    user = users[0]
    return (
        jsonify(
            {
                "user_id": user.id,
                "username": user.email,
                "email": user.email,
            }
        ),
        200,
    )


@account_bp.route("/api/account", methods=["GET"])
@jwt_required
def get_account():
    """Get current user account information."""
    from vault.database.schema import User, db

    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user_obj = db.session.query(User).filter_by(id=user.id).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_obj.to_dict()), 200


@account_bp.route("/api/account/password", methods=["POST"])
@jwt_required
def change_password():
    """Change user password."""
    from vault.database.schema import User, db

    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = user.id
    user_ip = get_client_ip() or "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    origin = request.headers.get("Origin", "unknown")

    audit = _get_audit()

    # Enhanced rate limiting for sensitive operations
    rate_limiter = _get_rate_limiter()
    if rate_limiter:
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=3600,  # 1 hour window
            action_name="password_change",
            user_id=user_id,
        )
        if not is_allowed:
            audit.log_action(
                "password_change",
                user_ip,
                {
                    "error": "Rate limit exceeded",
                    "user_id": user_id,
                    "user_agent": user_agent,
                    "origin": origin,
                },
                False,
            )
            return jsonify({"error": error_msg or "Rate limit exceeded"}), 429

    if not request.is_json:
        audit.log_action(
            "password_change",
            user_ip,
            {
                "error": "Request must be JSON",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        audit.log_action(
            "password_change",
            user_ip,
            {
                "error": "Missing passwords",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "current_password and new_password are required"}), 400

    # Get user and verify current password
    user_obj = db.session.query(User).filter_by(id=user_id).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    # Verify current password using AuthService
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user_obj.email, current_password)
    if not result:
        audit.log_action(
            "password_change",
            user_ip,
            {
                "error": "Invalid current password",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "Invalid current password"}), 403

    # Validate new password strength using centralized validator
    is_valid, error_message = validate_password_strength(new_password)
    if not is_valid:
        audit.log_action(
            "password_change",
            user_ip,
            {
                "error": error_message or "Password validation failed",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": error_message or "Invalid password"}), 400

    # Update password using AuthService
    try:
        updated_user = auth_service.update_user(user_id, password=new_password)
        if not updated_user:
            audit.log_action(
                "password_change",
                user_ip,
                {
                    "error": "Failed to update password",
                    "user_id": user_id,
                    "user_agent": user_agent,
                    "origin": origin,
                },
                False,
            )
            return jsonify({"error": "Failed to update password"}), 500
    except ValueError as e:
        audit.log_action(
            "password_change",
            user_ip,
            {
                "error": str(e),
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": str(e)}), 400

    audit.log_action(
        "password_change",
        user_ip,
        {
            "user_id": user_id,
            "user_agent": user_agent,
            "origin": origin,
        },
        True,
    )

    return (
        jsonify({"status": "success", "message": "Password changed successfully"}),
        200,
    )


@account_bp.route("/api/account", methods=["DELETE"])
@jwt_required
def delete_account():
    """Delete user account."""
    from vault.database.schema import User, db

    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = user.id
    user_ip = get_client_ip() or "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    origin = request.headers.get("Origin", "unknown")

    audit = _get_audit()

    # Enhanced rate limiting for sensitive operations
    rate_limiter = _get_rate_limiter()
    if rate_limiter:
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=3,
            window_seconds=3600,  # 1 hour window
            action_name="account_delete",
            user_id=user_id,
        )
        if not is_allowed:
            audit.log_action(
                "account_delete",
                user_ip,
                {
                    "error": "Rate limit exceeded",
                    "user_id": user_id,
                    "user_agent": user_agent,
                    "origin": origin,
                },
                False,
            )
            return jsonify({"error": error_msg or "Rate limit exceeded"}), 429

    if not request.is_json:
        audit.log_action(
            "account_delete",
            user_ip,
            {
                "error": "Request must be JSON",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.json
    password = data.get("password")

    if not password:
        audit.log_action(
            "account_delete",
            user_ip,
            {
                "error": "Missing password",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "Password is required"}), 400

    # Get user and verify password
    user_obj = db.session.query(User).filter_by(id=user_id).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    # Verify password using AuthService
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user_obj.email, password)
    if not result:
        audit.log_action(
            "account_delete",
            user_ip,
            {
                "error": "Invalid password",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
        )
        return jsonify({"error": "Invalid password"}), 403

    # Permanently delete user account
    success = auth_service.delete_user(user_id)
    if not success:
        return jsonify({"error": "Failed to delete account"}), 500

    audit.log_action(
        "account_delete",
        user_ip,
        {
            "user_id": user_id,
            "user_agent": user_agent,
            "origin": origin,
        },
        True,
    )

    # Clear session (for backward compatibility)
    session.clear()

    return (
        jsonify({"status": "success", "message": "Account deleted successfully"}),
        200,
    )


__all__ = ["account_bp"]
