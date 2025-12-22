"""Quota management API routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from vault.database.schema import GlobalRole
from vault.middleware import get_current_user, jwt_required, require_role
from vault.services.quota_service import QuotaService

quota_api_bp = Blueprint("quota_api", __name__, url_prefix="/api/quotas")


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


@quota_api_bp.route("/me", methods=["GET"])
@jwt_required
def get_my_quota():
    """Get current user's quota."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    quota_service = _get_quota_service()
    quota_info = quota_service.get_quota_info(user_id=user.id)

    return (
        jsonify(
            {
                "quota": quota_info,
            }
        ),
        200,
    )


@quota_api_bp.route("", methods=["POST"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def create_quota():
    """Create or update quota (admin only)."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    user_id = data.get("user_id")
    max_storage_bytes = data.get("max_storage_bytes")
    data.get("max_files")

    if not max_storage_bytes:
        return jsonify({"error": "max_storage_bytes is required"}), 400

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    quota_service = _get_quota_service()

    try:
        quota = quota_service.create_or_update_user_quota(
            user_id=user_id,
            storage_limit_bytes=max_storage_bytes,
        )
        return (
            jsonify(
                {
                    "quota": quota.to_dict(),
                }
            ),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
