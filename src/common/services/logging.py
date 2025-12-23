"""Unified logging helpers for Leyzen Vault components."""

from __future__ import annotations

import json
import logging.handlers
import re
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from common.constants import LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT


_CONTROL_CHAR_ESCAPES = {
    ord("\r"): "\\r",
    ord("\n"): "\\n",
    ord("\t"): "\\t",
}

# Secret detection patterns
_SECRET_PATTERNS = [
    # Original patterns
    r'key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9+/=]{20,})',
    r'password["\']?\s*[:=]\s*["\']?([^"\']+)',
    r'secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9+/=]{20,})',
    r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9+/=]{20,})',
    # JWT token pattern (3 parts separated by dots)
    r"Bearer\s+([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    r"Authorization:\s*Bearer\s+([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    # JSON format patterns
    r'"key"\s*:\s*"([^"]{20,})"',
    r'"password"\s*:\s*"([^"]+)"',
    r'"secret"\s*:\s*"([^"]{20,})"',
    r'"token"\s*:\s*"([^"]{20,})"',
    r'"jwt"\s*:\s*"([^"]+)"',
    # XML format patterns
    r"<key>([^<]{20,})</key>",
    r"<password>([^<]+)</password>",
    r"<secret>([^<]{20,})</secret>",
    r"<token>([^<]{20,})</token>",
]


def _is_ip_address(candidate: str) -> bool:
    """Check if a string looks like an IP address.

    Args:
        candidate: String to check

    Returns:
        True if the string looks like an IP address, False otherwise
    """
    # IPv4: 4 octets, each 1-3 digits, separated by dots
    # IPv6: uses colons, but can also use dots in some formats
    # Simple check: if it matches IPv4 pattern (4 numbers 0-255 separated by dots)
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, candidate):
        # Additional validation: check if each octet is 0-255
        try:
            parts = candidate.split(".")
            if len(parts) == 4:
                for part in parts:
                    num = int(part)
                    if num < 0 or num > 255:
                        return False
                return True
        except ValueError:
            return False
    return False


def _sanitize_log_value(value: Any, enable_secret_detection: bool = True) -> Any:
    """Sanitize log values to prevent secret leakage and control characters.

    Args:
        value: Value to sanitize
        enable_secret_detection: If True, detect and redact secrets (default: True)

    Returns:
        Sanitized value
    """
    if isinstance(value, str):
        sanitized = value

        if enable_secret_detection:
            # First, handle JWT tokens specifically (complete replacement)
            # JWT format: header.payload.signature (3 parts separated by dots)
            # JWT parts are base64-encoded and typically much longer than IP addresses
            # IPv4 addresses have 4 octets (1-3 digits each), IPv6 addresses use colons
            # Strategy: Only match JWT tokens that are long enough AND contain letters
            # AND are not IP addresses
            jwt_pattern = (
                r"([A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
            )

            def is_jwt_not_ip(match):
                candidate = match.group(1)
                # First check: if it's an IP address, don't redact it
                if _is_ip_address(candidate):
                    return candidate
                # Second check: if it contains at least one letter AND is long enough, it's likely a JWT
                # IP addresses (IPv4) are only digits and dots, and have 4 octets
                # JWT tokens have 3 parts, are much longer, and contain letters (base64 encoding)
                if re.search(r"[A-Za-z]", candidate) and len(candidate) > 50:
                    return "[REDACTED_JWT_TOKEN]"
                # If it doesn't match JWT criteria, don't redact
                return candidate

            sanitized = re.sub(jwt_pattern, is_jwt_not_ip, sanitized)

            # Redact Bearer tokens completely
            bearer_pattern = r"Bearer\s+[A-Za-z0-9_.-]+"
            sanitized = re.sub(
                bearer_pattern, "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE
            )

            # Then apply other secret patterns
            for pattern in _SECRET_PATTERNS:
                # Skip JWT/Bearer patterns as we already handled them
                if (
                    "Bearer" in pattern
                    or "jwt" in pattern.lower()
                    or "Authorization" in pattern
                ):
                    continue
                sanitized = re.sub(
                    pattern,
                    lambda m: m.group(0).replace(m.group(1), "[REDACTED]"),
                    sanitized,
                    flags=re.IGNORECASE,
                )

            # Redact any long base64-like strings (potential keys)
            base64_pattern = r"([A-Za-z0-9+/]{40,}={0,2})"
            sanitized = re.sub(
                base64_pattern,
                lambda m: "[REDACTED_KEY]" if len(m.group(1)) > 40 else m.group(1),
                sanitized,
            )

            # Redact tokens in query strings and headers
            # But don't redact client_ip (it's not a secret, it's metadata)
            sanitized = re.sub(
                r"(token|key|secret|password|auth)(?!\w)[=:]\s*[^\s,}]+",
                r"\1=[REDACTED]",
                sanitized,
                flags=re.IGNORECASE,
            )

        # Always escape control characters
        return sanitized.translate(_CONTROL_CHAR_ESCAPES)

    if isinstance(value, dict):
        # Special handling for common metadata keys that should not be redacted
        # IP addresses are metadata, not secrets
        result = {}
        for k, v in value.items():
            key_str = str(k)
            # If the key is client_ip, ip, or similar, and the value looks like an IP, don't sanitize it
            if key_str.lower() in (
                "client_ip",
                "ip",
                "remote_addr",
                "client_address",
            ) and isinstance(v, str):
                # Verify it's actually an IP address before skipping sanitization
                if _is_ip_address(v):
                    result[key_str] = (
                        v  # Don't sanitize IP addresses in metadata fields
                    )
                else:
                    result[key_str] = _sanitize_log_value(v, enable_secret_detection)
            else:
                result[key_str] = _sanitize_log_value(v, enable_secret_detection)
        return result

    if isinstance(value, (list, tuple, set)):
        return [_sanitize_log_value(v, enable_secret_detection) for v in value]

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return _sanitize_log_value(str(value), enable_secret_detection)


