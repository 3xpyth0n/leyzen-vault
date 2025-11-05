"""File upload/download API endpoints and file explorer."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from ..extensions import csrf
from ..models import FileDatabase, FileMetadata
from ..services.audit import AuditService
from ..services.rate_limiter import RateLimiter
from ..services.share_service import ShareService
from ..storage import FileStorage
from .utils import get_client_ip, login_required

files_bp = Blueprint("files", __name__)


@files_bp.route("/", strict_slashes=False)
@login_required
def index():
    """Serve the main file explorer interface."""
    return render_template("files.html")


def _get_storage() -> FileStorage:
    """Get the file storage instance from Flask config."""
    return current_app.config["VAULT_STORAGE"]


def _get_database() -> FileDatabase:
    """Get the file database instance from Flask config."""
    return current_app.config["VAULT_DATABASE"]


def _get_audit() -> AuditService:
    """Get the audit service instance from Flask config."""
    return current_app.config["VAULT_AUDIT"]


def _get_share_service() -> ShareService:
    """Get the share service instance from Flask config."""
    return current_app.config["VAULT_SHARE"]


def _get_rate_limiter() -> RateLimiter:
    """Get the rate limiter instance from Flask config."""
    return current_app.config["VAULT_RATE_LIMITER"]


@files_bp.route("/api/files", methods=["POST"])
@login_required
def upload_file():
    """Upload an encrypted file."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    rate_limiter = _get_rate_limiter()
    settings = current_app.config.get("VAULT_SETTINGS")

    # Check rate limit
    is_allowed, rate_limit_error = rate_limiter.check_rate_limit(user_ip)
    if not is_allowed:
        audit.log_action(
            "upload",
            user_ip,
            {"error": "rate_limit_exceeded", "message": rate_limit_error},
            False,
        )
        return jsonify({"error": rate_limit_error}), 429

    if "file" not in request.files:
        audit.log_action(
            "upload",
            user_ip,
            {"error": "No file provided"},
            False,
        )
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        audit.log_action(
            "upload",
            user_ip,
            {"error": "Empty filename"},
            False,
        )
        return jsonify({"error": "Empty filename"}), 400

    original_name = file.filename or "unnamed"

    # Read encrypted file data
    encrypted_data = file.read()
    if not encrypted_data:
        audit.log_action(
            "upload",
            user_ip,
            {"error": "Empty file", "filename": original_name},
            False,
        )
        return jsonify({"error": "Empty file"}), 400

    # Check file size limit
    if settings:
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        original_size = request.form.get("original_size")
        if original_size:
            try:
                original_size = int(original_size)
                if original_size > max_size_bytes:
                    audit.log_action(
                        "upload",
                        user_ip,
                        {
                            "error": "file_too_large",
                            "filename": original_name,
                            "size": original_size,
                            "max_size": max_size_bytes,
                        },
                        False,
                    )
                    return (
                        jsonify(
                            {
                                "error": f"File too large: maximum {settings.max_file_size_mb}MB allowed"
                            }
                        ),
                        413,
                    )
            except ValueError:
                pass

        # Also check encrypted size as fallback
        if len(encrypted_data) > max_size_bytes:
            audit.log_action(
                "upload",
                user_ip,
                {
                    "error": "encrypted_file_too_large",
                    "filename": original_name,
                    "encrypted_size": len(encrypted_data),
                    "max_size": max_size_bytes,
                },
                False,
            )
            return (
                jsonify(
                    {
                        "error": f"File too large: maximum {settings.max_file_size_mb}MB allowed"
                    }
                ),
                413,
            )

    storage = _get_storage()
    database = _get_database()

    # Generate file ID
    file_id = storage.generate_file_id()

    # Compute hash of encrypted data
    encrypted_hash = storage.compute_hash(encrypted_data)

    # Save encrypted file
    storage.save_file(file_id, encrypted_data)

    # Get original size from request if provided, otherwise use encrypted size
    # Note: The client should send the original size in a header or form field
    original_size = request.form.get("original_size")
    if original_size:
        try:
            original_size = int(original_size)
        except ValueError:
            original_size = len(encrypted_data)
    else:
        original_size = len(encrypted_data)  # Fallback

    # Store metadata
    settings = current_app.config.get("VAULT_SETTINGS")
    # Use timezone-aware datetime with configured timezone
    if settings:
        from zoneinfo import ZoneInfo

        current_time = datetime.now(settings.timezone)
    else:
        current_time = datetime.now()

    metadata = FileMetadata(
        file_id=file_id,
        original_name=original_name,
        size=original_size,
        encrypted_size=len(encrypted_data),
        created_at=current_time,
        encrypted_hash=encrypted_hash,
    )
    database.add_file(metadata)

    # Log successful upload
    audit.log_action(
        "upload",
        user_ip,
        {
            "file_id": file_id,
            "filename": original_name,
            "size": original_size,
            "encrypted_size": len(encrypted_data),
            "hash": encrypted_hash,
        },
        True,
        file_id=file_id,
    )

    return jsonify({"file_id": file_id, "status": "success"}), 201


