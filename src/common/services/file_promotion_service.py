"""Unified file promotion service for persistent storage.

This service handles promotion of legitimate files from tmpfs (/data) to persistent
storage (/data-source) with strict validation. It can be used by both the vault
(after each upload) and the orchestrator (during rotation).
"""

from __future__ import annotations

import fcntl
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from common.services.sync_validation_service import SyncValidationService

logger = logging.getLogger(__name__)


class FilePromotionService:
    """Unified service for promoting validated files to persistent storage.

    This service validates files using SyncValidationService (checks file ID exists
    in database AND hash matches) before promoting them to persistent storage.
    It also handles cleanup of orphaned files (files that don't exist in database).
    """

    def __init__(
        self,
        validation_service: SyncValidationService,
        logger_instance: logging.Logger | None = None,
    ):
        """Initialize the promotion service.

        Args:
            validation_service: SyncValidationService instance for file validation
            logger_instance: Logger instance. If None, uses default logger.
        """
        self.validation_service = validation_service
        self._logger = logger_instance or logger

    def promote_file(
        self,
        file_id: str,
        source_path: Path,
        target_dir: Path,
        base_dir: Path | None = None,
    ) -> tuple[bool, str | None]:
        """Promote a file from tmpfs to persistent storage with validation.

        This method validates the file (checks it exists in database and hash matches)
        before promoting it. If validation fails, the file is rejected.

        Args:
            file_id: File identifier (storage_ref)
            source_path: Path to the file in tmpfs (/data/files/{file_id})
            target_dir: Target directory for persistent storage (/data-source)
            base_dir: Base directory for validation (defaults to source_path.parent)

        Returns:
            Tuple of (success, error_message). If successful, error_message is None.
        """
        if not source_path.exists():
            self._logger.warning(
                f"[PROMOTION] File {file_id} not found at {source_path}"
            )
            return False, f"File {file_id} not found at {source_path}"

        if not target_dir:
            self._logger.warning(
                f"[PROMOTION] Target directory not configured for file {file_id}"
            )
            return False, "Target directory not configured"

        self._logger.info(
            f"[PROMOTION] Starting promotion for file {file_id} from {source_path}"
        )

        # Force reload whitelist to include newly created file in DB
        # The whitelist is cached, so we need to reload it after the file was created
        self.validation_service.reload_whitelist()

        # Validate file before promotion
        if base_dir is None:
            base_dir = source_path.parent

        is_valid, error_msg = self.validation_service.is_file_legitimate(
            source_path, base_dir
        )

        if not is_valid:
            # File is not legitimate - delete it immediately for security
            self._logger.error(
                f"[PROMOTION SECURITY] File {file_id} failed validation: {error_msg}"
            )
            try:
                source_path.unlink()
                self._logger.warning(
                    f"[PROMOTION SECURITY] Rejected and deleted invalid file {file_id}: {error_msg}"
                )
            except Exception as e:
                self._logger.error(
                    f"[PROMOTION ERROR] Failed to delete invalid file {file_id}: {e}"
                )
            return False, f"Validation failed: {error_msg}"

        # File is legitimate - promote it atomically
        # Use the same logic as sync_volumes which works correctly
        try:
            # Prepare target directory
            target_files_dir = target_dir / "files"
            target_files_dir.mkdir(parents=True, exist_ok=True)
            target_file_path = target_files_dir / file_id

            # Copy file if it doesn't exist or if source is newer
            if not target_file_path.exists() or (
                source_path.stat().st_mtime > target_file_path.stat().st_mtime
            ):
                # Use temporary file for atomic operation (same as sync_volumes)
                temp_file = None
                try:
                    # Create temporary file in the same directory to guarantee same filesystem
                    temp_fd, temp_path = tempfile.mkstemp(
                        dir=target_files_dir,
                        prefix=".promote_",
                        suffix=".tmp",
                    )
                    temp_file = Path(temp_path)
                    os.close(temp_fd)

                    # Copy to temporary file (same as sync_volumes)
                    # Use copy2 to preserve metadata (same as sync_volumes)
                    shutil.copy2(source_path, temp_file)

                    # Re-validate after copy (protection against race condition)
                    # The temp file has a different name, so we can't extract file_id from it.
                    # Instead, we validate by checking the hash directly against the whitelist.
                    # We already validated the source file, so we just need to verify the
                    # temp file hash matches the expected hash.
                    import hashlib

                    temp_hash = self.validation_service.compute_file_hash(temp_file)
                    temp_size = temp_file.stat().st_size

                    # Check if file_id exists in whitelist and hash/size match
                    if file_id not in self.validation_service._legitimate_files:
                        is_still_valid = False
                        revalidation_error = (
                            f"File ID {file_id} not found in database after copy"
                        )
                    else:
                        file_metadata = self.validation_service._legitimate_files[
                            file_id
                        ]
                        expected_hash = file_metadata["encrypted_hash"]
                        expected_size = file_metadata["size"]

                        if temp_hash != expected_hash:
                            is_still_valid = False
                            revalidation_error = f"Hash mismatch after copy: expected {expected_hash[:16]}..., got {temp_hash[:16]}..."
                        elif temp_size != expected_size:
                            is_still_valid = False
                            revalidation_error = f"Size mismatch after copy: expected {expected_size}, got {temp_size}"
                        else:
                            is_still_valid = True
                            revalidation_error = None

                    if is_still_valid:
                        # Atomically rename (atomic operation on same filesystem)
                        temp_file.rename(target_file_path)
                        self._logger.info(
                            f"[PROMOTION] Successfully promoted file {file_id} to persistent storage at {target_file_path} "
                            f"(size: {target_file_path.stat().st_size} bytes)"
                        )
                        return True, None
                    else:
                        # File became invalid during promotion - delete it
                        temp_file.unlink()
                        self._logger.warning(
                            f"[PROMOTION SECURITY] File {file_id} became invalid during promotion: {revalidation_error}"
                        )
                        return False, f"Revalidation failed: {revalidation_error}"
                except Exception as e:
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    raise
            else:
                # File already exists and is up to date
                self._logger.info(
                    f"[PROMOTION] File {file_id} already exists in persistent storage and is up to date"
                )
                return True, None

        except Exception as e:
            self._logger.error(
                f"[PROMOTION ERROR] Failed to promote file {file_id}: {e}",
                exc_info=True,
            )
            return False, f"Promotion failed: {str(e)}"

    def promote_files_batch(
        self,
        files: list[dict[str, Any]],
        source_dir: Path,
        target_dir: Path,
        base_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Promote multiple files in a batch.

        Args:
            files: List of file dictionaries with keys:
                - file_id: File identifier (storage_ref)
            source_dir: Source directory containing files (/data/files)
            target_dir: Target directory for persistent storage (/data-source)
            base_dir: Base directory for validation (defaults to source_dir)

        Returns:
            Dictionary with promotion statistics:
                - promoted: Number of files successfully promoted
                - failed: Number of files that failed promotion
                - errors: List of error messages
        """
        if base_dir is None:
            base_dir = source_dir

        promoted = 0
        failed = 0
        errors: list[str] = []

        for file_info in files:
            file_id = file_info.get("file_id")
            if not file_id:
                failed += 1
                errors.append("Missing file_id in file info")
                continue

            source_path = source_dir / file_id
            success, error_msg = self.promote_file(
                file_id, source_path, target_dir, base_dir
            )

            if success:
                promoted += 1
            else:
                failed += 1
                errors.append(f"File {file_id}: {error_msg}")

        return {
            "promoted": promoted,
            "failed": failed,
            "errors": errors,
        }

    def cleanup_orphaned_files(
        self,
        target_dir: Path,
        base_dir: Path | None = None,
        dry_run: bool = False,
        lock_timeout: int = 300,
    ) -> dict[str, Any]:
        """Clean up orphaned files from persistent storage.

        Orphaned files are files that exist in /data-source but don't have
        a corresponding entry in the database.

        This method uses file locking to prevent conflicts between multiple
        cleanup workers (vault and orchestrator).

        Args:
            target_dir: Target directory to clean up (/data-source)
            base_dir: Base directory for validation (defaults to target_dir / "files")
            dry_run: If True, only report what would be deleted without actually deleting
            lock_timeout: Lock timeout in seconds (default: 5 minutes)

        Returns:
            Dictionary with cleanup statistics
        """
        if not target_dir:
            return {
                "deleted": [],
                "failed": [],
                "deleted_count": 0,
                "failed_count": 0,
            }

        # Load whitelist
        self.validation_service.load_whitelist()

        target_files_dir = target_dir / "files"
        if not target_files_dir.exists():
            return {
                "deleted": [],
                "failed": [],
                "deleted_count": 0,
                "failed_count": 0,
            }

        if base_dir is None:
            base_dir = target_files_dir

        # Use file locking to prevent conflicts between workers
        lock_file = target_dir / ".cleanup.lock"
        lock_acquired = False

        try:
            # Try to acquire lock
            lock_acquired = self._acquire_lock(lock_file, lock_timeout)
            if not lock_acquired:
                self._logger.info(
                    "[CLEANUP] Another cleanup process is running, skipping this run"
                )
                return {
                    "deleted": [],
                    "failed": [],
                    "deleted_count": 0,
                    "failed_count": 0,
                    "skipped": True,
                }

            deleted: list[str] = []
            failed: list[str] = []

            # Recursively check all files in target storage
            def cleanup_directory(directory: Path) -> None:
                """Recursively clean up orphaned files in directory."""
                if not directory.exists():
                    return

                for item in directory.iterdir():
                    if item.is_dir():
                        # Recursively process subdirectories
                        cleanup_directory(item)
                    else:
                        # Skip lock file and temp files
                        if item.name.startswith(
                            ".cleanup.lock"
                        ) or item.name.startswith(".promote_"):
                            continue

                        # Validate file
                        is_valid, error_msg = (
                            self.validation_service.is_file_legitimate(item, base_dir)
                        )

                        if not is_valid:
                            # File is orphaned or invalid - delete it
                            file_id = item.name
                            try:
                                if not dry_run:
                                    item.unlink()
                                    self._logger.info(
                                        f"[CLEANUP] Deleted orphaned file: {item.relative_to(target_files_dir)}"
                                    )
                                else:
                                    self._logger.info(
                                        f"[CLEANUP DRY RUN] Would delete orphaned file: {item.relative_to(target_files_dir)}"
                                    )
                                deleted.append(str(item.relative_to(target_files_dir)))
                            except Exception as e:
                                self._logger.error(
                                    f"[CLEANUP ERROR] Failed to delete orphaned file {item}: {e}"
                                )
                                failed.append(str(item.relative_to(target_files_dir)))

            cleanup_directory(target_files_dir)

            result = {
                "deleted": deleted,
                "failed": failed,
                "deleted_count": len(deleted),
                "failed_count": len(failed),
                "dry_run": dry_run,
            }

            if deleted:
                self._logger.info(
                    f"[CLEANUP] Cleanup completed: {len(deleted)} orphaned files {'would be ' if dry_run else ''}deleted"
                )

            return result

        finally:
            # Release lock
            if lock_acquired:
                self._release_lock(lock_file)

    def _acquire_lock(self, lock_file: Path, timeout: int) -> bool:
        """Acquire a file lock for cleanup operations.

        Args:
            lock_file: Path to the lock file
            timeout: Lock timeout in seconds

        Returns:
            True if lock was acquired, False otherwise
        """
        try:
            # Check if lock file exists and is stale
            if lock_file.exists():
                lock_age = time.time() - lock_file.stat().st_mtime
                if lock_age > timeout:
                    # Lock is stale, remove it
                    self._logger.warning(
                        f"[CLEANUP] Removing stale lock file (age: {lock_age:.0f}s)"
                    )
                    try:
                        lock_file.unlink()
                    except Exception as e:
                        self._logger.error(
                            f"[CLEANUP] Failed to remove stale lock: {e}"
                        )
                        return False

            # Create lock file
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_WRONLY | os.O_EXCL)

            try:
                # Try to acquire exclusive lock
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID to lock file for debugging
                os.write(lock_fd, str(os.getpid()).encode())
                os.fsync(lock_fd)
                return True
            except (IOError, OSError):
                # Lock is held by another process
                os.close(lock_fd)
                return False

        except Exception as e:
            self._logger.error(f"[CLEANUP] Failed to acquire lock: {e}")
            return False

    def _release_lock(self, lock_file: Path) -> None:
        """Release a file lock.

        Args:
            lock_file: Path to the lock file
        """
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            self._logger.warning(f"[CLEANUP] Failed to release lock: {e}")


__all__ = ["FilePromotionService"]
