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
        import tempfile
        import os

        # Compute hash before writing
        expected_hash = self.compute_hash(encrypted_data)

        # Save to primary storage (tmpfs)
        files_dir = self.storage_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        file_path = files_dir / file_id

        temp_fd, temp_path = tempfile.mkstemp(
            dir=files_dir, prefix=f".{file_id}.", suffix=".tmp"
        )
        primary_saved = False
        source_saved = False
        source_temp_path = None

        try:
            # Write to primary storage
            with os.fdopen(temp_fd, "wb") as temp_file:
                temp_file.write(encrypted_data)
                temp_file.flush()
                os.fsync(temp_fd)  # Force write to disk

            # Verify integrity after write
            temp_file_path = Path(temp_path)
            written_data = temp_file_path.read_bytes()
            actual_hash = self.compute_hash(written_data)

            if actual_hash != expected_hash:
                temp_file_path.unlink()
                raise IOError(
                    f"Integrity check failed for file {file_id}: "
                    f"hash mismatch after write"
                )

            # Atomic rename in primary storage
            temp_file_path.rename(file_path)
            primary_saved = True

            # Also save to source storage (persistent) if configured
            if self.source_dir:
                source_files_dir = self.source_dir / "files"
                source_files_dir.mkdir(parents=True, exist_ok=True)
                source_file_path = source_files_dir / file_id

                # Copy to source storage atomically
                source_temp_fd, source_temp_path = tempfile.mkstemp(
                    dir=source_files_dir, prefix=f".{file_id}.", suffix=".tmp"
                )
                try:
                    with os.fdopen(source_temp_fd, "wb") as source_temp_file:
                        source_temp_file.write(encrypted_data)
                        source_temp_file.flush()
                        os.fsync(source_temp_fd)  # Force write to disk

                    # Verify integrity in source storage
                    source_temp_file_path = Path(source_temp_path)
                    source_written_data = source_temp_file_path.read_bytes()
                    source_actual_hash = self.compute_hash(source_written_data)

                    if source_actual_hash != expected_hash:
                        source_temp_file_path.unlink()
                        raise IOError(
                            f"Integrity check failed for file {file_id} in source storage: "
                            f"hash mismatch after write"
                        )

                    # Atomic rename in source storage
                    source_temp_file_path.rename(source_file_path)
                    source_saved = True
                except Exception as source_error:
                    # Cleanup source temp file on error
                    try:
                        if source_temp_path:
                            source_temp_file_path_obj = Path(source_temp_path)
                            if source_temp_file_path_obj.exists():
                                source_temp_file_path_obj.unlink()
                    except Exception:
                        pass
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
            # Cleanup temp file on error
            try:
                temp_path_obj = Path(temp_path)
                if temp_path_obj.exists():
                    temp_path_obj.unlink()
            except Exception:
                pass

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
        """Delete a stored file."""
        file_path = self.get_file_path(file_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

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
