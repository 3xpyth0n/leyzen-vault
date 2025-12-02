"""Advanced file API routes."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from flask import Blueprint, current_app, jsonify, request

from vault.database.schema import File, UploadSession, db
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.encryption_service import EncryptionService
from vault.services.file_service import AdvancedFileService
from vault.services.quota_service import QuotaService
from vault.services.zip_service import ZipService
from vault.storage import FileStorage
from vault.blueprints.validators import (
    validate_vaultspace_id,
    validate_file_id,
    validate_pagination_params,
)
from vault.utils.mime_type_detection import detect_mime_type
from vault.utils.safe_json import safe_json_loads

files_api_bp = Blueprint("files_api", __name__, url_prefix="/api/v2/files")


def _get_file_service() -> AdvancedFileService:
    """Get AdvancedFileService instance."""
    return AdvancedFileService()


def _get_encryption_service() -> EncryptionService:
    """Get EncryptionService instance."""
    return EncryptionService()


def _get_storage() -> FileStorage:
    """Get FileStorage instance."""
    storage = current_app.config.get("VAULT_STORAGE")
    if storage is None:
        raise RuntimeError(
            "VAULT_STORAGE is not configured. Please check application initialization."
        )
    return storage


def _get_quota_service() -> QuotaService:
    """Get QuotaService instance."""
    return QuotaService()


def _get_zip_service() -> ZipService:
    """Get ZipService instance."""
    return ZipService()


def _validate_encrypted_key(encrypted_key: str) -> tuple[bool, str]:
    """Validate encrypted key format and size.

    Uses EncryptionService for consistent validation across the application.

    Args:
        encrypted_key: The encrypted key to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    from vault.services.encryption_service import EncryptionService

    encryption_service = EncryptionService()
    is_valid = encryption_service.validate_encrypted_key_format(encrypted_key)

    if not is_valid:
        return False, "Invalid encrypted key format"

    # Additional validation: check entropy to ensure data is actually encrypted
    try:
        import base64

        decoded = base64.b64decode(encrypted_key, validate=True)

        # Extract ciphertext (after IV, before tag)
        if len(decoded) < 28:  # Minimum: IV (12) + tag (16)
            return False, "Invalid encrypted key structure"

        iv = decoded[:12]
        tag = decoded[-16:]
        ciphertext = decoded[12:-16]

        # Verify IV is not all zeros
        if all(b == 0 for b in iv):
            return False, "Invalid encrypted key (weak IV detected)"

        # Verify tag is not all zeros or repeating pattern
        if all(b == 0 for b in tag) or len(set(tag)) == 1:
            return False, "Invalid encrypted key (corrupted tag detected)"

        # Verify encryption entropy for ciphertext
        if len(ciphertext) > 0:
            is_encrypted, entropy = _check_encryption_entropy(ciphertext)
            if not is_encrypted:
                data_size = len(ciphertext)
                if data_size <= 64:
                    expected_threshold = 4.5
                elif data_size <= 128:
                    expected_threshold = 6.5
                else:
                    expected_threshold = 7.5
                return (
                    False,
                    f"Invalid encrypted key (low entropy: {entropy:.2f} bits/byte, expected > {expected_threshold})",
                )

        return True, ""
    except Exception as e:
        return False, f"Invalid encrypted key format: {str(e)}"


def _check_encryption_entropy(data: bytes) -> tuple[bool, float]:
    """Check if data has high entropy (indicating encryption).

    For small data sizes (e.g., 32 bytes for an AES-256 key), the entropy
    can be lower than 7.5 bits/byte even for properly encrypted data due to
    statistical variance. We use a size-adjusted threshold.

    Args:
        data: Data bytes to check

    Returns:
        Tuple of (is_encrypted, entropy_bits_per_byte)
    """
    import math
    from collections import Counter

    if len(data) < 16:
        return False, 0.0

    # Calculate Shannon entropy
    counter = Counter(data)
    entropy = 0.0
    for count in counter.values():
        probability = count / len(data)
        if probability > 0:
            entropy -= probability * math.log2(probability)

    # Size-adjusted entropy threshold
    # Encrypted data must meet minimum entropy requirements based on size
    data_size = len(data)
    if data_size <= 64:
        # Small ciphertexts require sufficient entropy to prevent weak encryption
        # Lower threshold accounts for statistical variance in small samples
        threshold = 4.5
    elif data_size <= 128:
        # Medium ciphertexts require moderate entropy threshold
        threshold = 6.5
    else:
        # Larger ciphertexts require strict entropy threshold
        threshold = 7.5

    # Additional check: encrypted data should not be all zeros or repeating patterns
    unique_bytes = len(counter)
    if unique_bytes == 1:
        # All bytes are the same - definitely not encrypted
        return False, entropy

    # Check if data is mostly zeros (another sign of non-encrypted data)
    zero_count = counter.get(0, 0)
    if zero_count > len(data) * 0.9:
        return False, entropy

    return entropy > threshold, entropy


