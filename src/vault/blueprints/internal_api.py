"""Internal API endpoints for orchestrator operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from vault.extensions import csrf
from vault.services.rate_limiter import RateLimiter
from vault.services.sync_validation_service import SyncValidationService

internal_api_bp = Blueprint("internal_api", __name__, url_prefix="/api/internal")


def _validate_internal_token() -> bool:
    """Validate internal API token from request headers.

    INTERNAL_API_TOKEN is auto-generated from SECRET_KEY if not explicitly set.
    Tokens are generated deterministically, so all services using the same SECRET_KEY
    will generate the same tokens without needing to share or persist them.

    Returns:
        True if token is valid, False otherwise
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header[len("Bearer ") :].strip()

    # Get INTERNAL_API_TOKEN from config (auto-generated from SECRET_KEY if not set)
    expected_token = current_app.config.get("INTERNAL_API_TOKEN")
    if not expected_token:
        # Log error if INTERNAL_API_TOKEN is not available
        current_app.logger.error(
            "INTERNAL_API_TOKEN not configured. Internal API access denied. "
            "Token should be auto-generated from SECRET_KEY."
        )
        return False

    import hmac

    return hmac.compare_digest(token, expected_token)


def _validate_container_name(container_name: str) -> bool:
    """Validate container name format matches SyncService validation.

    Validates that container name:
    - Starts with "vault_web"
    - Followed by a number (1-9 followed by digits)
    - Maximum length of 64 characters
    - No special characters except underscore

    Args:
        container_name: Container name to validate

    Returns:
        True if container name is valid, False otherwise
    """
    import re

    # Maximum length to prevent DoS
    if len(container_name) > 64:
        return False

    # Strict pattern: vault_web followed by number (1-9, then digits)
    # This matches the expected format: vault_web1, vault_web2, etc.
    container_name_pattern = re.compile(r"^vault_web[1-9][0-9]*$")
    return bool(container_name_pattern.match(container_name))


