"""File storage management for encrypted files."""

from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path
from typing import BinaryIO


class FileStorage:
    """Manages storage of encrypted files."""

    def __init__(self, storage_dir: Path):
        """Initialize storage with a directory."""
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

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

        # Reject path traversal sequences
        path_traversal_patterns = ["..", "/", "\\"]
        for pattern in path_traversal_patterns:
            if pattern in filename:
                return (
                    False,
                    f"Filename contains invalid characters: '{pattern}' (path traversal detected)",
                )

        # Reject null bytes
        if "\x00" in filename:
            return False, "Filename contains null bytes"

        # Whitelist approach: allow letters, digits, spaces, hyphens, underscores, dots
        # This covers most legitimate filenames while preventing dangerous characters
        # Allow Unicode characters for international filenames
        allowed_pattern = re.compile(r"^[\w\s\-\.]+$", re.UNICODE)
        if not allowed_pattern.match(filename):
            return (
                False,
                "Filename contains invalid characters. Only letters, numbers, spaces, hyphens, underscores, and dots are allowed.",
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
        """Save encrypted file data."""
        file_path = self.storage_dir / file_id
        file_path.write_bytes(encrypted_data)
        return file_path

    def get_file_path(self, file_id: str) -> Path:
        """Get the path to a stored file."""
        return self.storage_dir / file_id

    def read_file(self, file_id: str) -> bytes:
        """Read encrypted file data."""
        file_path = self.get_file_path(file_id)
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_id} not found")
        return file_path.read_bytes()

    def delete_file(self, file_id: str) -> bool:
        """Delete a stored file."""
        file_path = self.get_file_path(file_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def file_exists(self, file_id: str) -> bool:
        """Check if a file exists."""
        return self.get_file_path(file_id).exists()

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
            if not self.file_exists(file_id):
                return False, "File not found"

            # Read the file and compute its current hash
            encrypted_data = self.read_file(file_id)
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
