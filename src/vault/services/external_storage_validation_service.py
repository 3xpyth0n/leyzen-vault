"""Service for validating files in external S3 storage."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from vault.services.external_storage_service import ExternalStorageService

logger = logging.getLogger(__name__)


class ExternalStorageValidationService:
    """Service for validating files in external S3 storage using whitelist and hash."""

    def __init__(
        self,
        external_storage_service: ExternalStorageService,
        db_session: Session | None = None,
        File_model: type | None = None,
    ):
        """Initialize the validation service.

        Args:
            external_storage_service: ExternalStorageService instance
            db_session: SQLAlchemy session for database queries. If None, must be set later.
            File_model: File model class for database queries. If None, must be set later.
        """
        self.external_storage_service = external_storage_service
        self._legitimate_files: dict[str, dict[str, Any]] = {}
        self._legitimate_thumbnails: set[str] = set()
        self._loaded = False
        self._db_session = db_session
        self._File_model = File_model

    def set_database(self, db_session: Session, File_model: type) -> None:
        """Set database session and model after initialization.

        Args:
            db_session: SQLAlchemy session for database queries
            File_model: File model class for database queries
        """
        self._db_session = db_session
        self._File_model = File_model
        # Reset loaded state to force reload with new database connection
        self._loaded = False

    def load_legitimate_files(self) -> dict[str, dict[str, Any]]:
        """Load all legitimate file IDs and their metadata from PostgreSQL.

        Returns:
            Dictionary mapping file_id to file metadata (storage_ref, encrypted_hash, size)
        """
        if not self._db_session or not self._File_model:
            logger.warning(
                "Database session or File model not set. Cannot load legitimate files."
            )
            return {}

        try:
            # Query all non-deleted files
            files = (
                self._db_session.query(self._File_model)
                .filter(self._File_model.deleted_at.is_(None))
                .all()
            )

            legitimate_files = {}
            for file_obj in files:
                # Use storage_ref as the key (files are stored by storage_ref, not by id)
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                # Normalize storage_ref (remove any path prefixes)
                normalized_storage_ref = storage_ref.strip()
                if "/" in normalized_storage_ref:
                    # Extract just the filename (handle paths)
                    normalized_storage_ref = normalized_storage_ref.split("/")[-1]

                # Use normalized_storage_ref as the key
                legitimate_files[normalized_storage_ref] = {
                    "storage_ref": storage_ref,
                    "encrypted_hash": file_obj.encrypted_hash,
                    "size": file_obj.encrypted_size,
                    "file_id": file_id,
                }

            logger.info(
                f"Loaded {len(legitimate_files)} legitimate files from database for S3 validation."
            )
            return legitimate_files

        except Exception as e:
            logger.error(f"Failed to load legitimate files: {e}", exc_info=True)
            return {}

    def load_legitimate_thumbnails(self) -> set[str]:
        """Load all legitimate thumbnail storage references from PostgreSQL.

        Returns:
            Set of legitimate thumbnail storage references (normalized paths)
        """
        if not self._db_session or not self._File_model:
            logger.warning(
                "Database session or File model not set. Cannot load legitimate thumbnails."
            )
            return set()

        try:
            # Query all files with thumbnails
            files = (
                self._db_session.query(self._File_model)
                .filter(
                    and_(
                        self._File_model.deleted_at.is_(None),
                        self._File_model.thumbnail_refs.isnot(None),
                        self._File_model.has_thumbnail.is_(True),
                    )
                )
                .all()
            )

            legitimate_thumbnails = set()
            for file_obj in files:
                if not file_obj.thumbnail_refs:
                    continue

                try:
                    # Parse thumbnail_refs JSON
                    thumbnail_refs = json.loads(file_obj.thumbnail_refs)
                    if isinstance(thumbnail_refs, dict):
                        for size_key, storage_ref in thumbnail_refs.items():
                            if storage_ref:
                                # Normalize the storage_ref
                                normalized_ref = storage_ref.strip()
                                if normalized_ref.startswith("/data/files/"):
                                    normalized_ref = normalized_ref[
                                        len("/data/files/") :
                                    ]
                                elif normalized_ref.startswith("/"):
                                    normalized_ref = normalized_ref[1:]

                                # Normalize path separators
                                normalized_ref = normalized_ref.replace("\\", "/")

                                # Add normalized version
                                legitimate_thumbnails.add(normalized_ref)

                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(
                        f"Failed to parse thumbnail_refs for file {file_obj.id}: {e}"
                    )
                    continue

            logger.info(
                f"Loaded {len(legitimate_thumbnails)} legitimate thumbnail references for S3 validation"
            )
            return legitimate_thumbnails

        except Exception as e:
            logger.error(f"Failed to load legitimate thumbnails: {e}", exc_info=True)
            return set()

    def load_whitelist(self) -> None:
        """Load the complete whitelist (files + thumbnails) into memory."""
        if self._loaded:
            return

        self._legitimate_files = self.load_legitimate_files()
        self._legitimate_thumbnails = self.load_legitimate_thumbnails()
        self._loaded = True

        logger.info(
            f"Whitelist loaded for S3 validation: {len(self._legitimate_files)} files, "
            f"{len(self._legitimate_thumbnails)} thumbnails"
        )

    def reload_whitelist(self) -> None:
        """Force reload the whitelist from database."""
        self._loaded = False
        self.load_whitelist()

    def compute_file_hash(self, file_data: bytes) -> str:
        """Compute SHA-256 hash of file data.

        Args:
            file_data: File data bytes

        Returns:
            SHA-256 hash in hex format
        """
        return hashlib.sha256(file_data).hexdigest()

    def validate_file(self, file_id: str) -> tuple[bool, str | None]:
        """Validate if a file in S3 is legitimate.

        Args:
            file_id: File identifier (storage_ref)

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not self._loaded:
            self.load_whitelist()

        try:
            # Check if file_id exists in whitelist
            if file_id not in self._legitimate_files:
                return False, f"File ID {file_id} not found in database"

            # Get expected metadata
            file_metadata = self._legitimate_files[file_id]

            # Check if file exists in S3
            if not self.external_storage_service.file_exists(file_id):
                return False, f"File {file_id} not found in S3"

            # Read file from S3 and verify hash
            try:
                file_data = self.external_storage_service.read_file(file_id)
            except Exception as e:
                return False, f"Failed to read file {file_id} from S3: {e}"

            # Verify hash
            actual_hash = self.compute_file_hash(file_data)
            expected_hash = file_metadata["encrypted_hash"]

            if not expected_hash:
                logger.warning(
                    f"File {file_id} has no stored hash - accepting without hash validation"
                )
            elif actual_hash != expected_hash:
                return (
                    False,
                    f"Hash mismatch for file {file_id}: expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
                )

            # Verify file size
            actual_size = len(file_data)
            expected_size = file_metadata["size"]

            if actual_size != expected_size:
                return (
                    False,
                    f"Size mismatch for file {file_id}: expected {expected_size}, got {actual_size}",
                )

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_thumbnail(self, thumbnail_path: str) -> tuple[bool, str | None]:
        """Validate if a thumbnail in S3 is legitimate.

        Args:
            thumbnail_path: Thumbnail path (normalized)

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not self._loaded:
            self.load_whitelist()

        try:
            # Normalize path
            normalized_path = thumbnail_path.strip()
            if normalized_path.startswith("/data/files/"):
                normalized_path = normalized_path[len("/data/files/") :]
            elif normalized_path.startswith("/"):
                normalized_path = normalized_path[1:]

            normalized_path = normalized_path.replace("\\", "/")

            # Check if this normalized path is in the whitelist
            if normalized_path in self._legitimate_thumbnails:
                return True, None

            return False, f"Thumbnail {normalized_path} not found in database"

        except Exception as e:
            return False, f"Thumbnail validation error: {str(e)}"

    def cleanup_orphaned_files(self, dry_run: bool = False) -> dict[str, Any]:
        """Clean up orphaned files from S3.

        Orphaned files are files that exist in S3 but don't have
        a corresponding entry in the database.

        Args:
            dry_run: If True, only report what would be deleted without actually deleting

        Returns:
            Dictionary with cleanup statistics
        """
        # Load whitelist
        self.load_whitelist()

        deleted: list[str] = []
        failed: list[str] = []

        try:
            # List all files in S3
            all_s3_files = self.external_storage_service.list_files(prefix="files/")
            all_s3_thumbnails = self.external_storage_service.list_files(
                prefix="thumbnails/"
            )

            # Validate regular files
            for s3_key in all_s3_files:
                # Extract file_id from S3 key (remove "files/" prefix)
                if not s3_key.startswith("files/"):
                    continue

                file_id = s3_key[len("files/") :]

                # Validate file
                is_valid, error_msg = self.validate_file(file_id)

                if not is_valid:
                    # File is orphaned or invalid - delete it
                    try:
                        if not dry_run:
                            success = self.external_storage_service.delete_file(file_id)
                            if success:
                                logger.info(
                                    f"[CLEANUP] Deleted orphaned file from S3: {file_id}"
                                )
                                deleted.append(file_id)
                            else:
                                failed.append(file_id)
                        else:
                            logger.info(
                                f"[CLEANUP DRY RUN] Would delete orphaned file from S3: {file_id}"
                            )
                            deleted.append(file_id)
                    except Exception as e:
                        logger.error(
                            f"[CLEANUP ERROR] Failed to delete orphaned file {file_id} from S3: {e}"
                        )
                        failed.append(file_id)

            # Validate thumbnails
            for s3_key in all_s3_thumbnails:
                # Extract thumbnail path from S3 key (remove "thumbnails/" prefix)
                if not s3_key.startswith("thumbnails/"):
                    continue

                thumbnail_path = s3_key[len("thumbnails/") :]

                # Validate thumbnail
                is_valid, error_msg = self.validate_thumbnail(thumbnail_path)

                if not is_valid:
                    # Thumbnail is orphaned or invalid - delete it
                    try:
                        if not dry_run:
                            # For thumbnails, we need to extract the file_id from the path
                            # Thumbnail paths are like "thumbnails/{hash[:2]}/{hash[2:4]}/{hash}_{size}.jpg"
                            # We'll use the full path as the identifier
                            success = self.external_storage_service.delete_file(
                                thumbnail_path, is_thumbnail=True
                            )
                            if success:
                                logger.info(
                                    f"[CLEANUP] Deleted orphaned thumbnail from S3: {thumbnail_path}"
                                )
                                deleted.append(thumbnail_path)
                            else:
                                failed.append(thumbnail_path)
                        else:
                            logger.info(
                                f"[CLEANUP DRY RUN] Would delete orphaned thumbnail from S3: {thumbnail_path}"
                            )
                            deleted.append(thumbnail_path)
                    except Exception as e:
                        logger.error(
                            f"[CLEANUP ERROR] Failed to delete orphaned thumbnail {thumbnail_path} from S3: {e}"
                        )
                        failed.append(thumbnail_path)

            result = {
                "deleted": deleted,
                "failed": failed,
                "deleted_count": len(deleted),
                "failed_count": len(failed),
                "dry_run": dry_run,
            }

            if deleted:
                logger.info(
                    f"[CLEANUP] S3 cleanup completed: {len(deleted)} orphaned files {'would be ' if dry_run else ''}deleted"
                )

            return result

        except Exception as e:
            logger.error(f"[CLEANUP ERROR] S3 cleanup failed: {e}", exc_info=True)
            return {
                "deleted": deleted,
                "failed": failed,
                "deleted_count": len(deleted),
                "failed_count": len(failed),
                "dry_run": dry_run,
                "error": str(e),
            }


__all__ = ["ExternalStorageValidationService"]