@internal_api_bp.route("/sync", methods=["POST"])
@csrf.exempt  # Internal API, CSRF not needed
def sync_volumes():
    """Synchronize data from /data to /data-source.

    This endpoint is called by the orchestrator to synchronize data from the
    ephemeral tmpfs volume (/data) to the persistent source volume (/data-source)
    before container rotation.

    Request headers:
        Authorization: Bearer <INTERNAL_API_TOKEN>

    Note: INTERNAL_API_TOKEN is auto-generated from SECRET_KEY if not explicitly set.

    Returns:
        JSON with sync status
    """
    # Validate internal token
    if not _validate_internal_token():
        return jsonify({"error": "Unauthorized"}), 401

    # Validate container name if provided in request
    # Container name can come from request body, query params, or Host header
    container_name = None
    try:
        if request.is_json:
            json_data = request.get_json(silent=True)
            if json_data:
                container_name = json_data.get("container_name")
    except Exception:
        # If JSON parsing fails, continue without container name from body
        pass

    if not container_name:
        container_name = request.args.get("container_name")
    if not container_name:
        # Try to extract from Host header (format: container_name:port or container_name)
        host_header = request.headers.get("Host", "")
        if host_header:
            container_name = host_header.split(":")[0]

    if container_name and not _validate_container_name(container_name):
        current_app.logger.warning(
            f"[SYNC SECURITY] Invalid container name format: {container_name}"
        )
        return jsonify({"error": "Invalid container name format"}), 400

    # Rate limiting: max 1 sync per 30 seconds per token
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        # Use token as identifier for rate limiting
        auth_header = request.headers.get("Authorization", "")
        token = (
            auth_header[len("Bearer ") :].strip()
            if auth_header.startswith("Bearer ")
            else "unknown"
        )
        # Use token hash as identifier to avoid storing full token
        import hashlib

        token_id = f"sync:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            token_id, max_attempts=1, window_seconds=60, action_name="internal_sync"
        )
        if not is_allowed:
            current_app.logger.warning(
                f"[SYNC RATE LIMIT] Rate limit exceeded for sync endpoint: {error_msg}"
            )
            return (
                jsonify({"error": "Rate limit exceeded. Please wait before retrying."}),
                429,
            )

    source_dir = Path("/data")
    target_dir = Path("/data-source")

    try:
        # Initialize validation service and load whitelist
        validation_service = SyncValidationService()
        validation_service.load_whitelist()

        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Sync files directory if it exists
        source_files = source_dir / "files"
        target_files = target_dir / "files"

        files_synced = 0
        files_rejected = 0
        files_deleted = 0

        if source_files.exists() and source_files.is_dir():
            # Create target directory if it doesn't exist
            target_files.mkdir(parents=True, exist_ok=True)

            # Recursively validate and sync directory from source to target
            def sync_directory_validated(
                src: Path, dst: Path, base_dir: Path
            ) -> tuple[int, int, int]:
                """Recursively validate and sync directory from src to dst.

                Returns:
                    Tuple of (files_synced, files_rejected, files_deleted)
                """
                synced = 0
                rejected = 0
                deleted = 0

                if not dst.exists():
                    dst.mkdir(parents=True, exist_ok=True)

                for item in src.iterdir():
                    src_item = src / item.name
                    dst_item = dst / item.name

                    if src_item.is_dir():
                        # Recursively sync subdirectories
                        sub_synced, sub_rejected, sub_deleted = (
                            sync_directory_validated(src_item, dst_item, base_dir)
                        )
                        synced += sub_synced
                        rejected += sub_rejected
                        deleted += sub_deleted
                    else:
                        # Validate file before synchronizing
                        is_valid, error_msg = validation_service.is_file_legitimate(
                            src_item, base_dir
                        )

                        if is_valid:
                            # File is legitimate, synchronize it atomically
                            try:
                                # Copy file if it doesn't exist or if source is newer
                                if not dst_item.exists() or (
                                    src_item.stat().st_mtime > dst_item.stat().st_mtime
                                ):
                                    # Use temporary file for atomic operation to prevent race conditions
                                    temp_file = None
                                    try:
                                        # Create temporary file in the same directory to guarantee same filesystem
                                        temp_fd, temp_path = tempfile.mkstemp(
                                            dir=dst.parent,
                                            prefix=".sync_",
                                            suffix=".tmp",
                                        )
                                        temp_file = Path(temp_path)
                                        os.close(temp_fd)

                                        # Copy to temporary file
                                        shutil.copy2(src_item, temp_file)

                                        # Re-validate after copy (protection against race condition)
                                        is_still_valid, revalidation_error = (
                                            validation_service.is_file_legitimate(
                                                temp_file, base_dir
                                            )
                                        )

                                        if is_still_valid:
                                            # Atomically rename (atomic operation on same filesystem)
                                            temp_file.rename(dst_item)
                                            synced += 1
                                            current_app.logger.info(
                                                f"[SYNC VALID] Synchronized legitimate file: {src_item.relative_to(base_dir)}"
                                            )
                                        else:
                                            # File became invalid during sync, delete it
                                            temp_file.unlink()
                                            deleted += 1
                                            current_app.logger.warning(
                                                f"[SYNC SECURITY] File became invalid during sync: {src_item.relative_to(base_dir)} "
                                                f"(reason: {revalidation_error})"
                                            )
                                    except Exception as e:
                                        if temp_file and temp_file.exists():
                                            temp_file.unlink()
                                        raise
                            except Exception as e:
                                current_app.logger.error(
                                    f"[SYNC ERROR] Failed to copy file {src_item}: {e}"
                                )
                                rejected += 1
                        else:
                            # File is suspicious, delete it immediately
                            try:
                                file_size = src_item.stat().st_size
                                file_hash = validation_service.compute_file_hash(
                                    src_item
                                )

                                # Delete the suspicious file
                                src_item.unlink()
                                deleted += 1

                                current_app.logger.warning(
                                    f"[SYNC SECURITY] Deleted suspicious file: {src_item.relative_to(base_dir)} "
                                    f"(reason: {error_msg}, size: {file_size}, hash_prefix: {file_hash[:8]}...)"
                                )

                                # Also log as error for alerting
                                current_app.logger.error(
                                    f"[SYNC SECURITY ALERT] Suspicious file deleted during sync: "
                                    f"path={src_item.relative_to(base_dir)}, "
                                    f"reason={error_msg}, size={file_size}, hash_prefix: {file_hash[:8]}..."
                                )
                            except Exception as e:
                                current_app.logger.error(
                                    f"[SYNC ERROR] Failed to delete suspicious file {src_item}: {e}"
                                )
                                rejected += 1

                return synced, rejected, deleted

            files_synced, files_rejected, files_deleted = sync_directory_validated(
                source_files, target_files, source_files
            )

            current_app.logger.info(
                f"Successfully synchronized {files_synced} legitimate files from {source_files} to {target_files}, "
                f"rejected {files_rejected} files, deleted {files_deleted} suspicious files"
            )
        else:
            # Source directory doesn't exist, which is fine (no files to sync)
            current_app.logger.info("No files directory to sync")

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Synchronization completed",
                    "files_synced": files_synced,
                    "files_rejected": files_rejected,
                    "files_deleted": files_deleted,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Failed to synchronize volumes: {e}", exc_info=True)
        return jsonify({"error": f"Synchronization failed: {str(e)}"}), 500


__all__ = ["internal_api_bp"]
