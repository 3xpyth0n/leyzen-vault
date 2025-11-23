"""Centralized password validation utility for Leyzen Vault."""

from __future__ import annotations


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    if not password:
        return False, "Password is required"

    # Validate password length (minimum 12 characters)
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    # Check password complexity
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    # Require uppercase, lowercase, and digit (special characters are optional)
    if not (has_upper and has_lower and has_digit):
        return (
            False,
            "Password must contain at least one uppercase letter, one lowercase letter, and one digit",
        )

    # SECURITY: Check against common passwords list
    # This helps prevent users from using easily guessable passwords
    common_passwords = [
        "password",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty",
        "abc123",
        "letmein",
        "welcome",
        "admin",
        "root",
        "Password1",
        "Password123",
        "Welcome1",
        "Admin123",
    ]
    password_lower = password.lower()
    for common in common_passwords:
        if password_lower == common.lower() or password_lower.startswith(
            common.lower()
        ):
            return (
                False,
                "Password is too common. Please choose a more unique password.",
            )

    # SECURITY: Check password strength score
    # Simple scoring: length + character variety
    score = 0
    if len(password) >= 16:
        score += 2
    elif len(password) >= 12:
        score += 1

    # Check for special characters
    if has_special:
        score += 1

    # Check character variety
    variety_count = sum([has_upper, has_lower, has_digit, has_special])
    if variety_count >= 3:
        score += 1

    # Minimum score of 2 required (basic password)
    if score < 2:
        return (
            False,
            "Password is too weak. Use a longer password with more character variety.",
        )

    return True, None


def validate_password_strength_raise(password: str) -> None:
    """Validate password strength and raise ValueError if invalid.

    Args:
        password: Password to validate

    Raises:
        ValueError: If password does not meet strength requirements
    """
    is_valid, error_message = validate_password_strength(password)
    if not is_valid:
        raise ValueError(error_message or "Invalid password")


__all__ = ["validate_password_strength", "validate_password_strength_raise"]
