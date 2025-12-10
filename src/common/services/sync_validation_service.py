"""Service for validating files before synchronization."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session


class SyncValidationService:
    """Service for validating files before synchronization to prevent malware persistence."""

    def __init__(
        self,
        db_session: Session | None = None,
        File_model: type | None = None,
        logger: logging.Logger | None = None,
    ):
        """Initialize the validation service.

        Args:
            db_session: SQLAlchemy session for database queries. If None, must be set later.
            File_model: File model class for database queries. If None, must be set later.
            logger: Logger instance. If None, uses default logger.
        """
        self._legitimate_files: dict[str, dict[str, Any]] = {}
        self._legitimate_thumbnails: set[str] = set()
        self._loaded = False
        self._db_session = db_session
        self._File_model = File_model
        self._logger = logger or logging.getLogger(__name__)

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
            self._logger.warning(
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
                # The storage_ref is the actual filename in /data/files/
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                # Normalize storage_ref (remove any path prefixes)
                # storage_ref can be in different formats:
                # - Just the filename: "abc123..." (most common case)
                # - Full path: "/data/files/abc123..."
                # - Relative path: "files/abc123..."
                # In practice, storage_ref is stored as just the filename in the database
                normalized_storage_ref = storage_ref.strip()
                if "/" in normalized_storage_ref:
                    # Extract just the filename (handle paths)
                    normalized_storage_ref = normalized_storage_ref.split("/")[-1]

                # Use normalized_storage_ref as the key (this is the filename in /data/files/)
                legitimate_files[normalized_storage_ref] = {
                    "storage_ref": storage_ref,
                    "encrypted_hash": file_obj.encrypted_hash,
                    "size": file_obj.encrypted_size,
                    "file_id": file_id,
                }

            self._logger.info(
                f"Loaded {len(legitimate_files)} legitimate files from database. "
                f"Sample storage_refs: {list(legitimate_files.keys())[:5]}"
            )
            return legitimate_files

        except Exception as e:
            self._logger.error(f"Failed to load legitimate files: {e}", exc_info=True)
            return {}

    def load_legitimate_thumbnails(self) -> set[str]:
        """Load all legitimate thumbnail storage references from PostgreSQL.

        Returns:
            Set of legitimate thumbnail storage references (normalized paths)
        """
        if not self._db_session or not self._File_model:
            self._logger.warning(
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
                    # Format: {"64x64": "storage_ref", "128x128": "storage_ref", ...}
                    # storage_ref is the value returned by get_thumbnail_storage_key()
                    # which is like: "thumbnails/{hash[:2]}/{hash[2:4]}/{hash}_{size}.jpg"
                    thumbnail_refs = json.loads(file_obj.thumbnail_refs)
                    if isinstance(thumbnail_refs, dict):
                        for size_key, storage_ref in thumbnail_refs.items():
                            if storage_ref:
                                # Normalize the storage_ref to handle different formats
                                # Remove leading /data/files/ if present
                                normalized_ref = storage_ref.strip()
                                if normalized_ref.startswith("/data/files/"):
                                    normalized_ref = normalized_ref[
                                        len("/data/files/") :
                                    ]
                                elif normalized_ref.startswith("/"):
                                    normalized_ref = normalized_ref[1:]

                                # Normalize path separators (Windows vs Unix)
                                normalized_ref = normalized_ref.replace("\\", "/")

                                # Add normalized version
                                legitimate_thumbnails.add(normalized_ref)

                except (json.JSONDecodeError, AttributeError) as e:
                    self._logger.debug(
                        f"Failed to parse thumbnail_refs for file {file_obj.id}: {e}"
                    )
                    continue

            self._logger.info(
                f"Loaded {len(legitimate_thumbnails)} legitimate thumbnail references"
            )
            return legitimate_thumbnails

        except Exception as e:
            self._logger.error(
                f"Failed to load legitimate thumbnails: {e}", exc_info=True
            )
            return set()

    def load_whitelist(self) -> None:
        """Load the complete whitelist (files + thumbnails) into memory."""
        if self._loaded:
            return

        self._legitimate_files = self.load_legitimate_files()
        self._legitimate_thumbnails = self.load_legitimate_thumbnails()
        self._loaded = True

        self._logger.info(
            f"Whitelist loaded: {len(self._legitimate_files)} files, "
            f"{len(self._legitimate_thumbnails)} thumbnails"
        )

    def reload_whitelist(self) -> None:
        """Force reload the whitelist from database.

        This is useful after creating new files in the database to ensure
        the whitelist includes the newly created files.
        """
        self._loaded = False
        self.load_whitelist()

    def extract_file_id_from_path(self, file_path: Path, base_dir: Path) -> str | None:
        """Extract file_id from file path.

        Args:
            file_path: Full path to the file
            base_dir: Base directory (/data/files)

        Returns:
            File ID if extractable, None otherwise
        """
        try:
            # Get relative path from base_dir
            relative_path = file_path.relative_to(base_dir)
            parts = relative_path.parts

            if not parts:
                return None

            # Files are stored directly: /data/files/{file_id}
            # Thumbnails are stored: /data/files/thumbnails/{hash[:2]}/{hash[2:4]}/{hash}_{size}.jpg
            # Subdirectories (if any) would be: /data/files/{subdir}/{file_id}
            # For now, assume files are stored directly at the root of /data/files/
            if parts[0] == "thumbnails":
                # This is a thumbnail, return None to handle separately
                return None

            # First part should be the file_id (UUID format, 32 hex characters with hyphens)
            # Files are stored with file_id as filename directly in /data/files/
            file_id = parts[0]

            # Validate that it looks like a UUID (basic check)
            # UUID format: 8-4-4-4-12 hex characters
            if (
                len(file_id) >= 32
                and file_id.replace("-", "").replace("_", "").isalnum()
            ):
                return file_id

            # If it doesn't look like a UUID, it might still be valid (legacy format)
            # Return it anyway and let the whitelist check decide
            return file_id

        except (ValueError, IndexError):
            return None

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file.

        Args:
            file_path: Path to the file

        Returns:
            SHA-256 hash in hex format
        """
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            self._logger.error(f"Failed to compute hash for {file_path}: {e}")
            return ""

    def validate_file(self, file_path: Path, base_dir: Path) -> tuple[bool, str | None]:
        """Validate if a file is legitimate.

        Args:
            file_path: Full path to the file
            base_dir: Base directory (/data/files)

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        try:
            # Use common file validation utility to check path traversal
            # Import here to avoid circular dependencies
            try:
                from vault.utils.file_validation import validate_file_path
            except ImportError:
                # Fallback if vault.utils is not available (e.g., in orchestrator)
                # Basic path validation
                try:
                    file_path.resolve().relative_to(base_dir.resolve())
                except ValueError:
                    return False, "Path traversal detected"
                validate_file_path = lambda p, b: (True, None)

            is_valid_path, path_error = validate_file_path(file_path, base_dir)
            if not is_valid_path:
                return False, path_error

            # Get relative path and normalize it
            relative_path = file_path.relative_to(base_dir)
            normalized_path = str(relative_path).replace("\\", "/")

            # Check if it's a thumbnail first (in thumbnails/ subdirectory)
            if normalized_path.startswith("thumbnails/"):
                # This is a thumbnail, validate it separately
                return self.validate_thumbnail(file_path, base_dir)

            # Extract file_id (should be the first part of the path for regular files)
            file_id = self.extract_file_id_from_path(file_path, base_dir)

            if file_id is None:
                return False, "File ID not extractable from path"

            # Check if file_id exists in whitelist
            if file_id not in self._legitimate_files:
                return False, f"File ID {file_id} not found in database"

            # Get expected metadata
            file_metadata = self._legitimate_files[file_id]

            # Verify hash (cryptographic validation)
            actual_hash = self.compute_file_hash(file_path)
            expected_hash = file_metadata["encrypted_hash"]

            if not expected_hash:
                # If no hash is stored, compute and warn (should not happen in production)
                self._logger.warning(
                    f"File {file_id} has no stored hash - computing and accepting"
                )
            elif actual_hash != expected_hash:
                return (
                    False,
                    f"Hash mismatch for file {file_id}: expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
                )

            # Verify magic bytes (content-based validation)
            # Only check magic bytes if hash validation passed
            # If hash matches, file is valid regardless of magic bytes
            # This check is mainly for detecting unencrypted files when hash is missing
            if not expected_hash:
                # Only check magic bytes if no hash is stored (should not happen in production)
                try:
                    with open(file_path, "rb") as f:
                        magic_bytes = f.read(16)  # Read first 16 bytes

                    # Basic magic bytes validation (can be extended for specific file types)
                    # Encrypted files should not start with common plaintext signatures
                    # This is a basic check - more sophisticated validation can be added
                    plaintext_signatures = [
                        b"PK\x03\x04",  # ZIP files
                        b"\x89PNG",  # PNG images
                        b"GIF89a",  # GIF images
                        b"GIF87a",  # GIF images
                        b"\xff\xd8\xff",  # JPEG images
                        b"%PDF",  # PDF files
                        b"<!DOCTYPE",  # HTML/XML
                        b"<?xml",  # XML
                    ]

                    # If file starts with plaintext signature and is supposed to be encrypted,
                    # this might indicate tampering (unless it's a known format)
                    # For now, we just log a warning but don't reject
                    for sig in plaintext_signatures:
                        if magic_bytes.startswith(sig):
                            self._logger.warning(
                                f"File {file_id} starts with plaintext signature {sig.hex()} - "
                                "may not be encrypted or may be a known format"
                            )
                            break
                except Exception as e:
                    self._logger.warning(
                        f"Failed to read magic bytes for file {file_id}: {e}"
                    )
                    # Don't fail validation if magic bytes check fails

            # Verify file size (optional but recommended)
            actual_size = file_path.stat().st_size
            expected_size = file_metadata["size"]

            if actual_size != expected_size:
                return (
                    False,
                    f"Size mismatch for file {file_id}: expected {expected_size}, got {actual_size}",
                )

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_thumbnail(
        self, file_path: Path, base_dir: Path
    ) -> tuple[bool, str | None]:
        """Validate if a thumbnail is legitimate.

        Args:
            file_path: Full path to the thumbnail
            base_dir: Base directory (/data/files)

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        try:
            # Get relative path and normalize it
            relative_path = file_path.relative_to(base_dir)
            normalized_ref = str(relative_path).replace("\\", "/")

            # Remove leading /data/files/ if present (shouldn't be, but just in case)
            if normalized_ref.startswith("/data/files/"):
                normalized_ref = normalized_ref[len("/data/files/") :]
            elif normalized_ref.startswith("/"):
                normalized_ref = normalized_ref[1:]

            # Check if this normalized path is in the whitelist
            if normalized_ref in self._legitimate_thumbnails:
                return True, None

            return False, f"Thumbnail {normalized_ref} not found in database"

        except Exception as e:
            return False, f"Thumbnail validation error: {str(e)}"

    def is_file_legitimate(
        self, file_path: Path, base_dir: Path
    ) -> tuple[bool, str | None]:
        """Check if a file or thumbnail is legitimate.

        Args:
            file_path: Full path to the file
            base_dir: Base directory (/data/files)

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not self._loaded:
            self.load_whitelist()

        # Check if it's a thumbnail (in thumbnails/ subdirectory)
        try:
            relative_path = file_path.relative_to(base_dir)
            if str(relative_path).startswith("thumbnails/"):
                return self.validate_thumbnail(file_path, base_dir)
            else:
                return self.validate_file(file_path, base_dir)
        except ValueError:
            # Path is not relative to base_dir, which is invalid
            return False, "File path is not within base directory"


__all__ = ["SyncValidationService"]
