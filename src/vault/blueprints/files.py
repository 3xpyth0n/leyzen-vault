"""File upload/download API endpoints and file explorer."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from vault.middleware import get_current_user, jwt_required
from ..models import FileMetadata
from ..services.audit import AuditService
from ..services.rate_limiter import RateLimiter
from ..services.share_link_service import ShareService
from ..storage import FileStorage
from .utils import get_client_ip

files_bp = Blueprint("files", __name__)

# All frontend routes are handled by Vue.js SPA
# Only API routes remain here


def _get_storage() -> FileStorage:
    """Get the file storage instance from Flask config."""
    return current_app.config["VAULT_STORAGE"]


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
@jwt_required
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

    # Validate and normalize filename using common validation utility
    from vault.utils.file_validation import validate_filename

    is_valid, validation_error = validate_filename(original_name)
    if not is_valid:
        audit.log_action(
            "upload",
            user_ip,
            {
                "error": "invalid_filename",
                "message": validation_error,
                "filename": original_name,
            },
            False,
        )
        return jsonify({"error": validation_error or "Invalid filename"}), 400

    # Normalize filename (collapse spaces)
    original_name = re.sub(r"\s+", " ", original_name.strip())

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
    # SECURITY: Always use actual encrypted data size, never trust client-provided size
    if settings:
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        encrypted_size = len(encrypted_data)

        # Validate encrypted size first (this is what we actually store)
        if encrypted_size > max_size_bytes:
            audit.log_action(
                "upload",
                user_ip,
                {
                    "error": "encrypted_file_too_large",
                    "filename": original_name,
                    "encrypted_size": encrypted_size,
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

        # If original_size is provided, validate it for consistency but don't trust it
        # This helps detect potential client-side issues or attacks
        original_size_param = request.form.get("original_size")
        if original_size_param:
            try:
                declared_original_size = int(original_size_param)
                # Encrypted data should be larger than original (due to encryption overhead)
                # But not suspiciously larger (allow up to 2x for encryption overhead)
                if declared_original_size > encrypted_size * 2:
                    current_app.logger.warning(
                        f"Suspicious original_size declared: {declared_original_size} "
                        f"vs encrypted_size: {encrypted_size} for file {original_name}"
                    )
                    # Don't block, but log for investigation
            except ValueError:
                # Invalid original_size format, ignore
                pass

    storage = _get_storage()

    # Generate file ID
    file_id = storage.generate_file_id()

    # Compute hash of encrypted data
    encrypted_hash = storage.compute_hash(encrypted_data)

    # Save encrypted file with integrity verification
    try:
        storage.save_file(file_id, encrypted_data)
    except IOError as e:
        from .utils import safe_error_response

        current_app.logger.error(f"Failed to save file {file_id}: {type(e).__name__}")
        audit.log_action(
            "upload",
            user_ip,
            {"error": "Storage error", "filename": original_name},
            False,
        )
        return safe_error_response("internal_error", 500, str(e))

    # Determine original size for metadata
    # SECURITY: Use encrypted size as authoritative, but try to get declared original size
    # for display purposes (already validated above for consistency)
    encrypted_size = len(encrypted_data)
    original_size = encrypted_size  # Default to encrypted size

    original_size_param = request.form.get("original_size")
    if original_size_param:
        try:
            declared_size = int(original_size_param)
            # Only use declared size if it's reasonable (not larger than encrypted size)
            # Encrypted data should be larger due to encryption overhead
            if declared_size <= encrypted_size:
                original_size = declared_size
        except ValueError:
            # Invalid format, use encrypted size
            pass

    # Get folder_id (parent_id) from form data if provided
    parent_id = request.form.get("folder_id")
    if parent_id == "":
        parent_id = None

    # Get vaultspace_id from form data (required)
    vaultspace_id = request.form.get("vaultspace_id")
    if not vaultspace_id:
        audit.log_action(
            "upload",
            user_ip,
            {"error": "vaultspace_id is required"},
            False,
        )
        return jsonify({"error": "vaultspace_id is required"}), 400

    # Validate parent_id if provided (must be a folder)
    if parent_id is not None:
        from vault.database.schema import File, db

        folder = (
            db.session.query(File)
            .filter_by(
                id=parent_id, mime_type="application/x-directory", deleted_at=None
            )
            .first()
        )
        if folder is None:
            audit.log_action(
                "upload",
                user_ip,
                {"error": f"Folder {parent_id} not found"},
                False,
            )
            return jsonify({"error": "Folder not found"}), 404

    # Get optional metadata
    mime_type = request.form.get("mime_type")
    encrypted_tags = request.form.get("encrypted_tags")
    encrypted_description = request.form.get("encrypted_description")

    # Store metadata in PostgreSQL
    from vault.database.schema import File, db

    settings = current_app.config.get("VAULT_SETTINGS")
    # Use timezone-aware datetime with configured timezone
    if settings:
        from zoneinfo import ZoneInfo

        current_time = datetime.now(settings.timezone)
    else:
        current_time = datetime.now(timezone.utc)

    # Get current user ID
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    current_user_id = user.id

    # Check for duplicate names in the same folder
    existing_file = (
        db.session.query(File)
        .filter_by(
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            original_name=original_name,
        )
        .filter(File.deleted_at.is_(None))
        .first()
    )
    if existing_file:
        audit.log_action(
            "upload",
            user_ip,
            {
                "error": "duplicate_filename",
                "filename": original_name,
                "folder_id": parent_id,
            },
            False,
        )
        return (
            jsonify(
                {
                    "error": f"A file with the name '{original_name}' already exists in this folder"
                }
            ),
            409,
        )

    # Create File object in PostgreSQL
    file_obj = File(
        id=file_id,
        vaultspace_id=vaultspace_id,
        parent_id=parent_id,
        owner_user_id=current_user_id,
        original_name=original_name,
        size=original_size,
        encrypted_size=len(encrypted_data),
        encrypted_hash=encrypted_hash,
        encrypted_metadata=encrypted_description,  # Store description in metadata
        storage_ref=file_id,  # Use file_id as storage_ref
        mime_type=mime_type,
        created_at=current_time,
        updated_at=current_time,
    )
    db.session.add(file_obj)
    db.session.commit()

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

    # Promote file to persistent storage with validation
    # This ensures the file is persisted even without orchestrator
    # Validation checks that file exists in DB and hash matches
    try:
        from common.services.file_promotion_service import FilePromotionService
        from common.services.sync_validation_service import SyncValidationService
        from vault.database.schema import File

        # Initialize validation service with database
        validation_service = SyncValidationService(
            db_session=db.session, File_model=File, logger=current_app.logger
        )
        promotion_service = FilePromotionService(
            validation_service=validation_service, logger_instance=current_app.logger
        )

        # Get file path in tmpfs
        source_path = storage.get_file_path(file_id)
        target_dir = storage.source_dir

        if source_path.exists() and target_dir:
            success, error_msg = promotion_service.promote_file(
                file_id=file_id,
                source_path=source_path,
                target_dir=target_dir,
                base_dir=storage.storage_dir / "files",
            )

            if not success:
                # Log warning but don't fail the upload - file is already in cache
                current_app.logger.warning(
                    f"[PROMOTION] Failed to promote file {file_id}: {error_msg}"
                )
    except Exception as e:
        # Log error but don't fail the upload - file is already in cache
        current_app.logger.error(
            f"[PROMOTION ERROR] Failed to promote file {file_id}: {e}",
            exc_info=True,
        )

    return jsonify({"file_id": file_id, "status": "success"}), 201


# Share routes - separated from /api/files to avoid route conflicts
@files_bp.route("/api/share/<file_id>", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
def create_share_link(file_id: str):
    """Create a share link for a file."""
    # Import traceback here to avoid importing at module level if not needed (only used in error handling)
    import traceback

    try:
        # JWT authentication check
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Invalid authorization header format"}), 401

        token = parts[1]
        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            current_app.logger.error("SECRET_KEY not found in config")
            return jsonify({"error": "Server configuration error"}), 500

        from vault.services.auth_service import AuthService

        auth_service = AuthService(secret_key)
        user = auth_service.verify_token(token)

        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_ip = get_client_ip() or "unknown"
        audit = _get_audit()
        share_service = _get_share_service()

        # Verify file exists in PostgreSQL
        metadata = None
        try:
            from vault.database.schema import File, db

            file_obj = (
                db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
            )
            if file_obj:
                # Convert File to FileMetadata-like object
                from vault.models import FileMetadata

                metadata = FileMetadata(
                    file_id=file_obj.id,
                    original_name=file_obj.original_name,
                    size=file_obj.size,
                    encrypted_size=file_obj.encrypted_size,
                    created_at=file_obj.created_at,
                    encrypted_hash=file_obj.encrypted_hash,
                    folder_id=file_obj.parent_id,
                    encrypted_tags=None,
                    encrypted_description=None,
                    mime_type=file_obj.mime_type,
                    thumbnail_hash=None,
                    user_id=file_obj.owner_user_id,
                )
        except Exception as e:
            current_app.logger.error(
                f"Error querying database for file {file_id}: {type(e).__name__}"
            )
            return jsonify({"error": "Internal server error"}), 500

        if not metadata:
            audit.log_action(
                "share",
                user_ip,
                {"error": "File not found"},
                False,
                file_id=file_id,
            )
            return jsonify({"error": "File not found"}), 404

        # Get parameters from request
        expires_in_hours = None
        max_downloads = None
        try:
            if request.is_json and request.get_json():
                request_json = request.get_json()
                expires_in_hours = request_json.get("expires_in_hours")
                max_downloads = request_json.get("max_downloads")
        except Exception:
            pass

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
        try:
            share_link = share_service.create_share_link(
                file_id=file_id,
                expires_in_hours=expires_in_hours,
                max_downloads=max_downloads,
            )
        except Exception as e:
            current_app.logger.error(
                f"Error creating share link for file {file_id}: {type(e).__name__}"
            )
            return jsonify({"error": "Internal server error"}), 500

        # Log successful share link creation
        audit.log_action(
            "share",
            user_ip,
            {
                "file_id": file_id,
                "link_id": share_link.link_id if share_link else None,
                "expires_in_hours": expires_in_hours,
                "max_downloads": max_downloads,
            },
            True,
            file_id=file_id,
        )

        # Get share URL using VAULT_URL from settings
        share_url = share_service.get_share_url(share_link.link_id, share_link.file_id)
        share_link_dict = share_link.to_dict(share_url=share_url)
        return jsonify(share_link_dict), 201
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error in create_share_link: {type(e).__name__}"
        )
        current_app.logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500


@files_bp.route("/api/share/<file_id>/links", methods=["GET"])
@csrf.exempt  # JWT-authenticated API endpoint (GET but has side effects)
def list_share_links(file_id: str):
    """List all share links for a file."""
    # Import traceback here to avoid importing at module level if not needed (only used in error handling)
    import traceback

    try:
        # JWT authentication check
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Invalid authorization header format"}), 401

        token = parts[1]
        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            current_app.logger.error("SECRET_KEY not found in config")
            return jsonify({"error": "Server configuration error"}), 500

        from vault.services.auth_service import AuthService

        auth_service = AuthService(secret_key)
        user = auth_service.verify_token(token)

        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        share_service = _get_share_service()

        # Verify file exists in PostgreSQL
        file_metadata = None
        try:
            from vault.database.schema import File, db

            file_obj = (
                db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
            )
            if file_obj:
                # Convert File to FileMetadata-like object
                from vault.models import FileMetadata

                file_metadata = FileMetadata(
                    file_id=file_obj.id,
                    original_name=file_obj.original_name,
                    size=file_obj.size,
                    encrypted_size=file_obj.encrypted_size,
                    created_at=file_obj.created_at,
                    encrypted_hash=file_obj.encrypted_hash,
                    folder_id=file_obj.parent_id,
                    encrypted_tags=None,
                    encrypted_description=None,
                    mime_type=file_obj.mime_type,
                    thumbnail_hash=None,
                    user_id=file_obj.owner_user_id,
                )
        except Exception as e:
            current_app.logger.error(
                f"Error querying database for file {file_id}: {type(e).__name__}"
            )
            return jsonify({"error": "Internal server error"}), 500

        if not file_metadata:
            return jsonify({"error": "File not found"}), 404

        try:
            links = share_service.list_links_for_file(file_id)
        except Exception as e:
            current_app.logger.error(
                f"Error getting share links for file {file_id}: {type(e).__name__}"
            )
            return jsonify({"error": "Internal server error"}), 500

        # Include share URLs using VAULT_URL from settings
        links_dict = [
            link.to_dict(
                share_url=share_service.get_share_url(link.link_id, link.file_id)
            )
            for link in links
        ]
        return jsonify({"links": links_dict}), 200
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error in list_share_links: {type(e).__name__}"
        )
        current_app.logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500


@files_bp.route("/api/files/<file_id>", methods=["GET"])
def download_file(file_id: str):
    # Note: No @login_required to allow sharing via /share page
    # But we check if user is logged in and verify ownership
    """Download an encrypted file."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    share_service = _get_share_service()
    storage = _get_storage()

    # Check if user is authenticated via JWT
    user = get_current_user()
    user_id = user.id if user else None
    is_logged_in = user is not None

    # Check if this is a share link download
    link_token = request.args.get("token")
    share_link = None
    actual_file_id = file_id  # Will be updated if using share link

    if link_token:
        # Get share link first (before validation to get better error messages)
        share_link = share_service.get_share_link(link_token)
        if not share_link:
            from .utils import safe_error_response

            current_app.logger.warning(
                f"Share link not found: token={link_token[:20]}..., file_id={file_id}"
            )
            audit.log_action(
                "download",
                user_ip,
                {"error": "Share link not found", "link_token": link_token[:20]},
                False,
                file_id=file_id,
            )
            return jsonify({"error": "Share link not found"}), 404

        # Validate share link
        is_valid, error_msg = share_service.validate_share_link(link_token)
        if not is_valid:
            current_app.logger.warning(
                f"Invalid share link: {error_msg}, token={link_token[:20]}..., file_id={file_id}"
            )
            audit.log_action(
                "download",
                user_ip,
                {
                    "error": error_msg or "Invalid share link",
                    "file_id": file_id,
                    "link_token": link_token[:20],
                },
                False,
                file_id=file_id,
            )
            return jsonify({"error": error_msg or "Invalid share link"}), 403

        # Verify it's for this file
        if share_link.file_id != file_id:
            from .utils import safe_error_response

            current_app.logger.warning(
                f"Share link file mismatch: link_file_id={share_link.file_id}, requested_file_id={file_id}"
            )
            audit.log_action(
                "download",
                user_ip,
                {
                    "error": "Share link file mismatch",
                    "link_file_id": share_link.file_id,
                    "requested_file_id": file_id,
                },
                False,
                file_id=file_id,
            )
            return jsonify({"error": "Share link file mismatch"}), 403

        # Use file_id from share link
        actual_file_id = share_link.file_id
    elif is_logged_in:
        # For logged-in users, verify they own the file or are admin
        # File will be checked below
        pass
    else:
        # Not logged in and no share token - deny access
        audit.log_action(
            "download",
            user_ip,
            {"error": "Authentication required", "file_id": file_id},
            False,
            file_id=file_id,
        )
        return jsonify({"error": "Authentication required"}), 401

    # Get file from PostgreSQL using actual_file_id
    from vault.database.schema import File, User, GlobalRole, db

    file_obj = (
        db.session.query(File).filter_by(id=actual_file_id, deleted_at=None).first()
    )

    # Verify file exists
    if not file_obj:
        from .utils import safe_error_response

        current_app.logger.error(
            f"File not found in database: file_id={actual_file_id}, link_token={link_token[:20] if link_token else 'N/A'}"
        )
        audit.log_action(
            "download",
            user_ip,
            {"error": "File not found", "file_id": actual_file_id},
            False,
            file_id=actual_file_id,
        )
        return jsonify({"error": "File not found"}), 404

    # For logged-in users (without share link), verify ownership
    # SECURITY: Admins cannot access user files without explicit sharing
    if is_logged_in and not link_token:
        # Only the owner can access the file
        if file_obj.owner_user_id != user_id:
            from .utils import safe_error_response

            audit.log_action(
                "download",
                user_ip,
                {"error": "Access denied - not owner"},
                False,
                file_id=actual_file_id,
            )
            return safe_error_response("authorization_error", 403)

    # Increment download count if share link
    if link_token and share_link:
        share_service.increment_download_count(link_token)

        # Check if limit reached after increment
        updated_link = share_service.get_share_link(link_token)
        if updated_link and updated_link.has_reached_limit():
            share_service.revoke_link(link_token)

    # Use storage_ref if available, otherwise fallback to file_id
    # For files uploaded via old system, storage_ref might not be set, so use file_id
    storage_ref = None
    if hasattr(file_obj, "storage_ref") and file_obj.storage_ref:
        storage_ref = file_obj.storage_ref
    else:
        # Fallback to file_id for old system compatibility
        storage_ref = actual_file_id

    # Try storage_ref first, then fallback to file_id if not found
    if not storage.file_exists(storage_ref):
        # If storage_ref is different from file_id, try file_id as fallback
        if storage_ref != actual_file_id and storage.file_exists(actual_file_id):
            storage_ref = actual_file_id
        else:
            from .utils import safe_error_response

            current_app.logger.error(
                f"File not found in storage: file_id={actual_file_id}"
            )
            audit.log_action(
                "download",
                user_ip,
                {"error": "File data not found"},
                False,
                file_id=actual_file_id,
            )
            return safe_error_response(
                "file_not_found", 404, f"File storage_ref={storage_ref} not found"
            )

    # Log successful download
    audit.log_action(
        "download",
        user_ip,
        {
            "file_id": actual_file_id,
            "filename": file_obj.original_name,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "via_share_link": bool(link_token),
        },
        True,
        file_id=actual_file_id,
    )

    # Find file path (checks both storage and source)
    file_path = storage._find_file_path(storage_ref)
    if not file_path:
        current_app.logger.error(
            f"File not found in storage or source: file_id={actual_file_id}, storage_ref={storage_ref}"
        )
        audit.log_action(
            "download",
            user_ip,
            {"error": "File data not found"},
            False,
            file_id=actual_file_id,
        )
        return jsonify({"error": "File not found"}), 404

    return send_file(
        file_path,
        mimetype="application/octet-stream",
        download_name=file_obj.original_name,
    )


