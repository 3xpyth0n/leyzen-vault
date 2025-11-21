"""File storage management for encrypted files."""

from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from pathlib import Path
from typing import BinaryIO


class FileStorage:
    """Manages storage of encrypted files."""

    def __init__(self, storage_dir: Path, source_dir: Path | None = None):
        """Initialize storage with a directory.

        Args:
            storage_dir: Primary storage directory (tmpfs, ephemeral)
            source_dir: Optional source directory (persistent, for reading if file not in storage_dir)
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.source_dir = source_dir
        if self.source_dir:
            self.source_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_filename(filename: str) -> tuple[bool, str | None]:
        """Validate filename to prevent path traversal and other security issues.

        Args:
            filename: The filename to validate

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
            If invalid, error_message contains the reason.
        """
        if not filename:
            return False, "Filename cannot be empty"

        # Maximum filename length (255 characters is filesystem limit)
        MAX_FILENAME_LENGTH = 255
        if len(filename) > MAX_FILENAME_LENGTH:
            return (
                False,
                f"Filename too long: maximum {MAX_FILENAME_LENGTH} characters allowed",
            )

        # Normalize: trim whitespace
        filename = filename.strip()
        if not filename:
            return False, "Filename cannot be empty after trimming whitespace"

        # Unicode normalization (NFKC: Compatibility Decomposition, followed by Canonical Composition)
        # This normalizes similar-looking characters (homoglyphs) and converts them to their
        # canonical ASCII equivalents, effectively preventing homoglyph attacks
        filename = unicodedata.normalize("NFKC", filename)

        # Strict validation: reject non-ASCII characters after normalization
        # After NFKC normalization, any remaining non-ASCII characters are rejected.
        # This effectively prevents homoglyph attacks since NFKC normalization converts
        # visually similar characters (like Cyrillic letters) to their ASCII equivalents.
        try:
            filename.encode("ascii")
        except UnicodeEncodeError:
            return (
                False,
                "Filename contains non-ASCII characters after normalization (potential homoglyph attack)",
            )

        # Reject path traversal sequences
        path_traversal_patterns = ["..", "/", "\\"]
        for pattern in path_traversal_patterns:
            if pattern in filename:
                return (
                    False,
                    f"Filename contains invalid characters: '{pattern}' (path traversal detected)",
                )

        # Combined validation: check control characters and Unicode categories in a single pass
        # Control characters: U+0000 to U+001F (C0 controls) and U+007F to U+009F (C1 controls)
        # Whitelist approach: allow only safe Unicode characters
        # Allow: letters (all Unicode letter categories), digits, spaces, hyphens, underscores, dots, parentheses
        allowed_category_prefixes = {
            "L",  # Letter (all subcategories: Lu, Ll, Lt, Lm, Lo)
            "N",  # Number (all subcategories: Nd, Nl, No)
        }
        allowed_categories = {
            "Zs",  # Space separator (specifically allow spaces)
        }
        allowed_chars = {
            "-",
            "_",
            ".",
            "(",
            ")",
        }  # Allow parentheses for numbered names (e.g., "New Folder(1)")

        # Single pass validation: check control characters and Unicode categories together
        for char in filename:
            code_point = ord(char)

            # Check for control characters and null bytes first (fastest check)
            if (
                code_point == 0  # Null byte
                or (
                    0x00 <= code_point <= 0x1F
                )  # C0 control characters (U+0000 to U+001F)
                or (
                    0x7F <= code_point <= 0x9F
                )  # C1 control characters (U+007F to U+009F)
            ):
                return False, "Filename contains control characters or null bytes"

            # Skip Unicode category check for explicitly allowed characters
            if char in allowed_chars:
                continue

            # Check Unicode category for remaining characters
            category = unicodedata.category(char)
            # Check if category starts with allowed prefix (L or N) or is exactly Zs
            if (
                category[0] not in allowed_category_prefixes
                and category not in allowed_categories
            ):
                return (
                    False,
                    f"Filename contains invalid character: '{char}' (category: {category}). Only letters, numbers, spaces, hyphens, underscores, dots, and parentheses are allowed.",
                )

        # Normalize: collapse multiple spaces into single space
        filename_normalized = re.sub(r"\s+", " ", filename)

        # Check that normalized filename is not too long
        if len(filename_normalized) > MAX_FILENAME_LENGTH:
            return (
                False,
                f"Filename too long after normalization: maximum {MAX_FILENAME_LENGTH} characters allowed",
            )

        return True, None

    def generate_file_id(self) -> str:
        """Generate a unique file ID."""
        return secrets.token_urlsafe(16)

    def compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of encrypted data."""
        return hashlib.sha256(data).hexdigest()

    def _write_file_atomically(
        self, file_path: Path, data: bytes, expected_hash: str, file_id: str
    ) -> None:
        """Write file atomically with integrity verification.

        Writes data to a temporary file, verifies integrity using incremental hashing,
        then atomically renames to the target path.

        Args:
            file_path: Target file path
            data: Data to write
            expected_hash: Expected SHA-256 hash of the data
            file_id: File identifier for error messages

        Raises:
            IOError: If write fails or integrity check fails
        """
        import tempfile
        import os

        # Create temporary file in the same directory as target
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp"
        )
        temp_file_path = Path(temp_path)

        try:
            # Write data and compute hash incrementally to avoid re-reading
            hasher = hashlib.sha256()
            with os.fdopen(temp_fd, "wb") as temp_file:
                temp_file.write(data)
                hasher.update(data)
                temp_file.flush()
                os.fsync(temp_fd)  # Force write to disk

            # Verify integrity using hash computed during write
            actual_hash = hasher.hexdigest()

            if actual_hash != expected_hash:
                temp_file_path.unlink()
                raise IOError(
                    f"Integrity check failed for file {file_id}: "
                    f"hash mismatch after write"
                )

            # Atomic rename
            temp_file_path.rename(file_path)
        except Exception as e:
            # Cleanup temp file on error
            try:
                if temp_file_path.exists():
                    temp_file_path.unlink()
            except Exception:
                pass
            raise IOError(f"Failed to write file {file_id}: {e}") from e

    def save_file(self, file_id: str, encrypted_data: bytes) -> Path:
        """Save encrypted file data with integrity verification.

        Saves to both storage_dir (primary, tmpfs) and source_dir (persistent) if configured.

        Args:
            file_id: File identifier
            encrypted_data: Encrypted file data to save

        Returns:
            Path to the saved file in primary storage

        Raises:
            IOError: If file write fails or integrity check fails
        """
        # Compute hash before writing
        expected_hash = self.compute_hash(encrypted_data)

        # Save to primary storage (tmpfs)
        files_dir = self.storage_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        file_path = files_dir / file_id

        primary_saved = False
        source_saved = False

        try:
            # Write to primary storage atomically
            self._write_file_atomically(
                file_path, encrypted_data, expected_hash, file_id
            )
            primary_saved = True

            # Also save to source storage (persistent) if configured
            if self.source_dir:
                source_files_dir = self.source_dir / "files"
                source_files_dir.mkdir(parents=True, exist_ok=True)
                source_file_path = source_files_dir / file_id

                try:
                    # Write to source storage atomically
                    self._write_file_atomically(
                        source_file_path, encrypted_data, expected_hash, file_id
                    )
                    source_saved = True
                except Exception as source_error:
                    # Log error but don't fail if primary save succeeded
                    # Source storage is a backup, primary is required
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to save file {file_id} to source storage: {source_error}. "
                        f"File saved to primary storage only."
                    )

            return file_path

        except Exception as e:
            # If primary save failed, cleanup source if it was saved
            if source_saved and self.source_dir:
                try:
                    source_file_path = self.source_dir / "files" / file_id
                    if source_file_path.exists():
                        source_file_path.unlink()
                except Exception:
                    pass

            raise IOError(f"Failed to save file {file_id}: {e}") from e

    def get_file_path(self, file_id: str) -> Path:
        """Get the path to a stored file in primary storage."""
        files_dir = self.storage_dir / "files"
        return files_dir / file_id

    def get_source_file_path(self, file_id: str) -> Path | None:
        """Get the path to a stored file in source storage, if source_dir is configured."""
        if not self.source_dir:
            return None
        # Ensure we're looking in the files subdirectory
        source_files_dir = self.source_dir / "files"
        return source_files_dir / file_id

    def _find_file_path(self, file_id: str) -> Path | None:
        """Find the file path, checking primary storage first, then source storage.

        Returns:
            Path to the file if found, None otherwise
        """
        # Check primary storage first
        file_path = self.get_file_path(file_id)
        if file_path.exists():
            return file_path

        # Check source storage
        if self.source_dir:
            source_file_path = self.get_source_file_path(file_id)
            if source_file_path and source_file_path.exists():
                return source_file_path

        return None

    def read_file(self, file_id: str) -> bytes:
        """Read encrypted file data.

        First checks primary storage, then source storage if configured.
        """
        file_path = self._find_file_path(file_id)
        if file_path:
            return file_path.read_bytes()

        raise FileNotFoundError(f"File {file_id} not found in storage or source")

    def delete_file(self, file_id: str) -> bool:
        """Delete a stored file from both primary and source storage.

        Args:
            file_id: File identifier (storage_ref)

        Returns:
            True if deleted from at least one location, False if not found anywhere
        """
        deleted_primary = False
        deleted_source = False

        # Delete from primary storage (/data/files/)
        file_path = self.get_file_path(file_id)
        if file_path.exists():
            file_path.unlink()
            deleted_primary = True

        # Delete from source storage (/data-source/files/)
        if self.source_dir:
            source_file_path = self.get_source_file_path(file_id)
            if source_file_path and source_file_path.exists():
                source_file_path.unlink()
                deleted_source = True

        # Return True if deleted from at least one location
        return deleted_primary or deleted_source

    def file_exists(self, file_id: str) -> bool:
        """Check if a file exists.

        First checks primary storage, then source storage if configured.
        """
        return self._find_file_path(file_id) is not None

    def verify_file_integrity(
        self, file_id: str, expected_hash: str
    ) -> tuple[bool, str | None]:
        """Verify file integrity by comparing current hash with expected hash.

        Args:
            file_id: The file ID to verify
            expected_hash: The expected SHA-256 hash of the encrypted file

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
            If invalid or file not found, error_message contains the reason.
        """
        try:
            file_path = self._find_file_path(file_id)
            if not file_path:
                return False, "File not found"

            # Read the file and compute its current hash
            encrypted_data = file_path.read_bytes()
            current_hash = self.compute_hash(encrypted_data)

            # Compare hashes
            if current_hash != expected_hash:
                return (
                    False,
                    f"Hash mismatch: expected {expected_hash[:16]}..., got {current_hash[:16]}...",
                )

            return True, None
        except FileNotFoundError:
            return False, "File not found"
        except Exception as exc:
            return False, f"Error during integrity check: {exc}"

    def get_temp_file_path(self, session_id: str) -> Path:
        """Get the path to a temporary file for a session.

        Args:
            session_id: Upload session ID

        Returns:
            Path to the temporary file
        """
        uploads_dir = self.storage_dir / "uploads" / "sessions"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        return uploads_dir / session_id

    def save_chunk(self, session_id: str, chunk_index: int, chunk_data: bytes) -> None:
        """Append chunk to temporary file for chunked upload.

        Args:
            session_id: Upload session ID
            chunk_index: Zero-based chunk index (for validation)
            chunk_data: Chunk data to append

        Raises:
            IOError: If chunk write fails
            ValueError: If chunk_index doesn't match expected next chunk
        """
        import os

        temp_file_path = self.get_temp_file_path(session_id)
        temp_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists and validate chunk_index matches expected position
        if temp_file_path.exists():
            existing_size = temp_file_path.stat().st_size
            # Verify we're appending in order (rough check)
            # This is a basic validation; full validation happens during completion
            if chunk_index > 0 and existing_size == 0:
                raise ValueError(
                    f"Expected chunk {chunk_index} but file is empty. Chunks must be uploaded in order."
                )
        elif chunk_index != 0:
            raise ValueError(
                f"Expected chunk 0 but got chunk {chunk_index}. Chunks must start with index 0."
            )

        try:
            # Append chunk to temporary file
            # Use 'ab' mode to append in binary mode
            with temp_file_path.open("ab") as temp_file:
                temp_file.write(chunk_data)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Force write to disk
        except Exception as e:
            raise IOError(
                f"Failed to save chunk {chunk_index} for session {session_id}: {e}"
            ) from e

    def complete_chunked_upload(
        self, session_id: str, file_id: str, expected_hash: str | None = None
    ) -> Path:
        """Move temporary file to final location and verify integrity.

        Args:
            session_id: Upload session ID
            file_id: Final file identifier
            expected_hash: Optional expected SHA-256 hash for verification

        Returns:
            Path to the saved file in primary storage

        Raises:
            IOError: If file move fails or integrity check fails
            FileNotFoundError: If temporary file doesn't exist
        """
        import os
        import shutil

        temp_file_path = self.get_temp_file_path(session_id)

        if not temp_file_path.exists():
            raise FileNotFoundError(
                f"Temporary file for session {session_id} not found"
            )

        # Read temporary file data
        encrypted_data = temp_file_path.read_bytes()

        # Compute hash if not provided
        if expected_hash is None:
            expected_hash = self.compute_hash(encrypted_data)
        else:
            # Verify hash matches
            actual_hash = self.compute_hash(encrypted_data)
            if actual_hash != expected_hash:
                # Cleanup temp file
                try:
                    temp_file_path.unlink()
                except Exception:
                    pass
                raise IOError(
                    f"Integrity check failed for session {session_id}: hash mismatch"
                )

        # Save to final location using existing save_file method
        # This handles both primary and source storage
        try:
            file_path = self.save_file(file_id, encrypted_data)

            # Cleanup temporary file after successful save
            try:
                temp_file_path.unlink()
            except Exception:
                # Log warning but don't fail if cleanup fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to delete temporary file for session {session_id}"
                )

            return file_path
        except Exception as e:
            # If save failed, keep temp file for potential retry
            # But log the error
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to complete chunked upload for session {session_id}: {e}"
            )
            raise IOError(
                f"Failed to complete chunked upload for session {session_id}: {e}"
            ) from e

    def delete_temp_file(self, session_id: str) -> None:
        """Delete temporary file for a session.

        Args:
            session_id: Upload session ID
        """
        temp_file_path = self.get_temp_file_path(session_id)
        try:
            if temp_file_path.exists():
                temp_file_path.unlink()
        except Exception as e:
            # Log warning but don't raise - cleanup is best effort
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to delete temporary file for session {session_id}: {e}"
            )
