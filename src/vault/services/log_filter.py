"""Log filtering service to prevent sensitive data exposure in logs."""

from __future__ import annotations

import re
from typing import Any


class SensitiveDataFilter:
    """Filter sensitive data from log messages."""

    # Patterns to detect and redact sensitive data
    SENSITIVE_PATTERNS = [
        # JWT tokens (Bearer tokens)
        (
            r"Bearer\s+([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]*)",
            "Bearer [REDACTED]",
        ),
        # API tokens (long random strings)
        (r"token[=:]\s*([A-Za-z0-9\-_]{32,})", "token=[REDACTED]"),
        # Passwords
        (r"password[=:]\s*([^\s,}]+)", "password=[REDACTED]"),
        # Secret keys
        (r"secret[_\s]*key[=:]\s*([^\s,}]+)", "secret_key=[REDACTED]"),
        # API keys
        (r"api[_\s]*key[=:]\s*([^\s,}]+)", "api_key=[REDACTED]"),
        # Authorization headers
        (r"Authorization[=:]\s*([^\s,}]+)", "Authorization=[REDACTED]"),
        # Master keys
        (r"master[_\s]*key[=:]\s*([^\s,}]+)", "master_key=[REDACTED]"),
        # Encryption keys
        (r"encryption[_\s]*key[=:]\s*([^\s,}]+)", "encryption_key=[REDACTED]"),
    ]

    @classmethod
    def redact_sensitive_data(cls, message: str) -> str:
        """Redact sensitive data from a log message.

        Args:
            message: Original log message

        Returns:
            Log message with sensitive data redacted
        """
        if not isinstance(message, str):
            message = str(message)

        redacted = message
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)

        # Also redact tokens in URLs
        redacted = re.sub(
            r"token=([A-Za-z0-9\-_]{20,})",
            "token=[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )

        # Redact any long base64-like strings that might be keys
        redacted = re.sub(
            r"([A-Za-z0-9+/]{40,}={0,2})",
            lambda m: "[REDACTED]" if len(m.group(1)) > 40 else m.group(1),
            redacted,
        )

        return redacted

    @classmethod
    def safe_log_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Create a safe version of a dictionary for logging.

        Args:
            data: Original dictionary

        Returns:
            Dictionary with sensitive keys redacted
        """
        sensitive_keys = {
            "token",
            "password",
            "secret",
            "secret_key",
            "api_key",
            "master_key",
            "encryption_key",
            "auth",
            "authorization",
            "bearer",
            "jwt",
            "key",
        }

        safe_dict = {}
        for key, value in data.items():
            key_lower = key.lower()
            # Check if key contains sensitive terms
            if any(sensitive_term in key_lower for sensitive_term in sensitive_keys):
                safe_dict[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 20:
                # Redact long strings that might be tokens
                safe_dict[key] = cls.redact_sensitive_data(value)
            elif isinstance(value, dict):
                safe_dict[key] = cls.safe_log_dict(value)
            else:
                safe_dict[key] = value

        return safe_dict


__all__ = ["SensitiveDataFilter"]
