"""File versioning API v2 routes with JWT authentication."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.file_service import AdvancedFileService
from vault.services.version_service import VersionService

versions_api_bp = Blueprint("versions_api", __name__, url_prefix="/api/v2/versions")


def _get_version_service() -> VersionService:
    """Get VersionService instance."""
    return VersionService()


def _get_file_service() -> AdvancedFileService:
    """Get AdvancedFileService instance."""
    return AdvancedFileService()


@versions_api_bp.route("/files/<file_id>", methods=["GET"])
@jwt_required
def get_version_history(file_id: str):
    """Get version history for a file.

    Query parameters:
        - branch_name: Branch name (default: "main")
        - limit: Maximum results (default: 50)
        - offset: Offset for pagination (default: 0)

    Returns:
        JSON with version history
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    version_service = _get_version_service()

    branch_name = request.args.get("branch_name", "main")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    try:
        history = version_service.get_version_history(
            file_id=file_id,
            branch_name=branch_name,
            limit=limit,
            offset=offset,
        )
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@versions_api_bp.route("/<version_id>", methods=["GET"])
@jwt_required
def get_version(version_id: str):
    """Get a specific version by ID.

    Returns:
        JSON with version details
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    version_service = _get_version_service()

    try:
        version = version_service.get_version(version_id)
        if not version:
            return jsonify({"error": "Version not found"}), 404

        return jsonify({"version": version.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@versions_api_bp.route("/files/<file_id>/restore", methods=["POST"])
@jwt_required
def restore_version(file_id: str):
    """Restore a file to a previous version.

    Request body:
        {
            "version_id": "version-uuid"
        }

    Returns:
        JSON with updated file info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    version_id = data.get("version_id")
    if not version_id:
        return jsonify({"error": "version_id is required"}), 400

    version_service = _get_version_service()

    try:
        file_obj = version_service.restore_version(
            file_id=file_id,
            version_id=version_id,
            restored_by=user.id,
        )
        return jsonify({"file": file_obj.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@versions_api_bp.route("/compare", methods=["POST"])
@jwt_required
def compare_versions():
    """Compare two versions.

    Request body:
        {
            "version1_id": "version-uuid",
            "version2_id": "version-uuid"
        }

    Returns:
        JSON with comparison results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    version1_id = data.get("version1_id")
    version2_id = data.get("version2_id")

    if not version1_id or not version2_id:
        return jsonify({"error": "version1_id and version2_id are required"}), 400

    version_service = _get_version_service()

    try:
        comparison = version_service.compare_versions(
            version1_id=version1_id,
            version2_id=version2_id,
        )
        return jsonify(comparison), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@versions_api_bp.route("/files/<file_id>/cleanup", methods=["POST"])
@jwt_required
def cleanup_versions(file_id: str):
    """Clean up old versions, keeping only the most recent ones.

    Request body:
        {
            "keep_count": 10 (optional, default: 10),
            "branch_name": "main" (optional, default: "main")
        }

    Returns:
        JSON with cleanup results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json() or {}
    keep_count = int(data.get("keep_count", 10))
    branch_name = data.get("branch_name", "main")

    version_service = _get_version_service()

    try:
        deleted_count = version_service.cleanup_old_versions(
            file_id=file_id,
            keep_count=keep_count,
            branch_name=branch_name,
        )
        return jsonify({"deleted_count": deleted_count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
