"""Account management API endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from ..extensions import csrf
from ..services.audit import AuditService
from ..services.auth_service import AuthService
from ..utils.password_validator import validate_password_strength
from .utils import get_client_ip, get_current_user_id, login_required

account_bp = Blueprint("account", __name__)


def _get_audit() -> AuditService:
    """Get the audit service instance from Flask config."""
    return current_app.config["VAULT_AUDIT"]


def _get_auth_service() -> AuthService:
    """Get AuthService instance."""
    secret_key = current_app.config.get("SECRET_KEY", "")
    return AuthService(secret_key)


# All frontend routes are handled by Vue.js SPA
# Only API routes remain here


@account_bp.route("/api/users/<user_id>", methods=["GET"])
@login_required
def get_user(user_id: str):
    """Get user information by ID."""
    from vault.database.schema import User, db

    user_obj = db.session.query(User).filter_by(id=user_id, is_active=True).first()
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
@login_required
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
            User.is_active == True,
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
@login_required
def get_account():
    """Get current user account information."""
    from vault.database.schema import User, db

    user_id = get_current_user_id()
    username = session.get("username")

    # Handle legacy mode (user_id is None but logged_in is True)
    if not user_id:
        # Legacy mode - return basic info from session
        return (
            jsonify(
                {
                    "user_id": None,
                    "username": username or "Unknown",
                    "email": None,
                    "created_at": None,
                    "last_login": None,
                    "is_active": True,
                }
            ),
            200,
        )

    user_obj = db.session.query(User).filter_by(id=user_id, is_active=True).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_obj.to_dict()), 200


@account_bp.route("/api/account/password", methods=["POST"])
@login_required
def change_password():
    """Change user password."""
    from vault.database.schema import User, db

    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    if not request.is_json:
        audit.log_action(
            "password_change",
            user_ip,
            {"error": "Request must be JSON", "user_id": user_id},
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
            {"error": "Missing passwords", "user_id": user_id},
            False,
        )
        return jsonify({"error": "current_password and new_password are required"}), 400

    # Get user and verify current password
    user_obj = db.session.query(User).filter_by(id=user_id, is_active=True).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    # Verify current password using AuthService
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user_obj.email, current_password)
    if not result:
        audit.log_action(
            "password_change",
            user_ip,
            {"error": "Invalid current password", "user_id": user_id},
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
                {"error": "Failed to update password", "user_id": user_id},
                False,
            )
            return jsonify({"error": "Failed to update password"}), 500
    except ValueError as e:
        audit.log_action(
            "password_change",
            user_ip,
            {"error": str(e), "user_id": user_id},
            False,
        )
        return jsonify({"error": str(e)}), 400

    audit.log_action(
        "password_change",
        user_ip,
        {"user_id": user_id},
        True,
    )

    return (
        jsonify({"status": "success", "message": "Password changed successfully"}),
        200,
    )


@account_bp.route("/api/account", methods=["DELETE"])
@login_required
def delete_account():
    """Delete user account."""
    from vault.database.schema import User, db

    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    if not request.is_json:
        audit.log_action(
            "account_delete",
            user_ip,
            {"error": "Request must be JSON", "user_id": user_id},
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.json
    password = data.get("password")

    if not password:
        audit.log_action(
            "account_delete",
            user_ip,
            {"error": "Missing password", "user_id": user_id},
            False,
        )
        return jsonify({"error": "Password is required"}), 400

    # Get user and verify password
    user_obj = db.session.query(User).filter_by(id=user_id, is_active=True).first()
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    # Verify password using AuthService
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user_obj.email, password)
    if not result:
        audit.log_action(
            "account_delete",
            user_ip,
            {"error": "Invalid password", "user_id": user_id},
            False,
        )
        return jsonify({"error": "Invalid password"}), 403

    # Soft delete: mark user as inactive
    user_obj.is_active = False
    db.session.commit()

    audit.log_action(
        "account_delete",
        user_ip,
        {"user_id": user_id},
        True,
    )

    # Clear session
    session.clear()

    return (
        jsonify({"status": "success", "message": "Account deleted successfully"}),
        200,
    )


__all__ = ["account_bp"]
