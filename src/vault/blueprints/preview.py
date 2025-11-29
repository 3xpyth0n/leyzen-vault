"""Preview API endpoints for file thumbnails and previews."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, send_file
from pathlib import Path

from ..storage import FileStorage
from ..services.preview import PreviewService
from ..middleware.jwt_auth import jwt_required
from ..utils.mime_type_detection import detect_mime_type_from_extension
from .utils import get_client_ip

preview_bp = Blueprint("preview", __name__)


def _get_storage() -> FileStorage:
    """Get the file storage instance from Flask config."""
    return current_app.config["VAULT_STORAGE"]


def _get_preview_service() -> PreviewService:
    """Get the preview service instance from Flask config."""
    if "VAULT_PREVIEW" not in current_app.config:
        storage = _get_storage()
        preview_service = PreviewService(storage.storage_dir)
        current_app.config["VAULT_PREVIEW"] = preview_service
    return current_app.config["VAULT_PREVIEW"]


@preview_bp.route("/api/files/<file_id>/thumbnail", methods=["GET"])
@jwt_required
def get_thumbnail(file_id: str):
    """Get thumbnail for a file."""
    from vault.database.schema import File, db

    preview_service = _get_preview_service()

    # Verify file exists
    file_obj = db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
    if not file_obj:
        return jsonify({"error": "File not found"}), 404

    # Check if thumbnail exists
    thumbnail_data = preview_service.get_thumbnail(file_id)
    if not thumbnail_data:
        return jsonify({"error": "Thumbnail not available"}), 404

    # Return thumbnail
    thumbnail_path = preview_service.get_thumbnail_path(file_id)
    return send_file(
        thumbnail_path,
        mimetype="image/jpeg",
        download_name=f"{file_id}_thumb.jpg",
    )


@preview_bp.route("/api/files/<file_id>/preview", methods=["GET"])
@jwt_required
def get_preview(file_id: str):
    """Get preview information for a file."""
    from vault.database.schema import File, db

    preview_service = _get_preview_service()

    # Verify file exists
    file_obj = db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
    if not file_obj:
        return jsonify({"error": "File not found"}), 404

    mime_type = file_obj.mime_type or ""

    # If mime type is generic, try to detect from extension
    generic_mime_types = [
        "application/octet-stream",
        "application/x-unknown",
        "binary/octet-stream",
    ]
    if mime_type in generic_mime_types and file_obj.original_name:
        detected_mime = detect_mime_type_from_extension(file_obj.original_name)
        if detected_mime and detected_mime not in generic_mime_types:
            mime_type = detected_mime

    # Check if thumbnail exists
    has_thumbnail = preview_service.thumbnail_exists(file_id)

    # Determine preview availability based on MIME type
    preview_available = False
    preview_type = "unsupported"

    if mime_type.startswith("image/"):
        preview_available = True
        preview_type = "image"
    elif mime_type == "application/pdf":
        preview_available = True
        preview_type = "pdf"
    elif mime_type.startswith("video/"):
        preview_available = True
        preview_type = "video"
    elif mime_type.startswith("audio/"):
        preview_available = True
        preview_type = "audio"
    elif (
        mime_type.startswith("text/")
        or mime_type == "application/json"
        or mime_type == "application/xml"
        or "javascript" in mime_type
        or "css" in mime_type
        or "html" in mime_type
    ):
        preview_available = True
        preview_type = "text"

    return (
        jsonify(
            {
                "file_id": file_id,
                "mime_type": mime_type,
                "has_thumbnail": has_thumbnail,
                "preview_available": preview_available,
                "preview_type": preview_type,
            }
        ),
        200,
    )


__all__ = ["preview_bp"]
