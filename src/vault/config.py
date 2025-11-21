"""Configuration loading for Leyzen Vault."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from zoneinfo import ZoneInfo

from common.config_utils import parse_bool, parse_int_env_var, validate_secret_entropy
from common.constants import (
    CAPTCHA_LENGTH_DEFAULT,
    CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
    LOGIN_CSRF_TTL_SECONDS_DEFAULT,
    PROXY_TRUST_COUNT_DEFAULT,
    TIMEZONE_DEFAULT,
)
from common.env import load_env_with_override, parse_timezone
from common.exceptions import ConfigurationError


def get_postgres_url(env_values: dict[str, str]) -> str:
    """Build PostgreSQL connection URL from environment variables.

    This function performs the primary validation of POSTGRES_PASSWORD. It ensures
    that the password is present and non-empty before constructing the connection URL.

    Note on validation layers:
    - Primary validation (this function): Application-level validation that raises
      ConfigurationError with a clear error message if POSTGRES_PASSWORD is missing.
      This is called when the Vault application starts and provides better error
      messages for operators.
    - Secondary validation (Docker Compose): Infrastructure-level validation in
      src/compose/build.py that uses Docker Compose's ${VAR:?error} syntax to prevent
      the PostgreSQL container from starting without a password. This fails fast at
      container startup time.

    Both validations are necessary:
    1. Docker Compose validation prevents containers from starting with invalid config
    2. Application validation provides better error messages and handles runtime changes

    Args:
        env_values: Dictionary containing environment variables

    Returns:
        PostgreSQL connection URL string

    Raises:
        ConfigurationError: If POSTGRES_PASSWORD is missing or empty
    """
    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
    postgres_port = env_values.get("POSTGRES_PORT", "5432")
    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
    postgres_user = env_values.get("POSTGRES_USER", "leyzen")
    postgres_password = env_values.get("POSTGRES_PASSWORD", "")

    if not postgres_password:
        raise ConfigurationError("POSTGRES_PASSWORD is required")

    return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"


@dataclass(frozen=True)
class SMTPConfig:
    """SMTP configuration for email sending."""

    host: str
    port: int
    user: str
    password: str
    use_tls: bool
    from_email: str
    from_name: str


@dataclass(frozen=True)
class VaultSettings:
    """Application settings for Leyzen Vault."""

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
    audit_retention_days: int
    smtp_config: SMTPConfig | None = None
    vault_url: str | None = None
    email_verification_expiry_minutes: int = 10
    max_total_size_mb: int | None = None


def load_settings() -> VaultSettings:
    """Load settings from environment variables.

    Use /setup on first run to create the superadmin account.
    """
    env_values = load_env_with_override()
    # Merge with actual os.environ to allow runtime overrides
    env_values.update(os.environ)

    # Secret key (required)
    secret_key = env_values.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError("SECRET_KEY is required (minimum 32 characters)")

    validate_secret_entropy(secret_key, min_length=32, secret_name="SECRET_KEY")

    # Timezone
    timezone = parse_timezone(env_values, allow_fallback=False)

    # Proxy trust count
    proxy_trust_count = parse_int_env_var(
        "PROXY_TRUST_COUNT", PROXY_TRUST_COUNT_DEFAULT, env_values, min_value=0
    )

    # Captcha settings
    captcha_length = parse_int_env_var(
        "CAPTCHA_LENGTH", CAPTCHA_LENGTH_DEFAULT, env_values
    )
    captcha_store_ttl = parse_int_env_var(
        "CAPTCHA_STORE_TTL_SECONDS",
        CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
        env_values,
    )
    login_csrf_ttl = parse_int_env_var(
        "LOGIN_CSRF_TTL_SECONDS",
        LOGIN_CSRF_TTL_SECONDS_DEFAULT,
        env_values,
    )

    # Session cookie secure flag
    session_cookie_secure = parse_bool(
        env_values.get("SESSION_COOKIE_SECURE"), default=True
    )

    # SECURITY: Validate session cookie security for HTTPS deployments
    # If HTTPS is enabled (via ENABLE_HTTPS), SESSION_COOKIE_SECURE should be True
    enable_https = parse_bool(env_values.get("ENABLE_HTTPS"), default=False)
    if enable_https and not session_cookie_secure:
        import warnings

        warnings.warn(
            "SECURITY WARNING: ENABLE_HTTPS is True but SESSION_COOKIE_SECURE is False. "
            "Session cookies should be marked as Secure when using HTTPS. "
            "Set SESSION_COOKIE_SECURE=true in your .env file.",
            UserWarning,
        )

    # Log file - use /data/vault.log by default
    log_file_env = env_values.get("VAULT_LOG_FILE", "/data/vault.log")
    log_file = Path(log_file_env)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if not log_file.exists():
            log_file.touch()
    except OSError:
        # Fallback to tmpfs location (dev/shm is tmpfs by default)
        log_file = Path("/dev/shm/vault.log")

    # Max file size in MB (default: 100MB)
    max_file_size_mb = parse_int_env_var(
        "VAULT_MAX_FILE_SIZE_MB", 100, env_values, min_value=1, max_value=10240
    )

    # Max uploads per hour per IP (default: 50)
    max_uploads_per_hour = parse_int_env_var(
        "VAULT_MAX_UPLOADS_PER_HOUR", 50, env_values, min_value=1
    )

    # Audit log retention in days (default: 90 days)
    audit_retention_days = parse_int_env_var(
        "VAULT_AUDIT_RETENTION_DAYS", 90, env_values, min_value=1
    )

    # SMTP configuration (optional - required for email verification and invitations)
    smtp_config = None
    smtp_host = env_values.get("SMTP_HOST", "").strip()
    if smtp_host:
        smtp_port = parse_int_env_var(
            "SMTP_PORT", 587, env_values, min_value=1, max_value=65535
        )
        smtp_user = env_values.get("SMTP_USER", "").strip()
        smtp_password = env_values.get("SMTP_PASSWORD", "").strip()
        smtp_use_tls = parse_bool(env_values.get("SMTP_USE_TLS"), default=True)
        smtp_from_email = env_values.get("SMTP_FROM_EMAIL", "").strip()
        smtp_from_name = env_values.get("SMTP_FROM_NAME", "Leyzen Vault").strip()

        if not smtp_from_email:
            smtp_from_email = smtp_user  # Fallback to SMTP_USER if FROM_EMAIL not set

        if smtp_user and smtp_password and smtp_from_email:
            smtp_config = SMTPConfig(
                host=smtp_host,
                port=smtp_port,
                user=smtp_user,
                password=smtp_password,
                use_tls=smtp_use_tls,
                from_email=smtp_from_email,
                from_name=smtp_from_name,
            )

    # Vault URL (optional - used for email links)
    vault_url = env_values.get("VAULT_URL", "").strip()
    if vault_url:
        # Ensure URL ends without trailing slash for consistency
        vault_url = vault_url.rstrip("/")
    else:
        vault_url = None

    # Email verification expiry in minutes (default: 10 minutes)
    email_verification_expiry_minutes = parse_int_env_var(
        "EMAIL_VERIFICATION_EXPIRY_MINUTES", 10, env_values, min_value=1, max_value=1440
    )

    # Max total storage size in MB (optional - controls tmpfs size)
    # If not set, uses actual disk size detected at runtime
    max_total_size_mb = None
    if "VAULT_MAX_TOTAL_SIZE_MB" in env_values:
        max_total_size_mb_raw = env_values.get("VAULT_MAX_TOTAL_SIZE_MB", "").strip()
        if max_total_size_mb_raw:
            # Use a sentinel value to detect if parsing failed
            # If the value is invalid, parse_int_env_var will return 0, which we'll ignore
            parsed_value = parse_int_env_var(
                "VAULT_MAX_TOTAL_SIZE_MB", 0, env_values, min_value=1
            )
            if parsed_value > 0:
                max_total_size_mb = parsed_value

    return VaultSettings(
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
        audit_retention_days=audit_retention_days,
        smtp_config=smtp_config,
        vault_url=vault_url,
        email_verification_expiry_minutes=email_verification_expiry_minutes,
        max_total_size_mb=max_total_size_mb,
    )


def is_setup_complete(app) -> bool:
    """Check if setup is complete by verifying if at least one user exists in database.

    Args:
        app: Flask application with database initialized

    Returns:
        True if at least one user exists, False otherwise
    """
    try:
        from vault.database.schema import User, db

        with app.app_context():
            user_count = db.session.query(User).count()
            return user_count > 0
    except Exception:
        # If database is not initialized or error occurs, assume setup is not complete
        return False


__all__ = [
    "VaultSettings",
    "SMTPConfig",
    "load_settings",
    "get_postgres_url",
    "is_setup_complete",
]