@files_api_bp.route("/folders", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def create_folder():
    """Create a folder.

    Request body:
        {
            "vaultspace_id": "vaultspace-uuid",
            "name": "Folder Name",
            "parent_id": "parent-folder-uuid" (optional)
        }

    Returns:
        JSON with folder info
    """
    from vault.middleware import validate_json_request, validate_vaultspace_id_param

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    vaultspace_id = data.get("vaultspace_id")
    name = data.get("name", "").strip()
    parent_id = data.get("parent_id")
    overwrite = data.get("overwrite", False)

    # Validate vaultspace_id format
    if vaultspace_id and not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format (must be UUID)"}), 400

    # Validate parent_id format if provided
    if parent_id and not validate_file_id(parent_id):
        return jsonify({"error": "Invalid parent_id format (must be UUID)"}), 400

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not name:
        return jsonify({"error": "Folder name is required"}), 400

    file_service = _get_file_service()

    try:
        folder = file_service.create_folder(
            vaultspace_id=vaultspace_id,
            user_id=user.id,
            name=name,
            parent_id=parent_id,
            overwrite=overwrite,
        )

        return (
            jsonify(
                {
                    "folder": folder.to_dict(),
                }
            ),
            201,
        )
    except ValueError as e:
        error_message = str(e)
        # Check if error is about duplicate name
        if "already exists" in error_message.lower():
            return jsonify({"error": error_message}), 409
        return jsonify({"error": error_message}), 400


@files_api_bp.route("", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def upload_file_v2():
    """Upload file with VaultSpace support.

    Request form data:
        - vaultspace_id: VaultSpace ID (required)
        - file: File to upload (required)
        - encrypted_file_key: File key encrypted with VaultSpace key (required)
        - encrypted_metadata: Encrypted metadata JSON (optional)
        - parent_id: Parent folder ID (optional)

    Returns:
        JSON with file info and FileKey
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.form
    vaultspace_id = data.get("vaultspace_id")
    encrypted_file_key = data.get("encrypted_file_key")
    overwrite = data.get("overwrite", "false").lower() == "true"

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not encrypted_file_key:
        return jsonify({"error": "encrypted_file_key is required"}), 400

    # Validate encrypted key format and size
    is_valid, error_msg = _validate_encrypted_key(encrypted_file_key)
    if not is_valid:
        return jsonify({"error": f"Invalid encrypted_file_key: {error_msg}"}), 400

    # Rate limiting: 10 uploads per minute per user and IP
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        user_id = user.id
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=10,
            window_seconds=60,
            action_name="file_upload",
            user_id=user_id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many uploads. Please try again later."}
                ),
                429,
            )

    if "file" not in request.files:
        return jsonify({"error": "File is required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "File is required"}), 400

    # SECURITY: Validate file size before reading into memory
    # Check Content-Length header first (if available)
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            content_length_int = int(content_length)
            # Get max file size from settings
            settings = current_app.config.get("VAULT_SETTINGS")
            max_file_size_bytes = (
                (settings.max_file_size_mb if settings else 100) * 1024 * 1024
            )
            if content_length_int > max_file_size_bytes:
                return (
                    jsonify(
                        {
                            "error": f"File size exceeds maximum allowed size ({settings.max_file_size_mb if settings else 100}MB)"
                        }
                    ),
                    413,  # Payload Too Large
                )
        except (ValueError, TypeError):
            # Invalid Content-Length header - continue with file read validation
            pass

    file_service = _get_file_service()
    storage = _get_storage()
    quota_service = _get_quota_service()

    try:
        # Read file data first to check size
        file_data = file.read()
        file_size = len(file_data)

        # SECURITY: Validate file size after reading
        settings = current_app.config.get("VAULT_SETTINGS")
        max_file_size_bytes = (
            (settings.max_file_size_mb if settings else 100) * 1024 * 1024
        )
        if file_size > max_file_size_bytes:
            return (
                jsonify(
                    {
                        "error": f"File size exceeds maximum allowed size ({settings.max_file_size_mb if settings else 100}MB)"
                    }
                ),
                413,  # Payload Too Large
            )

        # Check storage quota before upload
        # Estimate encrypted size (add ~33% overhead for AES-GCM)
        estimated_encrypted_size = int(file_size * 1.33)

        has_storage_quota, storage_quota_info = quota_service.check_user_quota(
            user.id, estimated_encrypted_size
        )

        if not has_storage_quota:
            return (
                jsonify(
                    {
                        "error": "Storage quota exceeded",
                        "quota_info": storage_quota_info,
                    }
                ),
                403,
            )

        # Check file quota before upload
        has_file_quota, file_quota_info = quota_service.check_user_file_quota(
            user.id, additional_files=1
        )

        if not has_file_quota:
            return (
                jsonify(
                    {
                        "error": "File quota exceeded",
                        "quota_info": file_quota_info,
                    }
                ),
                403,
            )

        # Generate file ID for storage
        file_id = storage.generate_file_id()

        # Store encrypted file (file is already encrypted client-side)
        try:
            saved_path = storage.save_file(file_id, file_data)
            # save_file returns a Path, but we use file_id as storage_ref
            storage_ref = file_id
        except IOError as e:
            current_app.logger.error(
                f"Failed to save file {file_id}: {type(e).__name__}: {e}"
            )
            return jsonify({"error": "Failed to save file"}), 500

        # Calculate hash of encrypted data
        import hashlib

        encrypted_hash = hashlib.sha256(file_data).hexdigest()

        # Detect MIME type properly
        detected_mime_type = detect_mime_type(
            filename=file.filename,
            file_data=file_data,
            provided_mime_type=file.content_type,
        )

        # Upload file metadata
        file_obj, file_key = file_service.upload_file(
            vaultspace_id=vaultspace_id,
            user_id=user.id,
            original_name=file.filename,
            encrypted_data=file_data,
            encrypted_hash=encrypted_hash,
            storage_ref=file_id,  # Use file_id as storage_ref
            encrypted_file_key=encrypted_file_key,
            mime_type=detected_mime_type,
            parent_id=data.get("parent_id"),
            encrypted_metadata=data.get("encrypted_metadata"),
            overwrite=overwrite,
        )

        # Promote file to persistent storage with validation
        # This ensures the file is persisted even without orchestrator
        try:
            from common.services.file_promotion_service import (
                FilePromotionService,
            )
            from common.services.sync_validation_service import (
                SyncValidationService,
            )
            from vault.database.schema import File

            # Initialize validation service with database
            validation_service = SyncValidationService(
                db_session=db.session, File_model=File, logger=current_app.logger
            )
            promotion_service = FilePromotionService(
                validation_service=validation_service,
                logger_instance=current_app.logger,
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
                    current_app.logger.warning(
                        f"[PROMOTION] Failed to promote file {file_id}: {error_msg}"
                    )
        except Exception as e:
            current_app.logger.error(
                f"[PROMOTION ERROR] Exception during promotion of {file_id}: {e}",
                exc_info=True,
            )

        return (
            jsonify(
                {
                    "file": file_obj.to_dict(),
                    "file_key": file_key.to_dict(),
                }
            ),
            201,
        )
    except ValueError as e:
        error_message = str(e)
        # Check if error is about duplicate name
        if "already exists" in error_message.lower():
            return jsonify({"error": error_message}), 409
        return jsonify({"error": error_message}), 400


@files_api_bp.route("", methods=["GET"])
@jwt_required
def list_files():
    """List files in a VaultSpace.

    Query parameters:
        - vaultspace_id: VaultSpace ID (required)
        - parent_id: Parent folder ID (optional)

    Returns:
        JSON with list of files
    """
    from vault.blueprints.validators import validate_file_id, validate_vaultspace_id

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")
    parent_id = request.args.get("parent_id")

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    # Validate vaultspace_id format
    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format (must be UUID)"}), 400

    # Validate parent_id format if provided
    if parent_id and not validate_file_id(parent_id):
        return jsonify({"error": "Invalid parent_id format (must be UUID)"}), 400

    page, per_page, error = validate_pagination_params(
        request.args.get("page", 1), request.args.get("per_page", 50), max_per_page=100
    )
    if error:
        return jsonify({"error": error}), 400

    file_service = _get_file_service()

    try:
        result = file_service.list_files_in_vaultspace(
            vaultspace_id=vaultspace_id,
            user_id=user.id,
            parent_id=parent_id,
            page=page,
            per_page=per_page,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/<file_id>", methods=["GET"])
@jwt_required
def get_file(file_id: str):
    """Get file details and encrypted FileKey.

    Query parameters:
        - vaultspace_id: VaultSpace ID (required)

    Returns:
        JSON with file info and encrypted FileKey
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")
    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format"}), 400

    file_service = _get_file_service()
    encryption_service = _get_encryption_service()

    try:
        file_obj, permissions = file_service.get_file_with_permissions(file_id, user.id)

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        if file_obj.vaultspace_id != vaultspace_id:
            return (
                jsonify({"error": "File does not belong to specified VaultSpace"}),
                400,
            )

        # Check if user has read permission
        has_permission = False
        if file_obj.owner_user_id == user.id:
            has_permission = True
        elif permissions:
            has_permission = True

        if not has_permission:
            return jsonify({"error": "Permission denied"}), 403

        # For folders (directories), we don't need a FileKey
        if file_obj.mime_type == "application/x-directory":
            return (
                jsonify(
                    {
                        "file": file_obj.to_dict(),
                        "file_key": None,
                    }
                ),
                200,
            )

        # Get encrypted FileKey for regular files
        file_key = encryption_service.get_file_key(file_id, vaultspace_id)

        if not file_key:
            return jsonify({"error": "FileKey not found"}), 404

        return (
            jsonify(
                {
                    "file": file_obj.to_dict(),
                    "file_key": file_key.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/<file_id>/download", methods=["GET"])
@jwt_required
def download_file(file_id: str):
    """Download encrypted file data.

    Query parameters:
        - vaultspace_id: VaultSpace ID (required)

    Returns:
        Encrypted file data as binary stream
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")
    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format"}), 400

    # Rate limiting: 20 downloads per minute per user
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        user_id = user.id
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=20,
            window_seconds=60,
            action_name="file_download",
            user_id=user_id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {
                        "error": error_msg
                        or "Too many downloads. Please try again later."
                    }
                ),
                429,
            )

    file_service = _get_file_service()
    storage = _get_storage()

    try:
        # Get file with permissions check
        file_obj, permissions = file_service.get_file_with_permissions(file_id, user.id)

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        if file_obj.vaultspace_id != vaultspace_id:
            return (
                jsonify({"error": "File does not belong to specified VaultSpace"}),
                400,
            )

        # Check if user has read permission
        has_permission = False
        if file_obj.owner_user_id == user.id:
            has_permission = True
        elif permissions:
            has_permission = True

        if not has_permission:
            return jsonify({"error": "Permission denied"}), 403

        # Read encrypted file data from storage
        try:
            encrypted_data = storage.read_file(file_obj.storage_ref)
        except FileNotFoundError as e:
            current_app.logger.error(
                f"File {file_id} not found in storage. storage_ref: {file_obj.storage_ref}, error: {e}"
            )
            return jsonify({"error": "File data not found in storage"}), 404

        # Return encrypted file as binary response
        from flask import Response

        response = Response(
            encrypted_data,
            mimetype="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file_obj.original_name}.encrypted"',
                "Content-Length": str(len(encrypted_data)),
            },
        )
        return response

    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/<file_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def delete_file(file_id: str):
    """Delete a file or folder.

    Args:
        file_id: File ID

    Returns:
        JSON with success message
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()
    storage = _get_storage()

    try:
        # Get file to get storage_ref
        file_obj, _ = file_service.get_file_with_permissions(file_id, user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        # Delete file
        success = file_service.delete_file(file_id, user.id)

        if not success:
            return jsonify({"error": "File not found"}), 404

        # Delete from storage (only if it's a file, not a folder)
        if file_obj.storage_ref and file_obj.mime_type != "application/x-directory":
            try:
                storage.delete_file(file_obj.storage_ref)
            except Exception as e:
                # Storage deletion failure shouldn't block database deletion, but log the error
                current_app.logger.warning(
                    f"Failed to delete storage file {file_obj.storage_ref}: {e}"
                )

        return (
            jsonify(
                {
                    "message": "File deleted successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@files_api_bp.route("/<file_id>/rename", methods=["PUT"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def rename_file(file_id: str):
    """Rename a file or folder.

    Request body:
        {
            "name": "New Name"
        }

    Returns:
        JSON with updated file info
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name is required"}), 400

    file_service = _get_file_service()

    try:
        file_obj = file_service.rename_file(
            file_id=file_id,
            user_id=user.id,
            new_name=new_name,
        )

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        return (
            jsonify(
                {
                    "file": file_obj.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@files_api_bp.route("/<file_id>/move", methods=["PUT"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def move_file(file_id: str):
    """Move a file or folder to a different parent.

    Request body:
        {
            "parent_id": "parent-folder-uuid" (optional, null for root)
        }

    Returns:
        JSON with updated file info
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    parent_id = data.get("parent_id")  # Can be None for root

    file_service = _get_file_service()

    try:
        file_obj = file_service.move_file(
            file_id=file_id,
            user_id=user.id,
            new_parent_id=parent_id,
        )

        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        return (
            jsonify(
                {
                    "file": file_obj.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/<file_id>/share", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def share_file_v2(file_id: str):
    """Share file endpoint.

    This endpoint returns HTTP 410 Gone. Use share links (ShareService) or public links (AdvancedSharingService) instead.

    Returns:
        HTTP 410 Gone with error message
    """
    return (
        jsonify(
            {
                "error": "This endpoint is not available. Please use share links or public links instead.",
                "code": "FEATURE_REMOVED",
            }
        ),
        410,
    )


@files_api_bp.route("/batch/delete", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def batch_delete_files():
    """Delete multiple files in batch.

    Request body:
        {
            "file_ids": ["file-uuid1", "file-uuid2", ...]
        }

    Returns:
        JSON with batch operation results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    file_ids = data.get("file_ids", [])
    if not isinstance(file_ids, list) or len(file_ids) == 0:
        return jsonify({"error": "file_ids must be a non-empty list"}), 400

    file_service = _get_file_service()
    storage = _get_storage()

    try:
        result = file_service.batch_delete_files(file_ids, user.id)

        # Delete from storage for successfully deleted files
        for file_id in file_ids:
            try:
                file_obj = db.session.query(File).filter_by(id=file_id).first()
                if (
                    file_obj
                    and file_obj.storage_ref
                    and file_obj.mime_type != "application/x-directory"
                ):
                    try:
                        storage.delete_file(file_obj.storage_ref)
                    except Exception as e:
                        # Storage deletion failure shouldn't block batch operation, but log the error
                        current_app.logger.warning(
                            f"Failed to delete storage file {file_obj.storage_ref} during batch operation: {e}"
                        )
            except Exception as e:
                # Log error but continue with batch operation
                current_app.logger.warning(
                    f"Error processing file {file_id} during batch operation: {e}"
                )

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/batch/move", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def batch_move_files():
    """Move multiple files to a new parent in batch.

    Request body:
        {
            "file_ids": ["file-uuid1", "file-uuid2", ...],
            "new_parent_id": "parent-folder-uuid" (optional, null for root)
        }

    Returns:
        JSON with batch operation results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    file_ids = data.get("file_ids", [])
    if not isinstance(file_ids, list) or len(file_ids) == 0:
        return jsonify({"error": "file_ids must be a non-empty list"}), 400

    new_parent_id = data.get("new_parent_id")

    file_service = _get_file_service()

    try:
        result = file_service.batch_move_files(file_ids, user.id, new_parent_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/batch/rename", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def batch_rename_files():
    """Rename multiple files in batch.

    Request body:
        {
            "file_renames": [
                {"file_id": "file-uuid1", "new_name": "New Name 1"},
                {"file_id": "file-uuid2", "new_name": "New Name 2"},
                ...
            ]
        }

    Returns:
        JSON with batch operation results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    file_renames = data.get("file_renames", [])
    if not isinstance(file_renames, list) or len(file_renames) == 0:
        return jsonify({"error": "file_renames must be a non-empty list"}), 400

    file_service = _get_file_service()

    try:
        result = file_service.batch_rename_files(file_renames, user.id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/<file_id>/copy", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def copy_file(file_id: str):
    """Copy a file or folder to a new location.

    Request body:
        {
            "new_parent_id": "parent-folder-uuid" (optional, null for root),
            "new_vaultspace_id": "vaultspace-uuid" (optional, null to keep same),
            "new_name": "New Name" (optional, null to keep same)
        }

    Returns:
        JSON with copied file info
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    new_parent_id = data.get("new_parent_id")
    new_vaultspace_id = data.get("new_vaultspace_id")
    new_name = data.get("new_name")

    file_service = _get_file_service()

    try:
        # Check if it's a folder
        file_obj, _ = file_service.get_file_with_permissions(file_id, user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404

        if file_obj.mime_type == "application/x-directory":
            copied_file = file_service.copy_folder(
                folder_id=file_id,
                user_id=user.id,
                new_parent_id=new_parent_id,
                new_vaultspace_id=new_vaultspace_id,
                new_name=new_name,
            )
        else:
            copied_file = file_service.copy_file(
                file_id=file_id,
                user_id=user.id,
                new_parent_id=new_parent_id,
                new_vaultspace_id=new_vaultspace_id,
                new_name=new_name,
            )

        return jsonify({"file": copied_file.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/recent", methods=["GET"])
@jwt_required
def list_recent_files():
    """List recent files.

    Query parameters:
        - vaultspace_id: Optional VaultSpace ID filter
        - limit: Maximum number of files to return (default: 50)
        - days: Number of days to look back (default: 30)

    Returns:
        JSON with list of recent files
    """
    from datetime import timedelta
    from sqlalchemy import and_, or_

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")
    limit = int(request.args.get("limit", 50))
    days = int(request.args.get("days", 30))

    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query recent files - CRITICAL: Must exclude deleted files
    # Use explicit and_() to ensure deleted_at filter is always applied
    query = db.session.query(File).filter(
        and_(
            File.deleted_at.is_(None),  # Exclude deleted files (trash)
            File.owner_user_id == user.id,
            or_(
                File.updated_at >= cutoff_date,
                File.created_at >= cutoff_date,
            ),
        )
    )

    # Filter by vaultspace if provided
    if vaultspace_id:
        query = query.filter(File.vaultspace_id == vaultspace_id)

    # Order by most recently updated first
    query = query.order_by(File.updated_at.desc())

    # Limit results
    recent_files = query.limit(limit).all()

    # Double-check: filter out any deleted files that might have slipped through
    # (defensive programming - should not happen but ensures data integrity)
    recent_files = [f for f in recent_files if f.deleted_at is None]

    return jsonify({"files": [f.to_dict() for f in recent_files]}), 200


@files_api_bp.route("/starred", methods=["GET"])
@jwt_required
def list_starred_files():
    """List all starred files.

    Query parameters:
        - vaultspace_id: Optional VaultSpace ID filter

    Returns:
        JSON with list of starred files
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_id = request.args.get("vaultspace_id")
    file_service = _get_file_service()

    try:
        starred_files = file_service.list_starred_files(
            vaultspace_id=vaultspace_id,
            user_id=user.id,
        )
        return jsonify({"files": [f.to_dict() for f in starred_files]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/<file_id>/star", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def toggle_star_file(file_id: str):
    """Toggle star status of a file.

    Returns:
        JSON with updated file info
    """
    # Validate file_id format
    if not validate_file_id(file_id):
        return jsonify({"error": "Invalid file_id format (must be UUID)"}), 400

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    file_service = _get_file_service()

    try:
        file_obj = file_service.toggle_star_file(file_id=file_id, user_id=user.id)
        if not file_obj:
            return jsonify({"error": "File not found"}), 404
        return jsonify({"file": file_obj.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@files_api_bp.route("/zip/prepare", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def prepare_zip():
    """Prepare folder tree for zipping.

    Request body:
        {
            "folder_id": "folder-uuid",
            "vaultspace_id": "vaultspace-uuid"
        }

    Returns:
        JSON with folder tree including files with encrypted keys
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    folder_id = data.get("folder_id")
    vaultspace_id = data.get("vaultspace_id")

    if not folder_id:
        return jsonify({"error": "folder_id is required"}), 400

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not validate_file_id(folder_id):
        return jsonify({"error": "Invalid folder_id format"}), 400

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    zip_service = _get_zip_service()

    try:
        folder_tree = zip_service.get_folder_tree(
            folder_id=folder_id,
            vaultspace_id=vaultspace_id,
            user_id=user.id,
        )

        return jsonify(folder_tree), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/zip/extract", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def prepare_extract():
    """Prepare ZIP file for extraction.

    Request body:
        {
            "zip_file_id": "file-uuid",
            "vaultspace_id": "vaultspace-uuid",
            "target_parent_id": "parent-folder-uuid" (optional)
        }

    Returns:
        JSON with ZIP file info and encrypted file key
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    zip_file_id = data.get("zip_file_id")
    vaultspace_id = data.get("vaultspace_id")
    target_parent_id = data.get("target_parent_id")

    if not zip_file_id:
        return jsonify({"error": "zip_file_id is required"}), 400

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not validate_file_id(zip_file_id):
        return jsonify({"error": "Invalid zip_file_id format"}), 400

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    if target_parent_id and not validate_file_id(target_parent_id):
        return jsonify({"error": "Invalid target_parent_id format"}), 400

    file_service = _get_file_service()
    encryption_service = _get_encryption_service()

    try:
        # Get file with permissions check
        file_obj, permissions = file_service.get_file_with_permissions(
            zip_file_id, user.id
        )

        if not file_obj:
            return jsonify({"error": "ZIP file not found"}), 404

        if file_obj.vaultspace_id != vaultspace_id:
            return (
                jsonify({"error": "ZIP file does not belong to specified VaultSpace"}),
                400,
            )

        # Check if it's actually a ZIP file
        # Check by MIME type or by file extension
        is_zip_by_mime = file_obj.mime_type in (
            "application/zip",
            "application/x-zip-compressed",
        )
        is_zip_by_extension = (
            file_obj.original_name and file_obj.original_name.lower().endswith(".zip")
        )

        if not (is_zip_by_mime or is_zip_by_extension):
            return jsonify({"error": "File is not a ZIP file"}), 400

        # Check permissions
        has_permission = False
        if file_obj.owner_user_id == user.id:
            has_permission = True
        elif permissions:
            has_permission = True

        if not has_permission:
            return jsonify({"error": "Permission denied"}), 403

        # Get encrypted file key
        file_key = encryption_service.get_file_key(zip_file_id, vaultspace_id)

        if not file_key:
            return jsonify({"error": "FileKey not found for ZIP file"}), 404

        return (
            jsonify(
                {
                    "file": file_obj.to_dict(),
                    "file_key": file_key.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/upload/session", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def create_upload_session():
    """Create an upload session for chunked file uploads.

    Request body:
        {
            "vaultspace_id": "vaultspace-uuid",
            "original_name": "file.txt",
            "total_size": 10485760,  # Expected total file size in bytes
            "chunk_size": 5242880,  # Chunk size in bytes (default 5MB)
            "encrypted_file_key": "encrypted-key",
            "parent_id": "parent-folder-uuid" (optional),
            "encrypted_metadata": "encrypted-metadata" (optional),
            "mime_type": "text/plain" (optional)
        }

    Returns:
        JSON with session_id and file_id
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    vaultspace_id = data.get("vaultspace_id")
    original_name = data.get("original_name")
    total_size = data.get("total_size")
    chunk_size = data.get("chunk_size", 5 * 1024 * 1024)  # Default 5MB
    encrypted_file_key = data.get("encrypted_file_key")

    if not vaultspace_id:
        return jsonify({"error": "vaultspace_id is required"}), 400

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    if not original_name:
        return jsonify({"error": "original_name is required"}), 400

    if not total_size or not isinstance(total_size, int) or total_size <= 0:
        return jsonify({"error": "total_size must be a positive integer"}), 400

    if not encrypted_file_key:
        return jsonify({"error": "encrypted_file_key is required"}), 400

    # Validate encrypted key format
    is_valid, error_msg = _validate_encrypted_key(encrypted_file_key)
    if not is_valid:
        return jsonify({"error": f"Invalid encrypted_file_key: {error_msg}"}), 400

    file_service = _get_file_service()
    storage = _get_storage()
    quota_service = _get_quota_service()

    try:
        # Verify user has access to VaultSpace
        from vault.services.vaultspace_service import VaultSpaceService

        vaultspace_service = VaultSpaceService()
        vaultspace = vaultspace_service.get_vaultspace(vaultspace_id)
        if not vaultspace:
            return jsonify({"error": "VaultSpace not found"}), 404

        if vaultspace.owner_user_id != user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Check storage quota
        # Estimate encrypted size (add ~33% overhead for AES-GCM)
        estimated_encrypted_size = int(total_size * 1.33)
        has_storage_quota, storage_quota_info = quota_service.check_user_quota(
            user.id, estimated_encrypted_size
        )
        if not has_storage_quota:
            return (
                jsonify(
                    {
                        "error": "Storage quota exceeded",
                        "quota_info": storage_quota_info,
                    }
                ),
                403,
            )

        # Check file quota
        has_file_quota, file_quota_info = quota_service.check_user_file_quota(
            user.id, additional_files=1
        )
        if not has_file_quota:
            return (
                jsonify(
                    {
                        "error": "File quota exceeded",
                        "quota_info": file_quota_info,
                    }
                ),
                403,
            )

        # Generate file ID upfront
        file_id = storage.generate_file_id()

        # Calculate total chunks
        total_chunks = (total_size + chunk_size - 1) // chunk_size  # Ceiling division

        # Set expiration to 24 hours from now
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        # Detect MIME type from filename if not provided or generic
        provided_mime_type = data.get("mime_type")
        detected_mime_type = detect_mime_type(
            filename=original_name,
            file_data=None,  # Can't detect from content in chunked upload
            provided_mime_type=provided_mime_type,
        )

        # Create upload session
        session = UploadSession(
            user_id=user.id,
            vaultspace_id=vaultspace_id,
            file_id=file_id,
            original_name=original_name,
            total_size=total_size,
            uploaded_size=0,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            uploaded_chunks=0,
            status="pending",
            encrypted_file_key=encrypted_file_key,
            parent_id=data.get("parent_id"),
            encrypted_metadata=data.get("encrypted_metadata"),
            mime_type=detected_mime_type,
            expires_at=expires_at,
        )

        # Add session to database and commit
        db.session.add(session)
        db.session.flush()  # Flush to get the ID without committing

        try:
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()
            raise

        current_app.logger.info(
            f"create_upload_session: Created session_id={session.id}, user_id={user.id}, "
            f"file_id={file_id}, total_chunks={total_chunks}"
        )

        # Return session info including all necessary data to recreate session if needed
        return (
            jsonify(
                {
                    "session_id": session.id,
                    "file_id": file_id,
                    "total_chunks": total_chunks,
                    "chunk_size": chunk_size,
                    "vaultspace_id": vaultspace_id,
                    "original_name": original_name,
                    "total_size": total_size,
                    "encrypted_file_key": encrypted_file_key,
                    "parent_id": data.get("parent_id"),
                    "mime_type": data.get("mime_type"),
                    "expires_at": expires_at.isoformat(),
                }
            ),
            201,
        )
    except ValueError as e:
        db.session.rollback()  # Ensure rollback on error
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/upload/chunk", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def upload_chunk():
    """Upload a chunk for chunked file uploads.

    Request form data:
        - session_id: Upload session ID (required)
        - chunk_index: Zero-based chunk index (required)
        - chunk: Chunk data (binary, required)

    Returns:
        JSON with progress info
    """
    user = get_current_user()
    if not user:
        current_app.logger.warning("upload_chunk: Authentication required")
        return jsonify({"error": "Authentication required"}), 401

    session_id = request.form.get("session_id")

    # Session data from client for validation and progress tracking
    session_data_from_client = request.form.get("session_data")

    chunk_index_str = request.form.get("chunk_index")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    if chunk_index_str is None:
        return jsonify({"error": "chunk_index is required"}), 400

    try:
        chunk_index = int(chunk_index_str)
        if chunk_index < 0:
            return jsonify({"error": "chunk_index must be non-negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "chunk_index must be an integer"}), 400

    if "chunk" not in request.files:
        return jsonify({"error": "chunk is required"}), 400

    chunk_file = request.files["chunk"]
    if chunk_file.filename == "":
        return jsonify({"error": "chunk is required"}), 400

    # Read chunk data
    chunk_data = chunk_file.read()

    storage = _get_storage()

    try:
        # File-based progress tracking: determine progress from the actual file on disk
        # This makes the system resilient to DB rollback issues between workers

        if not session_data_from_client:
            return jsonify({"error": "session_data is required for chunk upload"}), 400

        client_session_data = safe_json_loads(
            session_data_from_client,
            max_size=10 * 1024,  # 10KB for session data
            max_depth=20,
            context="upload session_data",
        )

        # Validate required fields from client
        total_size = client_session_data.get("total_size")
        chunk_size = client_session_data.get("chunk_size", 5 * 1024 * 1024)
        total_chunks = client_session_data.get("total_chunks")

        if not all([total_size, chunk_size, total_chunks]):
            return (
                jsonify({"error": "Invalid session_data: missing required fields"}),
                400,
            )

        # Determine actual progress by checking temp file size on disk
        temp_file_path = storage.get_temp_file_path(session_id)
        uploaded_size = 0
        uploaded_chunks = 0

        if temp_file_path.exists():
            uploaded_size = temp_file_path.stat().st_size
            # Calculate uploaded chunks from file size
            uploaded_chunks = uploaded_size // chunk_size

        # Validate chunk_index matches expected next chunk based on file size
        expected_chunk_index = uploaded_chunks
        if chunk_index != expected_chunk_index:
            return (
                jsonify(
                    {
                        "error": f"Expected chunk {expected_chunk_index}, got chunk {chunk_index}",
                        "expected_chunk_index": expected_chunk_index,
                    }
                ),
                400,
            )

        # Validate chunk size (except for last chunk)
        is_last_chunk = chunk_index == total_chunks - 1
        if not is_last_chunk and len(chunk_data) != chunk_size:
            return (
                jsonify(
                    {
                        "error": f"Chunk size mismatch: expected {chunk_size}, got {len(chunk_data)}",
                    }
                ),
                400,
            )

        # Save chunk to temporary file
        storage.save_chunk(session_id, chunk_index, chunk_data)

        # Re-check file size after writing to get actual progress
        if temp_file_path.exists():
            uploaded_size = temp_file_path.stat().st_size
            uploaded_chunks = chunk_index + 1
        else:
            uploaded_size = len(chunk_data)
            uploaded_chunks = chunk_index + 1

        # Check if all chunks are uploaded
        # We've uploaded chunk_index, so if chunk_index is the last chunk (total_chunks - 1), we're complete
        is_complete = chunk_index >= total_chunks - 1

        response_data = {
            "uploaded_size": uploaded_size,
            "total_size": total_size,
            "uploaded_chunks": uploaded_chunks,
            "total_chunks": total_chunks,
            "next_chunk_index": uploaded_chunks if not is_complete else None,
            "is_complete": is_complete,
        }
        return (
            jsonify(response_data),
            200,
        )
    except ValueError as e:
        current_app.logger.error(f"ValueError in upload_chunk: {e}")
        return jsonify({"error": str(e)}), 400
    except IOError as e:
        current_app.logger.error(
            f"IOError: Failed to save chunk {chunk_index} for session {session_id}: {e}"
        )
        return jsonify({"error": f"Failed to save chunk: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error in upload_chunk for session {session_id}, chunk {chunk_index}: {e}",
            exc_info=True,
        )
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@files_api_bp.route("/upload/complete", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def complete_upload():
    """Complete chunked upload and create File record.

    Request body:
        {
            "session_id": "session-uuid",
            "encrypted_hash": "sha256-hash" (optional, computed if not provided)
        }

    Returns:
        JSON with file info and FileKey
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    encrypted_hash = data.get("encrypted_hash")  # Optional, computed if not provided

    file_service = _get_file_service()
    storage = _get_storage()

    try:
        # Get session
        session = db.session.query(UploadSession).filter_by(id=session_id).first()
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Verify session belongs to user
        if session.user_id != user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Check if session is expired
        if session.is_expired() or session.status == "expired":
            session.status = "expired"
            db.session.commit()
            return jsonify({"error": "Session expired"}), 410

        # Verify all chunks are uploaded by checking the actual file on disk
        # Don't rely on session.uploaded_chunks as it may not be updated due to rollback issues
        temp_file_path = storage.get_temp_file_path(session_id)
        if not temp_file_path.exists():
            return jsonify({"error": "Temporary file not found"}), 404

        actual_file_size = temp_file_path.stat().st_size

        # Verify uploaded size matches total size (within tolerance for last chunk)
        if abs(actual_file_size - session.total_size) > 1024:  # 1KB tolerance
            return (
                jsonify(
                    {
                        "error": f"Size mismatch: uploaded {actual_file_size}, expected {session.total_size}",
                    }
                ),
                400,
            )

        # Complete chunked upload and move to final location
        # This calculates hash if not provided
        try:
            file_path = storage.complete_chunked_upload(
                session_id, session.file_id, encrypted_hash
            )

            # Get actual hash for database
            import hashlib

            encrypted_data = storage.read_file(session.file_id)
            final_hash = hashlib.sha256(encrypted_data).hexdigest()

            # Re-detect MIME type from complete file data for better accuracy
            # Note: encrypted_data is encrypted, so we can't detect from content
            # But we can still improve detection from filename if mime_type is generic
            final_mime_type = detect_mime_type(
                filename=session.original_name,
                file_data=None,  # Data is encrypted, can't detect from content
                provided_mime_type=session.mime_type,
            )

            # Create File record
            file_obj, file_key = file_service.upload_file(
                vaultspace_id=session.vaultspace_id,
                user_id=user.id,
                original_name=session.original_name,
                encrypted_data=encrypted_data,
                encrypted_hash=final_hash,
                storage_ref=session.file_id,
                encrypted_file_key=session.encrypted_file_key,
                mime_type=final_mime_type,
                parent_id=session.parent_id,
                encrypted_metadata=session.encrypted_metadata,
            )

            # Promote file to persistent storage with validation
            # This ensures the file is persisted even without orchestrator
            storage_ref = session.file_id
            try:
                from common.services.file_promotion_service import (
                    FilePromotionService,
                )
                from common.services.sync_validation_service import (
                    SyncValidationService,
                )
                from vault.database.schema import File

                # Initialize validation service with database
                validation_service = SyncValidationService(
                    db_session=db.session, File_model=File, logger=current_app.logger
                )
                promotion_service = FilePromotionService(
                    validation_service=validation_service,
                    logger_instance=current_app.logger,
                )

                # Get file path in tmpfs
                source_path = storage.get_file_path(storage_ref)
                target_dir = storage.source_dir

                if source_path.exists() and target_dir:
                    success, error_msg = promotion_service.promote_file(
                        file_id=storage_ref,
                        source_path=source_path,
                        target_dir=target_dir,
                        base_dir=storage.storage_dir / "files",
                    )

                    if not success:
                        current_app.logger.warning(
                            f"[PROMOTION] Failed to promote file {storage_ref}: {error_msg}"
                        )
            except Exception as e:
                current_app.logger.error(
                    f"[PROMOTION ERROR] Exception during promotion of {storage_ref}: {e}",
                    exc_info=True,
                )

            # Mark session as completed and delete
            session.status = "completed"
            db.session.delete(session)
            db.session.commit()

            return (
                jsonify(
                    {
                        "file": file_obj.to_dict(),
                        "file_key": file_key.to_dict(),
                    }
                ),
                201,
            )
        except FileNotFoundError as e:
            return jsonify({"error": f"Temporary file not found: {str(e)}"}), 404
        except IOError as e:
            # Mark session as failed for debugging
            session.status = "failed"
            db.session.commit()
            current_app.logger.error(
                f"Failed to complete upload for session {session_id}: {e}"
            )
            return jsonify({"error": f"Failed to complete upload: {str(e)}"}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@files_api_bp.route("/upload/session/<session_id>", methods=["GET"])
@jwt_required
def get_upload_status(session_id: str):
    """Get upload session status.

    Returns:
        JSON with session status and progress
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    try:
        session = db.session.query(UploadSession).filter_by(id=session_id).first()
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Verify session belongs to user
        if session.user_id != user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Check if session is expired
        if session.is_expired() or session.status == "expired":
            session.status = "expired"
            db.session.commit()

        return jsonify(session.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_api_bp.route("/upload/session/<session_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def cancel_upload(session_id: str):
    """Cancel upload session and delete temporary file.

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    storage = _get_storage()

    try:
        session = db.session.query(UploadSession).filter_by(id=session_id).first()
        if not session:
            return jsonify({"error": "Session not found"}), 404

        # Verify session belongs to user
        if session.user_id != user.id:
            return jsonify({"error": "Permission denied"}), 403

        # Delete temporary file
        storage.delete_temp_file(session_id)

        # Delete session
        db.session.delete(session)
        db.session.commit()

        return jsonify({"message": "Upload session cancelled successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
