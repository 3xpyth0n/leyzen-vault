"""Icon name validation for VaultSpace icons.

This module provides minimal validation for icon names.
Icons are provided by Lucide Icons library. The frontend handles icon availability
checking, so the backend only performs basic format validation for security.
"""


def is_valid_icon_name(icon_name: str) -> bool:
    """Check if an icon name is valid.

    Performs minimal validation: checks that the icon name is a non-empty string
    with reasonable length. The actual icon availability is validated by the frontend.

    Args:
        icon_name: Icon name to validate

    Returns:
        True if icon name is valid, False otherwise
    """
    if not icon_name or not isinstance(icon_name, str):
        return False

    # Basic length check to prevent extremely long strings
    if len(icon_name) > 100:
        return False

    # Check that it's not just whitespace
    if not icon_name.strip():
        return False

    return True


def get_valid_icon_names() -> set[str]:
    """Get a set of common valid icon names.

    Returns:
        Empty set (for backward compatibility)
    """
    return set()
