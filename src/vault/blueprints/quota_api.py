"""Quota API routes for Leyzen Vault."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from vault.middleware import get_current_user, jwt_required
from vault.services.quota_service import QuotaService

quota_api_bp = Blueprint("quota_api_v2", __name__, url_prefix="/api/v2/quota")


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


@quota_api_bp.route("", methods=["GET"])
@jwt_required
def get_quota():
    """Get quota information for the current user.

    Returns:
        JSON with quota information
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    quota_service = _get_quota_service()

    quota_info = quota_service.get_quota_info(user.id)

    return jsonify(quota_info), 200


@quota_api_bp.route("/check", methods=["POST"])
@jwt_required
def check_quota():
    """Check if user has enough quota for additional storage.

    Request body:
        {
            "additional_bytes": 1024 (optional, default: 0)
        }

    Returns:
        JSON with quota check result
    """
    from flask import request

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json() or {}
    additional_bytes = data.get("additional_bytes", 0)

    quota_service = _get_quota_service()
    has_quota, info = quota_service.check_user_quota(user.id, additional_bytes)

    return (
        jsonify(
            {
                "has_quota": has_quota,
                **info,
            }
        ),
        200 if has_quota else 403,
    )
