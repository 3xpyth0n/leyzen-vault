"""Common file validation utilities shared across services.

This module provides centralized file validation logic to prevent duplication
and ensure consistent validation across the application.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from vault.storage import FileStorage


def validate_filename(filename: str) -> tuple[bool, str | None]:
    """Validate filename to prevent path traversal and other security issues.

    This is a wrapper around FileStorage.validate_filename() to provide
    a centralized validation utility that can be used across services.

    Args:
        filename: The filename to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    return FileStorage.validate_filename(filename)


def validate_file_path(file_path: Path, base_dir: Path) -> tuple[bool, str | None]:
    """Validate that a file path is within the base directory (prevents path traversal).

    Args:
        file_path: The file path to validate
        base_dir: The base directory that the file must be within

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    try:
        # Resolve both paths to absolute paths
        file_path_abs = file_path.resolve()
        base_dir_abs = base_dir.resolve()

        # Check if file path is within base directory
        try:
            file_path_abs.relative_to(base_dir_abs)
            return True, None
        except ValueError:
            return (
                False,
                f"File path {file_path} is outside base directory {base_dir} (path traversal detected)",
            )
    except Exception as e:
        return False, f"Error validating file path: {str(e)}"


__all__ = ["validate_filename", "validate_file_path"]