@files_bp.route("/api/files", methods=["GET"])
@jwt_required
def list_files():
    """List files (metadata only), optionally filtered by folder and view type."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    try:
        from vault.database.schema import File, User, GlobalRole, db

        share_service = _get_share_service()

        # Get folder_id (parent_id) from query parameter if provided
        parent_id = request.args.get("folder_id")
        if parent_id == "":
            parent_id = None

        # Get view type from query parameter (recent, starred, shared, trash)
        view_type = request.args.get("view", "all")

        # Get current user ID
        # SECURITY: Admins can only see their own files - no admin bypass
        user = get_current_user()
        if not user:
            audit.log_action(
                "list_files",
                user_ip,
                {"error": "Authentication required"},
                False,
            )
            return jsonify({"error": "Authentication required"}), 401
        current_user_id = user.id

        # List files in the specified folder (or all files if parent_id is None)
        # Only show files owned by the current user
        # Build query based on view type
        if view_type == "trash":
            # For trash view, show deleted files
            query = db.session.query(File).filter(File.deleted_at.isnot(None))
        else:
            # For other views, show non-deleted files
            query = db.session.query(File).filter_by(deleted_at=None)

        # Filter by owner only
        query = query.filter(File.owner_user_id == current_user_id)

        # Filter by view type
        if view_type == "starred":
            # Only show starred files
            query = query.filter_by(is_starred=True)

        if parent_id is not None:
            query = query.filter_by(parent_id=parent_id)
        else:
            # Root level files (no parent)
            query = query.filter_by(parent_id=None)

        file_objs = query.all()

        # Convert File objects to FileMetadata-like objects for compatibility
        from vault.models import FileMetadata

        files = []
        for file_obj in file_objs:
            metadata = FileMetadata(
                file_id=file_obj.id,
                original_name=file_obj.original_name,
                size=file_obj.size,
                encrypted_size=file_obj.encrypted_size,
                created_at=file_obj.created_at,
                encrypted_hash=file_obj.encrypted_hash,
                folder_id=file_obj.parent_id,
                encrypted_tags=None,
                encrypted_description=file_obj.encrypted_metadata,
                mime_type=file_obj.mime_type,
                thumbnail_hash=None,
                user_id=file_obj.owner_user_id,
            )
            files.append(metadata)

        # Filter files based on view type
        if view_type == "recent":
            # Show files modified in last 7 days, sorted by most recent first
            # Import timedelta here to avoid importing at module level if not needed (only used for recent view)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            files = [f for f in files if f.created_at >= cutoff]
            files.sort(key=lambda x: x.created_at, reverse=True)
        elif view_type == "shared":
            # Show files that have active share links
            # Note: Only share links are used for sharing
            files_with_shares = []
            for file_metadata in files:
                try:
                    share_links = share_service.list_links_for_file(
                        file_metadata.file_id
                    )
                    active_links = [
                        link for link in share_links if not link.is_expired()
                    ]
                    # Include files with active share links
                    if len(active_links) > 0:
                        files_with_shares.append(file_metadata)
                except Exception as e:
                    current_app.logger.warning(
                        f"Failed to process share links for file {file_metadata.file_id}: {e}"
                    )
                    continue
            files = files_with_shares

        # Enhance each file with share link information
        files_with_shares = []
        for file_metadata in files:
            try:
                file_dict = file_metadata.to_dict()

                # Get all share links for this file
                try:
                    share_links = share_service.list_links_for_file(
                        file_metadata.file_id
                    )
                    # Filter to only non-expired links
                    active_links = [
                        link for link in share_links if not link.is_expired()
                    ]
                    file_dict["has_active_share"] = len(active_links) > 0
                    file_dict["active_share_count"] = len(active_links)
                except Exception as e:
                    # If share service fails, log and skip share info
                    current_app.logger.warning(
                        f"Failed to retrieve share links for file {file_metadata.file_id}: {e}"
                    )
                    file_dict["has_active_share"] = False
                    file_dict["active_share_count"] = 0

                files_with_shares.append(file_dict)
            except Exception as e:
                # Skip files that fail to serialize
                audit.log_action(
                    "list_files",
                    user_ip,
                    {
                        "error": f"Failed to serialize file {file_metadata.file_id}: {str(e)}"
                    },
                    False,
                )
                continue

        return jsonify({"files": files_with_shares}), 200
    except Exception as e:
        from .utils import safe_error_response

        current_app.logger.error(f"Error listing files: {type(e).__name__}")
        audit.log_action(
            "list_files",
            user_ip,
            {"error": "Internal error"},
            False,
        )
        return safe_error_response("internal_error", 500, str(e))


@files_bp.route("/api/shared/files", methods=["GET"])
@csrf.exempt  # JWT-authenticated API endpoint
def list_shared_files():
    """List files shared with the current user via share links."""
    # JWT authentication check
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid authorization header format"}), 401

    token = parts[1]
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        return jsonify({"error": "Server configuration error"}), 500

    from vault.services.auth_service import AuthService

    auth_service = AuthService(secret_key)
    user = auth_service.verify_token(token)

    if not user:
        return jsonify({"error": "Invalid or expired token"}), 401

    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    share_service = _get_share_service()
    current_user_id = user.id

    try:
        # Get all files that have active share links created by the current user
        # This shows files the user has shared with others
        from vault.database.schema import File, db

        # Query files from PostgreSQL directly
        all_file_objs = (
            db.session.query(File)
            .filter_by(owner_user_id=current_user_id, deleted_at=None)
            .all()
        )

        shared_files = []

        for file_obj in all_file_objs:
            try:
                share_links = share_service.list_links_for_file(file_obj.id)
                active_links = []
                for link in share_links:
                    # Check if link is not expired
                    if link.expires_at:
                        # Compare with current time
                        from datetime import timezone

                        now_utc = datetime.now(timezone.utc)
                        if link.expires_at.tzinfo:
                            expires_utc = link.expires_at.astimezone(timezone.utc)
                        else:
                            expires_utc = link.expires_at.replace(tzinfo=timezone.utc)
                        if now_utc <= expires_utc:
                            active_links.append(link)
                    else:
                        # No expiration date
                        active_links.append(link)

                if len(active_links) > 0:
                    # Convert File to dict format compatible with frontend
                    file_dict = {
                        "id": file_obj.id,
                        "file_id": file_obj.id,  # For compatibility
                        "original_name": file_obj.original_name,
                        "size": file_obj.size,
                        "encrypted_size": file_obj.encrypted_size,
                        "created_at": (
                            file_obj.created_at.isoformat()
                            if file_obj.created_at
                            else None
                        ),
                        "updated_at": (
                            file_obj.updated_at.isoformat()
                            if file_obj.updated_at
                            else None
                        ),
                        "mime_type": file_obj.mime_type,
                        "vaultspace_id": file_obj.vaultspace_id,
                        "parent_id": file_obj.parent_id,
                        "owner_user_id": file_obj.owner_user_id,
                        "is_starred": file_obj.is_starred,
                    }
                    # Add share link info with URLs
                    file_dict["share_links"] = [
                        link.to_dict(
                            share_url=share_service.get_share_url(
                                link.link_id, link.file_id
                            )
                        )
                        for link in active_links
                    ]
                    shared_files.append(file_dict)
            except Exception as e:
                current_app.logger.warning(
                    f"Failed to process share links for file {file_obj.id}: {e}"
                )
                continue

        return jsonify({"files": shared_files}), 200
    except Exception as e:
        audit.log_action(
            "list_shared_files",
            user_ip,
            {"error": str(e)},
            False,
        )
        return jsonify({"error": str(e)}), 500


@files_bp.route("/api/shares/<link_token>", methods=["GET"])
@csrf.exempt  # Public endpoint, no CSRF needed
def get_share_link_info(link_token: str):
    """Get information about a share link."""
    share_service = _get_share_service()
    share_link = share_service.get_share_link(link_token)

    if not share_link:
        return jsonify({"error": "Share link not found"}), 404

    is_valid, error_msg = share_service.validate_share_link(link_token)

    # Get file information from PostgreSQL
    filename = None
    size = None
    try:
        from vault.database.schema import File, db

        file_obj = (
            db.session.query(File)
            .filter_by(id=share_link.file_id, deleted_at=None)
            .first()
        )
        if file_obj:
            filename = file_obj.original_name
            size = file_obj.size
    except Exception as e:
        current_app.logger.error(f"Error fetching file info for share link: {str(e)}")

    # Get share URL using VAULT_URL from settings
    share_url = share_service.get_share_url(link_token, share_link.file_id)
    response_data = {
        **share_link.to_dict(share_url=share_url),
        "is_valid": is_valid,
        "error": error_msg,
    }

    # Add file information if available
    if filename:
        response_data["filename"] = filename
    if size is not None:
        response_data["size"] = size

    return jsonify(response_data), 200


@files_bp.route("/api/shares/<link_token>", methods=["DELETE"])
@csrf.exempt  # CSRF not needed for JWT-authenticated API endpoints
def revoke_share_link(link_token: str):
    """Revoke a share link."""
    # JWT authentication check
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid authorization header format"}), 401

    token = parts[1]
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        return jsonify({"error": "Server configuration error"}), 500

    from vault.services.auth_service import AuthService

    auth_service = AuthService(secret_key)
    user = auth_service.verify_token(token)

    if not user:
        return jsonify({"error": "Invalid or expired token"}), 401

    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    share_service = _get_share_service()

    # Get share link to verify it exists and get file_id
    share_link = share_service.get_share_link(link_token)
    if not share_link:
        from .utils import safe_error_response

        audit.log_action(
            "share_revoke",
            user_ip,
            {"error": "Share link not found"},
            False,
        )
        return safe_error_response("not_found", 404)

    # Verify file exists in PostgreSQL
    from vault.database.schema import File, db

    file_obj = (
        db.session.query(File).filter_by(id=share_link.file_id, deleted_at=None).first()
    )
    if not file_obj:
        from .utils import safe_error_response

        audit.log_action(
            "share_revoke",
            user_ip,
            {"error": "File not found"},
            False,
            file_id=share_link.file_id,
        )
        return safe_error_response("file_not_found", 404)

    # Revoke (permanently delete) the share link
    share_service.revoke_link(link_token)

    # Log successful revocation
    audit.log_action(
        "share_revoke",
        user_ip,
        {
            "link_token": link_token,
            "file_id": share_link.file_id,
            "filename": file_obj.original_name,
        },
        True,
        file_id=share_link.file_id,
    )

    return jsonify({"status": "success"}), 200


@files_bp.route("/api/files/<file_id>", methods=["DELETE"])
@jwt_required
def delete_file(file_id: str):
    """Delete a file."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = user.id
    user_ip = get_client_ip() or "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    origin = request.headers.get("Origin", "unknown")

    audit = _get_audit()
    storage = _get_storage()

    # Enhanced rate limiting for delete operations
    rate_limiter = _get_rate_limiter()
    if rate_limiter:
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=50,  # Allow reasonable batch deletes
            window_seconds=3600,  # 1 hour window
            action_name="file_delete",
            user_id=user_id,
        )
        if not is_allowed:
            audit.log_action(
                "delete",
                user_ip,
                {
                    "error": "Rate limit exceeded",
                    "file_id": file_id,
                    "user_id": user_id,
                    "user_agent": user_agent,
                    "origin": origin,
                },
                False,
                file_id=file_id,
            )
            return jsonify({"error": error_msg or "Rate limit exceeded"}), 429

    from vault.database.schema import File, db

    file_obj = db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
    if not file_obj:
        from .utils import safe_error_response

        audit.log_action(
            "delete",
            user_ip,
            {
                "error": "File not found",
                "user_id": user_id,
                "user_agent": user_agent,
                "origin": origin,
            },
            False,
            file_id=file_id,
        )
        return safe_error_response("file_not_found", 404)

    # Soft delete: set deleted_at timestamp
    file_obj.deleted_at = datetime.now(timezone.utc)
    db.session.commit()

    # Also delete from storage
    storage.delete_file(file_id)

    # Log successful deletion with enhanced context
    audit.log_action(
        "delete",
        user_ip,
        {
            "file_id": file_id,
            "filename": file_obj.original_name,
            "user_id": user_id,
            "user_agent": user_agent,
            "origin": origin,
        },
        True,
        file_id=file_id,
    )
    return jsonify({"status": "success"}), 200