class FileLogger:
    """Write structured log lines to a dedicated file with automatic rotation.

    This is a unified logger that works with both orchestrator Settings and vault
    VaultSettings. The logger accepts any object with `log_file` (Path) and
    `timezone` (ZoneInfo) attributes.

    Args:
        settings: Settings object with `log_file` and `timezone` attributes
        enable_secret_detection: If True, detect and redact secrets in logs (default: True)
    """

    def __init__(
        self,
        settings: Any,
        *,
        enable_secret_detection: bool = True,
        is_production: bool = True,
    ) -> None:
        """Initialize FileLogger.

        Args:
            settings: Settings object with `log_file` (Path) and `timezone` (ZoneInfo) attributes
            enable_secret_detection: Enable secret detection in logs (default: True for security)
            is_production: If True, set default log level to WARNING, otherwise INFO
        """
        self._settings = settings
        self._enable_secret_detection = enable_secret_detection
        self._is_production = is_production
        self._lock = Lock()

        # Configure rotating file handler
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotate at 10MB, keep 5 backups
        self._handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        # We write our own formatted lines, so disable default formatting
        self._handler.setFormatter(logging.Formatter("%(message)s"))

        # Create a logger instance just for the handler
        self._logger = logging.getLogger(f"file_logger_{id(self)}")
        # Default to WARNING in production, INFO in development
        default_level = logging.WARNING if is_production else logging.INFO
        self._logger.setLevel(default_level)
        self._logger.handlers = [self._handler]

    @property
    def log_file(self) -> Path:
        """Get the log file path."""
        return self._settings.log_file

    def setLevel(self, level: int) -> None:
        """Set the logging level for the file logger."""
        self._logger.setLevel(level)

    def log(
        self, msg: Any, *, context: Any | None = None, level: int = logging.INFO
    ) -> None:
        """Log a message with optional context and specific level.

        Args:
            msg: Message to log
            context: Optional context dictionary to include in the log entry
            level: The logging level to use (default: INFO)
        """
        # Respect the configured level before logging anything
        if not self._logger.isEnabledFor(level):
            return

        timezone: ZoneInfo = self._settings.timezone
        timestamp = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
        sanitized_msg = _sanitize_log_value(
            str(msg), enable_secret_detection=self._enable_secret_detection
        )
        line = f"[{timestamp}] {sanitized_msg}"

        if context is not None:
            sanitized_context = _sanitize_log_value(
                context, enable_secret_detection=self._enable_secret_detection
            )
            try:
                context_str = json.dumps(
                    sanitized_context, ensure_ascii=False, sort_keys=True
                )
            except (TypeError, ValueError):
                context_str = json.dumps(
                    _sanitize_log_value(
                        str(sanitized_context),
                        enable_secret_detection=self._enable_secret_detection,
                    ),
                    ensure_ascii=False,
                )
            line = f"{line} {context_str}"

        with self._lock:
            # Use the logger's handler for automatic rotation
            # Log at the requested level
            self._logger.log(level, line)

    def flush(self) -> None:
        """Flush the log handler to ensure all buffered messages are written to disk."""
        with self._lock:
            self._handler.flush()

    def info(self, msg: Any, *, context: Any | None = None) -> None:
        """Log an info message."""
        self.log(msg, context=context, level=logging.INFO)

    def error(self, msg: Any, *, context: Any | None = None) -> None:
        """Log an error message."""
        self.log(msg, context=context, level=logging.ERROR)

    def warning(self, msg: Any, *, context: Any | None = None) -> None:
        """Log a warning message."""
        self.log(msg, context=context, level=logging.WARNING)

    def debug(self, msg: Any, *, context: Any | None = None) -> None:
        """Log a debug message."""
        self.log(msg, context=context, level=logging.DEBUG)


__all__ = ["FileLogger", "_sanitize_log_value"]
