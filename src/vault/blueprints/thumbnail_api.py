"""Thumbnail API routes for Leyzen Vault."""

from __future__ import annotations

import json
from flask import Blueprint, Response, current_app, jsonify, request

from vault.database.schema import db
from vault.middleware import get_current_user, jwt_required
from vault.services.file_service import AdvancedFileService
from vault.services.thumbnail_service import ThumbnailService

thumbnail_api_bp = Blueprint("thumbnail_api", __name__, url_prefix="/api/v2/thumbnails")


def _get_file_service() -> AdvancedFileService:
    """Get AdvancedFileService instance."""
    return AdvancedFileService()


def _get_thumbnail_service() -> ThumbnailService:
    """Get ThumbnailService instance."""
    storage = current_app.config.get("VAULT_STORAGE")
    return ThumbnailService(storage=storage)


@thumbnail_api_bp.route("/<file_id>", methods=["GET"])
@jwt_required
def get_thumbnail(file_id: str):
    """Get thumbnail for a file.

    Query parameters:
        - size: Thumbnail size (64x64, 128x128, 256x256) - default: 256x256

    Returns:
        Thumbnail image (JPEG)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    size_str = request.args.get("size", "256x256")
    try:
        size = tuple(map(int, size_str.split("x")))
        if len(size) != 2:
            raise ValueError("Invalid size format")
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid size format. Use format: WIDTHxHEIGHT"}), 400

    file_service = _get_file_service()
    thumbnail_service = _get_thumbnail_service()

    try:
        # Check if user has access to file
        file_obj, permissions = file_service.get_file_with_permissions(file_id, user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        # Check if user has read permission
        has_permission = False
        if file_obj.owner_user_id == user.id:
            has_permission = True
        elif permissions:
            has_permission = True

        if not has_permission:
            return jsonify({"error": "Permission denied"}), 403

        # Get thumbnail from storage (if it exists)
        thumbnail_data = thumbnail_service.get_thumbnail(file_id, size)
        if not thumbnail_data:
            return jsonify({"error": "Thumbnail not found"}), 404

        return Response(
            thumbnail_data,
            mimetype="image/jpeg",
            headers={"Cache-Control": "public, max-age=31536000"},  # Cache for 1 year
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@thumbnail_api_bp.route("/<file_id>/generate", methods=["POST"])
@jwt_required
def generate_thumbnail(file_id: str):
    """Generate thumbnail for a file (requires decrypted file data).

    Request body:
        {
            "file_data": "base64_encoded_decrypted_file_data" (optional, if not provided, will fetch from storage)
        }

    Returns:
        JSON with thumbnail storage references
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()
    thumbnail_service = _get_thumbnail_service()
    current_app.config.get("VAULT_STORAGE")

    try:
        # Check if user has access to file
        file_obj, permissions = file_service.get_file_with_permissions(file_id, user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        # Check if user has read permission
        has_permission = False
        if file_obj.owner_user_id == user.id:
            has_permission = True
        elif permissions:
            has_permission = True

        if not has_permission:
            return jsonify({"error": "Permission denied"}), 403

        # Get file data (decrypted)
        data = request.get_json() or {}
        file_data_b64 = data.get("file_data")

        if file_data_b64:
            import base64

            file_data = base64.b64decode(file_data_b64)
        else:
            # Fetch encrypted file from storage and decrypt
            # Note: In production, this would require the file key
            # For now, we'll require file_data to be provided
            return jsonify({"error": "file_data required"}), 400

        # Detect actual MIME type from file data
        detected_mime_type = file_obj.mime_type
        if not detected_mime_type or detected_mime_type == "application/octet-stream":
            # Try to detect image type from file data using PIL
            try:
                from PIL import Image
                import io

                image = Image.open(io.BytesIO(file_data))
                # PIL can detect format, map to MIME type
                format_to_mime = {
                    "PNG": "image/png",
                    "JPEG": "image/jpeg",
                    "GIF": "image/gif",
                    "WEBP": "image/webp",
                    "BMP": "image/bmp",
                    "TIFF": "image/tiff",
                    "ICO": "image/x-icon",
                }
                detected_mime_type = format_to_mime.get(
                    image.format, detected_mime_type
                )
            except Exception:
                # If PIL can't open it, it's not an image
                pass

        # Only generate thumbnails for images
        if not detected_mime_type or not detected_mime_type.startswith("image/"):
            return jsonify({"error": "Thumbnails only available for images"}), 400

        # Generate thumbnails
        thumbnails = thumbnail_service.generate_and_save_thumbnails(
            file_id, file_data, detected_mime_type
        )

        if not thumbnails:
            return jsonify({"error": "Failed to generate thumbnails"}), 500

        # Update file record with thumbnail references
        file_obj.thumbnail_refs = json.dumps(thumbnails)
        file_obj.has_thumbnail = True
        db.session.commit()

        return (
            jsonify(
                {
                    "thumbnails": thumbnails,
                    "has_thumbnail": True,
                }
            ),
            201,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@thumbnail_api_bp.route("/<file_id>", methods=["DELETE"])
@jwt_required
def delete_thumbnail(file_id: str):
    """Delete thumbnails for a file.

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()
    thumbnail_service = _get_thumbnail_service()

    try:
        # Check if user has permission (must be owner or admin)
        file_obj, _ = file_service.get_file_with_permissions(file_id, user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        if file_obj.owner_user_id != user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Delete thumbnails
        thumbnail_service.delete_thumbnails(file_id)

        # Update file record
        file_obj.thumbnail_refs = None
        file_obj.has_thumbnail = False
        db.session.commit()

        return jsonify({"message": "Thumbnails deleted successfully"}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 403