@files_bp.route("/api/files/<file_id>", methods=["GET"])
def download_file(file_id: str):
    # Note: No @login_required to allow sharing via /share page
    """Download an encrypted file."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    share_service = _get_share_service()

    database = _get_database()
    storage = _get_storage()

    # Check if this is a share link download
    link_token = request.args.get("token")
    if link_token:
        is_valid, error_msg = share_service.validate_share_link(link_token)
        if not is_valid:
            audit.log_action(
                "download",
                user_ip,
                {
                    "error": error_msg or "Invalid share link",
                    "file_id": file_id,
                    "link_token": link_token,
                },
                False,
                file_id=file_id,
            )
            return jsonify({"error": error_msg or "Invalid share link"}), 403

        # Verify the link is for this file
        share_link = share_service.get_share_link(link_token)
        if share_link and share_link.file_id != file_id:
            audit.log_action(
                "download",
                user_ip,
                {
                    "error": "Share link file mismatch",
                    "file_id": file_id,
                    "link_token": link_token,
                },
                False,
                file_id=file_id,
            )
            return jsonify({"error": "Share link file mismatch"}), 403

        # Increment download count
        if share_link:
            share_service.increment_download_count(link_token)

            # Check if limit reached after increment
            updated_link = share_service.get_share_link(link_token)
            if updated_link and updated_link.has_reached_limit():
                share_service.deactivate_link(link_token)

    metadata = database.get_file(file_id)
    if not metadata:
        audit.log_action(
            "download",
            user_ip,
            {"error": "File not found", "file_id": file_id},
            False,
            file_id=file_id,
        )
        return jsonify({"error": "File not found"}), 404

    if not storage.file_exists(file_id):
        audit.log_action(
            "download",
            user_ip,
            {"error": "File data not found", "file_id": file_id},
            False,
            file_id=file_id,
        )
        return jsonify({"error": "File data not found"}), 404

    # Log successful download
    audit.log_action(
        "download",
        user_ip,
        {
            "file_id": file_id,
            "filename": metadata.original_name,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "via_share_link": bool(link_token),
        },
        True,
        file_id=file_id,
    )

    file_path = storage.get_file_path(file_id)
    return send_file(
        file_path,
        mimetype="application/octet-stream",
        download_name=metadata.original_name,
    )


@files_bp.route("/api/files", methods=["GET"])
@login_required
def list_files():
    """List all files (metadata only)."""
    database = _get_database()
    files = database.list_files()
    return jsonify({"files": [f.to_dict() for f in files]}), 200


@files_bp.route("/api/files/<file_id>/share", methods=["POST"])
@login_required
def create_share_link(file_id: str):
    """Create a share link for a file."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    share_service = _get_share_service()
    database = _get_database()

    # Verify file exists
    metadata = database.get_file(file_id)
    if not metadata:
        audit.log_action(
            "share",
            user_ip,
            {"error": "File not found", "file_id": file_id},
            False,
            file_id=file_id,
        )
        return jsonify({"error": "File not found"}), 404

    # Get parameters from request
    expires_in_hours = request.json.get("expires_in_hours") if request.is_json else None
    max_downloads = request.json.get("max_downloads") if request.is_json else None

    if expires_in_hours:
        try:
            expires_in_hours = int(expires_in_hours)
            if expires_in_hours < 1:
                expires_in_hours = None
        except (ValueError, TypeError):
            expires_in_hours = None

    if max_downloads:
        try:
            max_downloads = int(max_downloads)
            if max_downloads < 1:
                max_downloads = None
        except (ValueError, TypeError):
            max_downloads = None

    # Create share link
    share_link = share_service.create_share_link(
        file_id=file_id,
        expires_in_hours=expires_in_hours,
        max_downloads=max_downloads,
    )

    # Log successful share link creation
    audit.log_action(
        "share",
        user_ip,
        {
            "file_id": file_id,
            "link_id": share_link.link_id,
            "expires_in_hours": expires_in_hours,
            "max_downloads": max_downloads,
        },
        True,
        file_id=file_id,
    )

    return jsonify(share_link.to_dict()), 201


@files_bp.route("/api/files/<file_id>/shares", methods=["GET"])
@login_required
def list_share_links(file_id: str):
    """List all share links for a file."""
    share_service = _get_share_service()
    database = _get_database()

    # Verify file exists
    if not database.get_file(file_id):
        return jsonify({"error": "File not found"}), 404

    links = share_service.list_links_for_file(file_id)
    return jsonify({"links": [link.to_dict() for link in links]}), 200


@files_bp.route("/api/shares/<link_token>", methods=["GET"])
def get_share_link_info(link_token: str):
    """Get information about a share link."""
    share_service = _get_share_service()
    share_link = share_service.get_share_link(link_token)

    if not share_link:
        return jsonify({"error": "Share link not found"}), 404

    is_valid, error_msg = share_service.validate_share_link(link_token)

    return (
        jsonify(
            {
                **share_link.to_dict(),
                "is_valid": is_valid,
                "error": error_msg,
            }
        ),
        200,
    )


@files_bp.route("/api/files/<file_id>", methods=["DELETE"])
@login_required
def delete_file(file_id: str):
    """Delete a file."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    database = _get_database()
    storage = _get_storage()

    metadata = database.get_file(file_id)
    if not metadata:
        audit.log_action(
            "delete",
            user_ip,
            {"error": "File not found", "file_id": file_id},
            False,
            file_id=file_id,
        )
        return jsonify({"error": "File not found"}), 404

    deleted = database.delete_file(file_id)
    storage.delete_file(file_id)

    if deleted:
        # Log successful deletion
        audit.log_action(
            "delete",
            user_ip,
            {
                "file_id": file_id,
                "filename": metadata.original_name,
            },
            True,
            file_id=file_id,
        )
        return jsonify({"status": "success"}), 200

    audit.log_action(
        "delete",
        user_ip,
        {"error": "Failed to delete", "file_id": file_id},
        False,
        file_id=file_id,
    )
    return jsonify({"error": "Failed to delete"}), 500


__all__ = ["files_bp"]
