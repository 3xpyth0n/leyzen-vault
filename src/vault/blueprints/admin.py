"""Admin dashboard API routes with advanced features."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from vault.database.schema import GlobalRole, db
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required, require_role
from vault.services.admin_service import AdminService
from vault.services.quota_service import QuotaService

admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")


def _get_admin_service() -> AdminService:
    """Get AdminService instance."""
    from flask import current_app

    audit_service = current_app.config.get("VAULT_AUDIT")

    # Get QuotaService with proper configuration
    quota_service = _get_quota_service()

    return AdminService(audit_service=audit_service, quota_service=quota_service)


def _get_quota_service() -> QuotaService:
    """Get QuotaService instance with storage directory and max total size."""
    storage = current_app.config.get("VAULT_STORAGE")
    storage_dir = None
    if storage and hasattr(storage, "storage_dir"):
        storage_dir = storage.storage_dir

    # Get max_total_size_mb from settings and convert to bytes
    max_total_size_bytes = None
    settings = current_app.config.get("VAULT_SETTINGS")
    if (
        settings
        and hasattr(settings, "max_total_size_mb")
        and settings.max_total_size_mb
    ):
        max_total_size_bytes = settings.max_total_size_mb * 1024 * 1024

    return QuotaService(
        storage_dir=storage_dir, max_total_size_bytes=max_total_size_bytes
    )


@admin_api_bp.route("/users", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def list_users():
    """List all users with search and filters (admin only)."""
    admin_service = _get_admin_service()

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    query = request.args.get("query", "").strip() or None
    role = request.args.get("role", "").strip() or None

    result = admin_service.search_users(
        query=query, role=role, page=page, per_page=per_page
    )

    return jsonify(result), 200


@admin_api_bp.route("/users/<user_id>", methods=["PUT"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def update_user(user_id: str):
    """Update user (admin only).

    Rules:
        - Admin cannot modify superadmin users
        - Use /users/<user_id>/role endpoint for role changes
    """
    from vault.services.auth_service import AuthService
    from vault.database.schema import User

    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    auth_service = AuthService(current_app.config.get("SECRET_KEY", ""))

    # Get target user to check their role
    target_user = db.session.query(User).filter_by(id=user_id).first()
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    # Security check: Admin cannot modify superadmin users
    if current_user.global_role == GlobalRole.ADMIN:
        if target_user.global_role == GlobalRole.SUPERADMIN:
            return (
                jsonify({"error": "Admins cannot modify superadmin users"}),
                403,
            )

    try:
        # Prevent role changes via this endpoint - use /role endpoint instead
        global_role = None
        if data.get("global_role"):
            return (
                jsonify(
                    {"error": "Use /users/<user_id>/role endpoint to change user role"}
                ),
                400,
            )

        user = auth_service.update_user(
            user_id=user_id,
            email=data.get("email"),
            password=data.get("password"),
            global_role=global_role,
        )

        if not user:
            return jsonify({"error": "User not found"}), 404

        return (
            jsonify(
                {
                    "user": user.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/users/<user_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def delete_user(user_id: str):
    """Permanently delete user and all associated data (admin only).

    This performs a hard delete, removing:
    - User account
    - All VaultSpaces owned by the user
    - All files and folders owned by the user
    - All physical files from storage
    - All thumbnails
    - All related data (keys, permissions, etc.)

    This action cannot be undone.

    Rules:
        - Admin cannot delete superadmin users
        - Superadmin cannot delete their own account
        - At least one superadmin must always exist
    """
    from vault.services.auth_service import AuthService
    from vault.database.schema import User

    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "Authentication required"}), 401

    auth_service = AuthService(current_app.config.get("SECRET_KEY", ""))

    # Get target user (including inactive users for deletion check)
    target_user = db.session.query(User).filter_by(id=user_id).first()
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    # Security checks
    if current_user.global_role == GlobalRole.ADMIN:
        # Admin cannot delete superadmin
        if target_user.global_role == GlobalRole.SUPERADMIN:
            return (
                jsonify({"error": "Admins cannot delete superadmin users"}),
                403,
            )
    elif current_user.global_role == GlobalRole.SUPERADMIN:
        # Superadmin cannot delete their own account
        if current_user.id == user_id:
            return (
                jsonify(
                    {
                        "error": "Superadmin cannot delete their own account. Transfer the superadmin role to another user first."
                    }
                ),
                403,
            )
        # Check if deleting this superadmin would leave no superadmin
        if target_user.global_role == GlobalRole.SUPERADMIN:
            superadmin_count = auth_service.count_superadmins()
            if superadmin_count <= 1:
                return (
                    jsonify(
                        {
                            "error": "Cannot delete the last superadmin. At least one superadmin must exist."
                        }
                    ),
                    400,
                )

    # Hard delete: permanently remove user and all data
    success = auth_service.delete_user(user_id, hard_delete=True)

    if not success:
        return jsonify({"error": "User not found"}), 404

    return (
        jsonify({"message": "User and all associated data deleted successfully"}),
        200,
    )


@admin_api_bp.route("/users/<user_id>/role", methods=["PUT"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def update_user_role(user_id: str):
    """Update user global role (admin or superadmin).

    Request body:
        {
            "global_role": "user" | "admin" | "superadmin"
        }

    Returns:
        JSON with updated user info

    Rules:
        - Admin can only assign "user" or "admin" roles
        - Admin cannot modify superadmin users
        - Superadmin can assign any role
        - Only one superadmin can exist at a time
        - If a superadmin assigns superadmin to another user, they become admin
    """
    from vault.services.auth_service import AuthService
    from vault.database.schema import User

    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    role_str = data.get("global_role", "").strip()
    if not role_str:
        return jsonify({"error": "global_role is required"}), 400

    try:
        new_role = GlobalRole(role_str)
    except ValueError:
        return jsonify({"error": f"Invalid global_role: {role_str}"}), 400

    auth_service = AuthService(current_app.config.get("SECRET_KEY", ""))

    # Get target user (including inactive users for role changes)
    target_user = db.session.query(User).filter_by(id=user_id).first()
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    # Security checks based on current user's role
    if current_user.global_role == GlobalRole.ADMIN:
        # Admin restrictions
        if target_user.global_role == GlobalRole.SUPERADMIN:
            return (
                jsonify({"error": "Admins cannot modify the role of superadmin users"}),
                403,
            )

        if new_role == GlobalRole.SUPERADMIN:
            return (
                jsonify({"error": "Admins cannot assign superadmin role"}),
                403,
            )
    # Track if we need to handle superadmin transfer
    need_superadmin_transfer = (
        current_user.global_role == GlobalRole.SUPERADMIN
        and new_role == GlobalRole.SUPERADMIN
        and target_user.global_role != GlobalRole.SUPERADMIN
    )

    if need_superadmin_transfer:
        # Transfer superadmin role: make all existing superadmins admin
        # This includes the current user if they are assigning to someone else
        # Do this in the same transaction as the role update
        superadmins = auth_service.get_superadmins()
        for superadmin in superadmins:
            if superadmin.id != target_user.id:
                superadmin.global_role = GlobalRole.ADMIN
        # Don't commit yet - wait for the role update to complete

    try:
        # Update the user's role
        # If this is a superadmin transfer, all other superadmins have already been
        # changed to admin in this transaction, so this will make the target user the only superadmin
        user = auth_service.update_user(
            user_id=user_id,
            global_role=new_role,
        )

        if not user:
            return jsonify({"error": "User not found"}), 404

        return (
            jsonify(
                {
                    "user": user.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/users/<user_id>", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_user_details(user_id: str):
    """Get detailed user information (admin only)."""
    admin_service = _get_admin_service()
    details = admin_service.get_user_details(user_id)

    if not details:
        return jsonify({"error": "User not found"}), 404

    return jsonify(details), 200


@admin_api_bp.route("/stats", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_stats():
    """Get comprehensive system statistics (admin only)."""
    admin_service = _get_admin_service()
    stats = admin_service.get_system_stats()

    return jsonify(stats), 200


@admin_api_bp.route("/quotas", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def list_quotas():
    """List all quotas with user storage usage (admin only)."""
    from vault.database.schema import Quota, User

    quota_service = _get_quota_service()

    # Get all users
    all_users = db.session.query(User).all()

    # Get all existing quotas
    existing_quotas = {q.user_id: q for q in db.session.query(Quota).all()}

    # Build quota list with actual usage for all users
    quotas_list = []
    for user in all_users:
        # Get quota if exists
        quota = existing_quotas.get(user.id)

        # Calculate actual storage used
        used_storage = quota_service.calculate_user_storage_used(user.id)

        # Calculate actual files count
        used_files = quota_service.calculate_user_files_count(user.id)

        # Build quota dict
        quota_dict = {
            "id": quota.id if quota else None,
            "user_id": user.id,
            "user_email": user.email,
            "max_storage_bytes": quota.max_storage_bytes if quota else None,
            "used_storage_bytes": used_storage,
            "max_files": quota.max_files if quota else None,
            "used_files": used_files,
            "updated_at": quota.updated_at.isoformat() if quota else None,
        }
        quotas_list.append(quota_dict)

    return jsonify({"quotas": quotas_list}), 200


@admin_api_bp.route("/quotas", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def create_or_update_quota():
    """Create or update quota (admin only)."""
    from vault.database.schema import Quota

    quota_service = _get_quota_service()
    data = request.get_json()

    user_id = data.get("user_id")
    max_storage_bytes = data.get("max_storage_bytes")
    max_files = data.get("max_files")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        # Convert None to 0 for unlimited quota
        storage_limit = max_storage_bytes if max_storage_bytes is not None else 0

        quota = quota_service.create_or_update_user_quota(
            user_id=user_id,
            storage_limit_bytes=storage_limit,
        )

        # Update max_files if provided (including None to clear it)
        if "max_files" in data:
            quota.max_files = max_files
        db.session.commit()

        return jsonify({"quota": quota.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/audit-logs", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_audit_logs():
    """Get audit logs with filters (admin only)."""
    admin_service = _get_admin_service()

    limit = int(request.args.get("limit", 100))
    action = request.args.get("action", "").strip() or None
    file_id = request.args.get("file_id", "").strip() or None
    success_param = request.args.get("success")
    success = None
    if success_param is not None:
        success = success_param.lower() in ("true", "1", "yes")
    user_ip = request.args.get("user_ip", "").strip() or None

    logs = admin_service.get_audit_logs(
        limit=limit, action=action, file_id=file_id, success=success, user_ip=user_ip
    )

    return jsonify({"logs": logs, "count": len(logs)}), 200


@admin_api_bp.route("/audit-logs/export/csv", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def export_audit_logs_csv():
    """Export audit logs to CSV (admin only)."""
    from flask import send_file
    import tempfile
    import os

    admin_service = _get_admin_service()
    limit = int(request.args.get("limit", 1000))

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    try:
        success = admin_service.export_audit_logs_csv(temp_path, limit=limit)
        if not success:
            return jsonify({"error": "Failed to export audit logs"}), 500

        return send_file(
            temp_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"audit_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
        )
    finally:
        # Clean up temp file after sending
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@admin_api_bp.route("/audit-logs/export/json", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def export_audit_logs_json():
    """Export audit logs to JSON (admin only)."""
    from flask import send_file
    import tempfile
    import os

    admin_service = _get_admin_service()
    limit = int(request.args.get("limit", 1000))

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    temp_path = temp_file.name
    temp_file.close()

    try:
        success = admin_service.export_audit_logs_json(temp_path, limit=limit)
        if not success:
            return jsonify({"error": "Failed to export audit logs"}), 500

        return send_file(
            temp_path,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"audit_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
        )
    finally:
        # Clean up temp file after sending
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# Admin invitation and user management routes


@admin_api_bp.route("/users/<user_id>/send-verification", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def send_verification_email_admin(user_id: str):
    """Resend verification email to user (admin only)."""
    from vault.services.email_verification_service import EmailVerificationService
    from vault.database.schema import User, db

    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    email_verification_service = EmailVerificationService()
    # VAULT_URL from settings will be used automatically
    success = email_verification_service.send_verification_email(
        user_id=user_id,
        base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
    )

    if success:
        return jsonify({"message": "Verification email sent"}), 200
    else:
        return jsonify({"error": "Failed to send email"}), 500


@admin_api_bp.route("/invitations", methods=["GET", "POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def manage_invitations():
    """List or create invitations (admin only)."""
    from vault.services.invitation_service import InvitationService
    from vault.blueprints.validators import validate_email

    if request.method == "GET":
        invited_by = request.args.get("invited_by", "").strip() or None
        status = request.args.get("status", "").strip() or None
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))

        invitation_service = InvitationService()
        result = invitation_service.list_invitations(
            invited_by=invited_by,
            status=status,
            page=page,
            per_page=per_page,
        )
        return jsonify(result), 200
    else:
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        email = data.get("email", "").strip()
        if not email:
            return jsonify({"error": "Email is required"}), 400

        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400

        invitation_service = InvitationService()
        # VAULT_URL from settings will be used automatically

        try:
            invitation = invitation_service.create_invitation(
                email=email,
                invited_by=user.id,
                base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
            )
            return jsonify({"invitation": invitation.to_dict()}), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/invitations/<invitation_id>/resend", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def resend_invitation(invitation_id: str):
    """Resend invitation email (admin only)."""
    from vault.services.invitation_service import InvitationService

    invitation_service = InvitationService()
    # VAULT_URL from settings will be used automatically
    success = invitation_service.resend_invitation(
        invitation_id=invitation_id,
        base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
    )

    if success:
        return jsonify({"message": "Invitation resent successfully"}), 200
    else:
        return jsonify({"error": "Failed to resend invitation"}), 400


@admin_api_bp.route("/invitations/<invitation_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def cancel_invitation(invitation_id: str):
    """Cancel an invitation (admin only)."""
    from vault.services.invitation_service import InvitationService

    invitation_service = InvitationService()
    success = invitation_service.cancel_invitation(invitation_id=invitation_id)

    if success:
        return jsonify({"message": "Invitation cancelled successfully"}), 200
    else:
        return jsonify({"error": "Failed to cancel invitation"}), 400


@admin_api_bp.route("/settings", methods=["GET", "PUT"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def manage_settings():
    """Get or update system settings (admin only)."""
    from vault.database.schema import SystemSettings

    if request.method == "GET":
        settings = db.session.query(SystemSettings).all()
        settings_dict = {s.key: s.value for s in settings}

        # Priority: database value > config value
        # If allow_signup is not in database, fall back to config
        vault_settings = current_app.config.get("VAULT_SETTINGS")
        if "allow_signup" not in settings_dict and vault_settings:
            settings_dict["allow_signup"] = str(vault_settings.allow_signup)
        # If allow_signup is in database, use database value (already in settings_dict)

        return jsonify({"settings": settings_dict}), 200
    else:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        # Update allow_signup in database (reference only - actual config requires .env update)
        allow_signup = data.get("allow_signup")
        if allow_signup is not None:
            setting = (
                db.session.query(SystemSettings).filter_by(key="allow_signup").first()
            )
            if setting:
                setting.value = str(allow_signup).lower()
            else:
                setting = SystemSettings(
                    key="allow_signup", value=str(allow_signup).lower()
                )
                db.session.add(setting)
            db.session.commit()

        return jsonify({"message": "Settings updated successfully"}), 200


@admin_api_bp.route("/sso-domains", methods=["GET", "POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def manage_sso_domains():
    """List or create SSO domain rules (admin only)."""
    from vault.services.sso_domain_service import SSODomainService

    if request.method == "GET":
        sso_domain_service = SSODomainService()
        rules = sso_domain_service.list_rules()
        return jsonify({"rules": [rule.to_dict() for rule in rules]}), 200
    else:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        domain_pattern = data.get("domain_pattern", "").strip()
        sso_provider_id = data.get("sso_provider_id", "").strip() or None
        is_active = data.get("is_active", True)

        if not domain_pattern:
            return jsonify({"error": "domain_pattern is required"}), 400

        sso_domain_service = SSODomainService()

        try:
            rule = sso_domain_service.create_rule(
                domain_pattern=domain_pattern,
                sso_provider_id=sso_provider_id,
                is_active=is_active,
            )
            return jsonify({"rule": rule.to_dict()}), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/sso-domains/<rule_id>", methods=["PUT", "DELETE"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def manage_sso_domain(rule_id: str):
    """Update or delete SSO domain rule (admin only)."""
    from vault.services.sso_domain_service import SSODomainService

    if request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        domain_pattern = data.get("domain_pattern", "").strip() or None
        sso_provider_id = data.get("sso_provider_id", "").strip() or None
        is_active = data.get("is_active")

        sso_domain_service = SSODomainService()

        try:
            rule = sso_domain_service.update_rule(
                rule_id=rule_id,
                domain_pattern=domain_pattern,
                sso_provider_id=sso_provider_id,
                is_active=is_active,
            )
            if not rule:
                return jsonify({"error": "Rule not found"}), 404

            return jsonify({"rule": rule.to_dict()}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    else:
        sso_domain_service = SSODomainService()
        success = sso_domain_service.delete_rule(rule_id=rule_id)

        if success:
            return jsonify({"message": "Rule deleted successfully"}), 200
        else:
            return jsonify({"error": "Rule not found"}), 404


# API Key management routes


@admin_api_bp.route("/api-keys", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def list_api_keys():
    """List all API keys (admin and superadmin only)."""
    from vault.services.api_key_service import ApiKeyService

    api_key_service = ApiKeyService()
    api_keys = api_key_service.list_all_api_keys()

    return (
        jsonify(
            {
                "api_keys": [key.to_dict() for key in api_keys],
            }
        ),
        200,
    )


@admin_api_bp.route("/api-keys", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def create_api_key():
    """Generate a new API key (admin and superadmin only).

    Request body:
        {
            "user_id": "user-uuid",
            "name": "API key name/description"
        }

    Returns:
        JSON with API key object and plaintext key (shown only once)
    """
    from vault.services.api_key_service import ApiKeyService

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    user_id = data.get("user_id", "").strip()
    name = data.get("name", "").strip()

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400

    api_key_service = ApiKeyService()

    try:
        api_key, plaintext_key = api_key_service.generate_api_key(
            user_id=user_id, name=name
        )
        return (
            jsonify(
                {
                    "api_key": api_key.to_dict(),
                    "key": plaintext_key,  # Show only once
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_api_bp.route("/api-keys/<key_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def revoke_api_key(key_id: str):
    """Revoke (delete) an API key (admin and superadmin only).

    This permanently deletes the API key from the database.
    """
    from vault.services.api_key_service import ApiKeyService

    api_key_service = ApiKeyService()

    try:
        api_key_service.revoke_api_key(key_id)
        return jsonify({"message": "API key revoked successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@admin_api_bp.route("/api-keys/user/<user_id>", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def list_user_api_keys(user_id: str):
    """List all API keys for a specific user (admin and superadmin only)."""
    from vault.services.api_key_service import ApiKeyService

    api_key_service = ApiKeyService()
    api_keys = api_key_service.list_user_api_keys(user_id)

    return (
        jsonify(
            {
                "api_keys": [key.to_dict() for key in api_keys],
            }
        ),
        200,
    )
