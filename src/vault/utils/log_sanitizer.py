"""Log sanitization utilities to prevent information leakage."""

from __future__ import annotations

import re
from typing import Any


def sanitize_for_logging(value: Any, max_length: int = 100) -> str:
    """Sanitize a value for safe logging to prevent information leakage.

    Removes or masks sensitive information like:
    - Tokens (JWT, API keys, etc.)
    - Passwords
    - Email addresses (partially masked)
    - IP addresses (partially masked)
    - File paths (sanitized)

    Args:
        value: Value to sanitize (can be any type)
        max_length: Maximum length of sanitized string

    Returns:
        Sanitized string safe for logging
    """
    if value is None:
        return "None"

    # Convert to string
    str_value = str(value)

    # Truncate if too long
    if len(str_value) > max_length:
        str_value = str_value[:max_length] + "..."

    # Mask JWT tokens (Bearer tokens)
    str_value = re.sub(
        r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
        "Bearer [REDACTED]",
        str_value,
    )

    # Mask API keys (leyz_ prefix)
    str_value = re.sub(r"leyz_[A-Za-z0-9\-_]{20,}", "leyz_[REDACTED]", str_value)

    # Mask email addresses (show first 3 chars and domain)
    str_value = re.sub(
        r"([a-zA-Z0-9._%+-]{3})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        r"\1***@\2",
        str_value,
    )

    # Mask IP addresses (show first octet only)
    str_value = re.sub(
        r"\b(\d{1,3})\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", r"\1.***.***.***", str_value
    )

    # Mask IPv6 addresses (show first segment only)
    str_value = re.sub(r"\b([0-9a-fA-F]{1,4}):[0-9a-fA-F:]+", r"\1:****", str_value)

    # Mask passwords in common patterns
    str_value = re.sub(
        r"(password|passwd|pwd|secret|token|key)\s*[:=]\s*[^\s,}]+",
        r"\1=[REDACTED]",
        str_value,
        flags=re.IGNORECASE,
    )

    # Mask file paths (show only filename)
    str_value = re.sub(r"/[^\s/]+/([^/\s]+)$", r"/.../\1", str_value)

    # Remove potential SQL injection patterns
    str_value = re.sub(
        r"[';]+\s*(DROP|DELETE|UPDATE|INSERT|SELECT)",
        "[SQL_REDACTED]",
        str_value,
        flags=re.IGNORECASE,
    )

    return str_value


def sanitize_dict_for_logging(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a dictionary for safe logging.

    Args:
        data: Dictionary to sanitize

    Returns:
        Sanitized dictionary with sensitive values masked
    """
    sensitive_keys = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "jwt",
        "access_token",
        "refresh_token",
        "session",
        "cookie",
        "csrf",
    }

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict_for_logging(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                (
                    sanitize_for_logging(item)
                    if not isinstance(item, dict)
                    else sanitize_dict_for_logging(item)
                )
                for item in value
            ]
        else:
            sanitized[key] = sanitize_for_logging(value)

    return sanitized
