"""Valid SVG icon names for VaultSpace icons.

This module contains the list of valid icon names that can be used for VaultSpace icons.
Icons are SVG-based and defined in src/vault/static/icons.js.
"""

# Valid SVG icon names (excluding helper functions and aliases)
VALID_ICON_NAMES = {
    "folder",
    "file",
    "delete",
    "star",
    "users",
    "clock",
    "lock",
    "key",
    "user",
    "settings",
    "logout",
    "upload",
    "download",
    "link",
    "eye",
    "edit",
    "clipboard",
    "copy",
    "move",
    "search",
    "plus",
    "chart",
    "moon",
    "sun",
    "warning",
    "moreVertical",
    "grid",
    "list",
    "home",
    "image",
    "chevronDown",
    "check",
    "trash",
    "restore",
    "success",
    "error",
    "info",
    "sparkles",
    "school",
    "briefcase",
    "heart",
    "dollarSign",
    "book",
    "calendar",
    "shoppingBag",
    "car",
    "music",
    "video",
    "camera",
    "gamepad",
    "coffee",
    "building",
    "graduationCap",
    "wallet",
    "plane",
}


def is_valid_icon_name(icon_name: str) -> bool:
    """Check if an icon name is valid.

    Args:
        icon_name: Icon name to validate

    Returns:
        True if icon name is valid, False otherwise
    """
    if not icon_name or not isinstance(icon_name, str):
        return False
    return icon_name in VALID_ICON_NAMES


def get_valid_icon_names() -> set[str]:
    """Get the set of all valid icon names.

    Returns:
        Set of valid icon names
    """
    return VALID_ICON_NAMES.copy()
