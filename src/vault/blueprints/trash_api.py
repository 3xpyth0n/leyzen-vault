"""Trash API blueprint for managing deleted files."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.file_service import AdvancedFileService

trash_api_bp = Blueprint("trash_api", __name__, url_prefix="/api/v2/trash")


def _get_file_service() -> AdvancedFileService:
    return AdvancedFileService()


@trash_api_bp.route("", methods=["GET"])
@jwt_required
def list_trash():
    """List all deleted files (trash).

    Query parameters:
        - vaultspace_id: Optional VaultSpace ID filter

    Returns:
        JSON with list of deleted files
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")

    file_service = _get_file_service()
    try:
        trash_files = file_service.list_trash_files(
            vaultspace_id=vaultspace_id,
            user_id=user.id,
        )
        return (
            jsonify(
                {
                    "files": [f.to_dict() for f in trash_files],
                    "total": len(trash_files),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trash_api_bp.route("/<file_id>/restore", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def restore_file(file_id: str):
    """Restore a deleted file from trash.

    Args:
        file_id: File ID

    Returns:
        JSON with restored file info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()
    try:
        restored_file = file_service.restore_file(file_id, user.id)
        if not restored_file:
            return jsonify({"error": "File not found"}), 404
        return (
            jsonify(
                {
                    "file": restored_file.to_dict(),
                    "message": "File restored successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@trash_api_bp.route("/<file_id>/permanent", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def permanently_delete_file(file_id: str):
    """Permanently delete a file from trash (cannot be undone).

    Args:
        file_id: File ID

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()
    try:
        # Service now handles BOTH database AND physical file deletion
        success = file_service.permanently_delete_file(file_id, user.id)
        if not success:
            return jsonify({"error": "File not found"}), 404

        return (
            jsonify(
                {
                    "message": "File permanently deleted",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 403
