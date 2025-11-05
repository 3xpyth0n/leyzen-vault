"""Configuration loading for Leyzen Vault."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zoneinfo import ZoneInfo

from werkzeug.security import check_password_hash, generate_password_hash

from common.constants import (
    CAPTCHA_LENGTH_DEFAULT,
    CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
    LOGIN_CSRF_TTL_SECONDS_DEFAULT,
    PROXY_TRUST_COUNT_DEFAULT,
    TIMEZONE_DEFAULT,
)
from common.env import load_env_with_override, parse_timezone
from common.exceptions import ConfigurationError


@dataclass(frozen=True)
class VaultSettings:
    """Application settings for Leyzen Vault."""

    username: str
    password_hash: str
    secret_key: str
    timezone: ZoneInfo
    proxy_trust_count: int
    captcha_length: int
    captcha_store_ttl: int
    login_csrf_ttl: int
    log_file: Path
    session_cookie_secure: bool
    max_file_size_mb: int
    max_uploads_per_hour: int


def _parse_int_env_var(
    name: str,
    default: int,
    env: dict[str, str],
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Parse an integer environment variable with optional min/max constraints."""
    raw_value = env.get(name, str(default)).strip()
    try:
        value = int(raw_value)
        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value
    except ValueError:
        return default


_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def _parse_bool(value: str | None, *, default: bool) -> bool:
    """Parse a boolean environment variable."""
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    return default


def load_settings() -> VaultSettings:
    """Load settings from environment variables."""
    env_values = load_env_with_override()
    # Merge with actual os.environ to allow runtime overrides
    env_values.update(os.environ)

    # Username (required)
    username = env_values.get("VAULT_USER", "").strip()
    if not username:
        raise ConfigurationError("VAULT_USER is required")

    # Password (required)
    password = env_values.get("VAULT_PASS", "").strip()
    if not password:
        raise ConfigurationError("VAULT_PASS is required")

    # Generate password hash
    password_hash = generate_password_hash(password)

    # Secret key (required)
    secret_key = env_values.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError("SECRET_KEY is required (minimum 12 characters)")

    if len(secret_key) < 12:
        raise ConfigurationError("SECRET_KEY must be at least 12 characters long")

    # Timezone
    timezone = parse_timezone(env_values, allow_fallback=False)

    # Proxy trust count
    proxy_trust_count = _parse_int_env_var(
        "PROXY_TRUST_COUNT", PROXY_TRUST_COUNT_DEFAULT, env_values, min_value=0
    )

    # Captcha settings
    captcha_length = _parse_int_env_var(
        "CAPTCHA_LENGTH", CAPTCHA_LENGTH_DEFAULT, env_values
    )
    captcha_store_ttl = _parse_int_env_var(
        "CAPTCHA_STORE_TTL_SECONDS",
        CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
        env_values,
    )
    login_csrf_ttl = _parse_int_env_var(
        "LOGIN_CSRF_TTL_SECONDS",
        LOGIN_CSRF_TTL_SECONDS_DEFAULT,
        env_values,
    )

    # Session cookie secure flag
    session_cookie_secure = _parse_bool(
        env_values.get("SESSION_COOKIE_SECURE"), default=True
    )

    # Log file - use /data/vault.log by default
    log_file_env = env_values.get("VAULT_LOG_FILE", "/data/vault.log")
    log_file = Path(log_file_env)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if not log_file.exists():
            log_file.touch()
    except OSError:
        # Fallback to a default location
        log_file = Path("/tmp/vault.log")

    # Max file size in MB (default: 100MB)
    max_file_size_mb = _parse_int_env_var(
        "VAULT_MAX_FILE_SIZE_MB", 100, env_values, min_value=1, max_value=10240
    )

    # Max uploads per hour per IP (default: 50)
    max_uploads_per_hour = _parse_int_env_var(
        "VAULT_MAX_UPLOADS_PER_HOUR", 50, env_values, min_value=1
    )

    return VaultSettings(
        username=username,
        password_hash=password_hash,
        secret_key=secret_key,
        timezone=timezone,
        proxy_trust_count=proxy_trust_count,
        captcha_length=captcha_length,
        captcha_store_ttl=captcha_store_ttl,
        login_csrf_ttl=login_csrf_ttl,
        log_file=log_file,
        session_cookie_secure=session_cookie_secure,
        max_file_size_mb=max_file_size_mb,
        max_uploads_per_hour=max_uploads_per_hour,
    )


__all__ = ["VaultSettings", "load_settings"]
