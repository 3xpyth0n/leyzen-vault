"""Safe JSON parsing utilities with DoS protection.

This module provides safe JSON parsing functions that protect against
denial-of-service attacks via malicious JSON payloads (e.g., deeply nested
structures, extremely large payloads).
"""

from __future__ import annotations

import json
from typing import Any

# Default limits
MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB default
MAX_JSON_DEPTH = 100


def safe_json_loads(
    data: str,
    max_size: int = MAX_JSON_SIZE,
    max_depth: int = MAX_JSON_DEPTH,
    context: str = "unknown",
) -> Any:
    """Parse JSON with DoS protection.

    This function protects against denial-of-service attacks by:
    - Limiting the maximum size of JSON data
    - Limiting the maximum nesting depth
    - Providing clear error messages for debugging

    Args:
        data: JSON string to parse
        max_size: Maximum allowed size in bytes (default: 10MB)
        max_depth: Maximum allowed nesting depth (default: 100)
        context: Context description for error messages (default: "unknown")

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If JSON data exceeds size or depth limits, or is invalid

    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('{"nested": {"deep": "value"}}', max_depth=2)
        {'nested': {'deep': 'value'}}
    """
    if not isinstance(data, str):
        raise ValueError(f"JSON data must be a string, got {type(data).__name__}")

    if len(data) > max_size:
        raise ValueError(
            f"JSON data too large in {context}: {len(data)} bytes (max: {max_size})"
        )

    # Check approximate depth by counting brackets
    # This is a simple heuristic that works for most cases
    depth = 0
    max_found_depth = 0
    in_string = False
    escape_next = False

    for char in data:
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == "{" or char == "[":
                depth += 1
                max_found_depth = max(max_found_depth, depth)
            elif char == "}" or char == "]":
                depth -= 1

    if max_found_depth > max_depth:
        raise ValueError(
            f"JSON depth too large in {context}: {max_found_depth} (max: {max_depth})"
        )

    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {context}: {e}")


__all__ = ["safe_json_loads", "MAX_JSON_SIZE", "MAX_JSON_DEPTH"]