@files_bp.route("/api/files/<file_id>/move", methods=["PUT"])
@jwt_required
def move_file(file_id: str):
    """Move a file to a different folder."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    if not request.is_json:
        audit.log_action(
            "file_move",
            user_ip,
            {"error": "Request must be JSON", "file_id": file_id},
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    from vault.database.schema import File, db

    # Verify file exists
    file_obj = db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
    if not file_obj:
        from .utils import safe_error_response

        audit.log_action(
            "file_move",
            user_ip,
            {"error": "File not found"},
            False,
        )
        return safe_error_response("file_not_found", 404)

    data = request.json
    parent_id = data.get("folder_id")  # Can be None to move to root

    # Validate parent_id if provided (must be a folder)
    if parent_id is not None:
        folder = (
            db.session.query(File)
            .filter_by(
                id=parent_id, mime_type="application/x-directory", deleted_at=None
            )
            .first()
        )
        if folder is None:
            from .utils import safe_error_response

            audit.log_action(
                "file_move",
                user_ip,
                {"error": "Folder not found"},
                False,
            )
            return safe_error_response("not_found", 404)

    # Move the file by updating parent_id
    file_obj.parent_id = parent_id
    file_obj.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    audit.log_action(
        "file_move",
        user_ip,
        {
            "file_id": file_id,
            "filename": file_obj.original_name,
            "folder_id": parent_id,
        },
        True,
        file_id=file_id,
    )
    return jsonify({"status": "success"}), 200


__all__ = ["files_bp"]
