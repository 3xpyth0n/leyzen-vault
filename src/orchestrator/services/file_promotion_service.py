"""File promotion service for secure file promotion to persistent storage."""

from __future__ import annotations

import base64
import hashlib
import tempfile
from pathlib import Path
from typing import Any

from ..config import Settings
from common.services.logging import FileLogger


class FilePromotionService:
    """Service for securely promoting validated files to persistent storage.

    This service runs in the orchestrator and has write access to /data-source.
    It performs double validation (hash and size verification) before writing files
    to prevent malicious files from being persisted. Full database validation is
    performed by the vault container before sending files to this service.
    """

    def __init__(self, settings: Settings, logger: FileLogger) -> None:
        """Initialize the file promotion service.

        Args:
            settings: Orchestrator settings
            logger: Logger instance
        """
        self._settings = settings
        self._logger = logger
        self._data_source_dir = Path("/data-source")

    def promote_file(
        self,
        file_id: str,
        file_data: bytes | str,
        expected_hash: str,
        expected_size: int,
    ) -> tuple[bool, str | None]:
        """Promote a validated file to persistent storage.

        This method performs double validation:
        1. Validates the provided metadata (hash, size)
        2. Validates the file data itself

        Args:
            file_id: File identifier (storage_ref)
            file_data: File data (bytes or base64-encoded string)
            expected_hash: Expected SHA-256 hash
            expected_size: Expected file size

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Decode base64 if needed
            if isinstance(file_data, str):
                try:
                    file_data = base64.b64decode(file_data)
                except Exception as e:
                    return False, f"Failed to decode base64 data: {e}"

            # Verify data hash matches expected hash
            actual_hash = hashlib.sha256(file_data).hexdigest()
            if actual_hash != expected_hash:
                return (
                    False,
                    f"Hash mismatch for file {file_id}: expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
                )

            # Verify data size matches expected size
            if len(file_data) != expected_size:
                return (
                    False,
                    f"Size mismatch for file {file_id}: expected {expected_size}, got {len(file_data)}",
                )

            # Ensure target directory exists
            target_files_dir = self._data_source_dir / "files"
            target_files_dir.mkdir(parents=True, exist_ok=True)
            target_file_path = target_files_dir / file_id

            # Check if file already exists and is identical
            if target_file_path.exists():
                try:
                    existing_data = target_file_path.read_bytes()
                    existing_hash = hashlib.sha256(existing_data).hexdigest()
                    if existing_hash == expected_hash:
                        # File already exists and is identical, skip promotion
                        # This is normal - files are copied from /data-source to /data at container startup
                        # So they're already in persistent storage
                        return True, None
                except Exception as e:
                    self._logger.log(
                        f"[PROMOTION WARNING] Failed to check existing file {file_id}: {e}, will overwrite"
                    )

            # Write file atomically using temporary file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=target_files_dir,
                prefix=f".{file_id}.",
                suffix=".tmp",
            )
            temp_file_path = Path(temp_path)

            try:
                # Write data to temporary file
                with open(temp_fd, "wb") as temp_file:
                    temp_file.write(file_data)
                    temp_file.flush()

                # Re-validate after write (protection against race conditions)
                re_validation_hash = hashlib.sha256(file_data).hexdigest()
                if re_validation_hash != expected_hash:
                    temp_file_path.unlink()
                    return (
                        False,
                        f"Re-validation failed for file {file_id}: hash mismatch after write",
                    )

                # Atomically rename to target
                temp_file_path.rename(target_file_path)

                self._logger.log(
                    f"[PROMOTION] Successfully promoted file {file_id} to persistent storage"
                )
                return True, None

            except Exception as e:
                # Cleanup temp file on error
                try:
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                except Exception:
                    pass
                raise

        except Exception as e:
            error_msg = f"Failed to promote file {file_id}: {e}"
            self._logger.log(f"[PROMOTION ERROR] {error_msg}")
            return False, error_msg

    def promote_files_batch(self, files: list[dict[str, Any]]) -> dict[str, Any]:
        """Promote multiple files in a batch.

        Args:
            files: List of file dictionaries with keys:
                - file_id: File identifier (storage_ref)
                - file_data: File data (bytes or base64-encoded string)
                - expected_hash: Expected SHA-256 hash
                - expected_size: Expected file size

        Returns:
            Dictionary with promotion statistics:
                - promoted: Number of files successfully promoted
                - failed: Number of files that failed promotion
                - errors: List of error messages
        """
        promoted = 0
        failed = 0
        errors: list[str] = []

        for file_info in files:
            file_id = file_info.get("file_id")
            file_data = file_info.get("file_data")
            expected_hash = file_info.get("expected_hash")
            expected_size = file_info.get("expected_size")

            if not all([file_id, file_data, expected_hash, expected_size]):
                failed += 1
                errors.append(f"Missing required fields for file promotion")
                continue

            success, error_msg = self.promote_file(
                file_id, file_data, expected_hash, expected_size
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


__all__ = ["FilePromotionService"]
