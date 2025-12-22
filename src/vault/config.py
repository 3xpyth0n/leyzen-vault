"""Configuration loading for Leyzen Vault."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from pathlib import Path

from zoneinfo import ZoneInfo

from common.config_utils import parse_bool, parse_int_env_var, validate_secret_entropy
from common.constants import (
    CAPTCHA_LENGTH_DEFAULT,
    CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
    LOGIN_CSRF_TTL_SECONDS_DEFAULT,
    PROXY_TRUST_COUNT_DEFAULT,
)
from common.env import (
    load_env_with_priority,
    parse_timezone,
)
from common.exceptions import ConfigurationError


def get_postgres_url(
    env_values: dict[str, str],
    app: Any = None,
    secret_key: str | None = None,
    use_app_role: bool = False,
) -> str:
    """Build PostgreSQL connection URL.

    This function can use either the leyzen_app role (from SystemSecrets) or
    the default POSTGRES_USER. By default, uses POSTGRES_USER for backward compatibility.

    Args:
        env_values: Dictionary containing environment variables
        app: Optional Flask app instance (required to read from SystemSecrets when use_app_role=True)
        secret_key: Optional SECRET_KEY for decrypting password from SystemSecrets
        use_app_role: If True, use leyzen_app role from SystemSecrets. If False, use POSTGRES_USER.

    Returns:
        PostgreSQL connection URL string

    Raises:
        ConfigurationError: If password cannot be obtained
    """
    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
    postgres_port = env_values.get("POSTGRES_PORT", "5432")
    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")

    if use_app_role:
        # Use leyzen_app role from SystemSecrets
        from vault.services.db_password_service import DBPasswordService

        postgres_user = "leyzen_app"

        # Try to get password from SystemSecrets
        postgres_password = None
        if app and secret_key:
            try:
                postgres_password = DBPasswordService.get_password(
                    secret_key, DBPasswordService.SECRET_KEY_APP, app
                )
            except Exception:
                # SystemSecrets not available yet
                pass

        if not postgres_password:
            raise ConfigurationError(
                "leyzen_app password not found in SystemSecrets. "
                "Roles may not be initialized yet."
            )
    else:
        # Use default POSTGRES_USER
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
    jwt_expiration_hours: int = 120


def load_settings() -> VaultSettings:
    """Load settings from environment variables.

    Use /setup on first run to create the superadmin account.
    """
    # Load environment with proper priority: .env file overrides os.environ
    # This ensures .env file values take precedence for security and isolation
    env_values = load_env_with_priority()

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

    # JWT expiration time in hours (default: 120 hours = 5 days)
    jwt_expiration_hours = parse_int_env_var(
        "VAULT_JWT_EXPIRATION_HOURS", 120, env_values, min_value=1
    )

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
        jwt_expiration_hours=jwt_expiration_hours,
    )


def is_setup_complete(app, quiet: bool = False) -> bool:
    """Check if setup is complete by verifying if at least one user exists in database.

    Args:
        app: Flask application with database initialized
        quiet: If True, suppress log messages (useful during startup to avoid duplicate logs)

    Returns:
        True if at least one user exists, False otherwise
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        from vault.database.schema import User, db
        from flask import has_app_context

        app_logger = None
        try:
            app_logger = app.config.get("LOGGER", None)
        except Exception:
            pass

        # Check if we're already in an app context (e.g., from a Flask route)
        # If so, use the existing context instead of creating a new one
        if has_app_context():
            # Already in app context - use it directly
            try:
                # Ensure database connection is active
                from sqlalchemy import text

                db.session.execute(text("SELECT 1"))

                # Query user count
                user_count = db.session.query(User).count()
                result = user_count > 0
                if not quiet:
                    log_msg = f"[SETUP CHECK] User count: {user_count}, setup complete: {result}"
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.info(log_msg)
                return result
            except Exception as db_error:
                error_msg = f"[SETUP CHECK] Database query failed: {db_error}"
                if app_logger:
                    app_logger.log(error_msg)
                else:
                    logger.error(error_msg, exc_info=True)
                # Try to rollback any failed transaction
                try:
                    db.session.rollback()
                except Exception:
                    pass
                return False
        else:
            # Not in app context - create one
            with app.app_context():
                try:
                    # Ensure database connection is active
                    from sqlalchemy import text

                    db.session.execute(text("SELECT 1"))

                    # Query user count
                    user_count = db.session.query(User).count()
                    result = user_count > 0
                    if not quiet:
                        log_msg = f"[SETUP CHECK] User count: {user_count}, setup complete: {result}"
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.info(log_msg)
                    return result
                except Exception as db_error:
                    error_msg = f"[SETUP CHECK] Database query failed: {db_error}"
                    if app_logger:
                        app_logger.log(error_msg)
                    else:
                        logger.error(error_msg, exc_info=True)
                    # Try to rollback any failed transaction
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    return False
    except Exception as e:
        error_msg = f"[SETUP CHECK] Failed to check setup status: {e}"

        app_logger = None
        try:
            app_logger = app.config.get("LOGGER", None)
        except Exception:
            pass

        if app_logger:
            app_logger.log(error_msg)
        else:
            logger.error(error_msg, exc_info=True)
        return False


__all__ = [
    "VaultSettings",
    "SMTPConfig",
    "load_settings",
    "get_postgres_url",
    "is_setup_complete",
]
