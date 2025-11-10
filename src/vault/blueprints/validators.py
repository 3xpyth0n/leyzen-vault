"""Validation utilities for API endpoints."""

from __future__ import annotations

import re
from typing import Any


def validate_uuid(uuid_string: str | None) -> bool:
    """Validate that a string is a valid UUID format.

    Args:
        uuid_string: String to validate

    Returns:
        True if valid UUID format, False otherwise
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    # UUID format: 8-4-4-4-12 hex characters
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(uuid_pattern.match(uuid_string.strip()))


def validate_vaultspace_id(vaultspace_id: str | None) -> bool:
    """Validate that a string is a valid VaultSpace ID (UUID format).

    Args:
        vaultspace_id: VaultSpace ID to validate

    Returns:
        True if valid VaultSpace ID format, False otherwise
    """
    return validate_uuid(vaultspace_id)


def validate_file_id(file_id: str | None) -> bool:
    """Validate that a string is a valid File ID (UUID format).

    Args:
        file_id: File ID to validate

    Returns:
        True if valid File ID format, False otherwise
    """
    return validate_uuid(file_id)


def validate_pagination_params(
    page: Any, per_page: Any, max_per_page: int = 100
) -> tuple[int, int, str | None]:
    """Validate and normalize pagination parameters.

    Args:
        page: Page number (can be int, str, or None)
        per_page: Items per page (can be int, str, or None)
        max_per_page: Maximum allowed items per page (default: 100)

    Returns:
        Tuple of (page, per_page, error_message).
        If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    # Validate and convert page
    try:
        if page is None:
            page = 1
        elif isinstance(page, str):
            page = int(page.strip())
        else:
            page = int(page)

        if page < 1:
            return 1, 50, "Page number must be greater than 0"
    except (ValueError, TypeError):
        return 1, 50, "Invalid page number format"

    # Validate and convert per_page
    try:
        if per_page is None:
            per_page = 50
        elif isinstance(per_page, str):
            per_page = int(per_page.strip())
        else:
            per_page = int(per_page)

        if per_page < 1:
            return page, 50, "Items per page must be greater than 0"

        if per_page > max_per_page:
            return page, max_per_page, f"Items per page cannot exceed {max_per_page}"

    except (ValueError, TypeError):
        return page, 50, "Invalid items per page format"

    return page, per_page, None


def sanitize_string_input(
    input_string: str | None,
    max_length: int | None = None,
    allow_empty: bool = False,
) -> tuple[str | None, str | None]:
    """Sanitize and validate string input.

    Args:
        input_string: String to sanitize
        max_length: Maximum allowed length (None for no limit)
        allow_empty: Whether empty strings are allowed

    Returns:
        Tuple of (sanitized_string, error_message).
        If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    if input_string is None:
        if allow_empty:
            return None, None
        return None, "Input string is required"

    if not isinstance(input_string, str):
        return None, "Input must be a string"

    # Trim whitespace
    sanitized = input_string.strip()

    if not sanitized and not allow_empty:
        return None, "Input string cannot be empty"

    # Check length
    if max_length is not None and len(sanitized) > max_length:
        return (
            None,
            f"Input string too long: maximum {max_length} characters allowed",
        )

    # Remove control characters (except newlines and tabs in some cases)
    sanitized = "".join(
        char for char in sanitized if ord(char) >= 32 or char in ("\n", "\t", "\r")
    )

    return sanitized, None


def validate_email(email: str | None) -> bool:
    """Validate that a string is a valid email format.

    Args:
        email: Email string to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    email = email.strip()
    if not email:
        return False

    # Basic email validation pattern
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(email_pattern.match(email))


__all__ = [
    "validate_uuid",
    "validate_vaultspace_id",
    "validate_file_id",
    "validate_pagination_params",
    "sanitize_string_input",
    "validate_email",
]
