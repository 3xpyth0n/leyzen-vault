"""Configuration loading for the vault orchestrator application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

from common.config_utils import (
    parse_bool,
    parse_int_env_var,
    validate_default_credentials,
    validate_secret_entropy,
)
from common.constants import (
    ALLOWED_URL_SCHEMES,
    CAPTCHA_LENGTH_DEFAULT,
    CAPTCHA_STORE_TTL_SECONDS_DEFAULT,
    CSP_REPORT_MAX_SIZE_DEFAULT,
    CSP_REPORT_RATE_LIMIT_DEFAULT,
    CSP_REPORT_RATE_WINDOW_SECONDS,
    ROTATION_INTERVAL_DEFAULT,
    DOCKER_PROXY_BASE_URL_DEFAULT,
    LOGIN_CSRF_TTL_SECONDS_DEFAULT,
    ORCHESTRATOR_DIR,
    ORCHESTRATOR_LOG_FILE_DEFAULT,
    ORCHESTRATOR_PORT_DEFAULT,
    PROXY_TRUST_COUNT_DEFAULT,
    SSE_INTERVAL_MS_DEFAULT,
    SSE_INTERVAL_MS_MINIMUM,
)
from common.env import load_env_with_override, parse_container_names, parse_timezone
from common.exceptions import ConfigurationError
from common.token_utils import (
    derive_docker_proxy_token,
    derive_internal_api_token,
)


@dataclass(frozen=True)
class Settings:
    """Application settings derived from environment variables."""

    timezone: ZoneInfo
    username: str
    password_hash: str
    proxy_trust_count: int
    docker_proxy_url: str
    docker_proxy_token: str
    internal_api_token: str
    web_containers: list[str]
    rotation_interval: int
    log_file: Path
    html_dir: Path
    secret_key: str
    captcha_length: int
    captcha_store_ttl: int
    login_csrf_ttl: int
    csp_report_max_size: int
    csp_report_rate_limit: int
    csp_report_rate_window: timedelta
    sse_stream_interval_ms: int
    session_cookie_secure: bool
    orchestrator_port: int

    @property
    def log_dir(self) -> Path:
        return self.log_file.parent

    @property
    def sse_stream_interval_seconds(self) -> float:
        """Return the SSE stream interval expressed in seconds."""

        return max(
            SSE_INTERVAL_MS_MINIMUM / 1000.0, self.sse_stream_interval_ms / 1000.0
        )


def _ensure_required_variables(required: list[str], env: dict[str, str]) -> None:
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(sorted(missing))}"
        )


def _determine_log_file(base_dir: Path, env: dict[str, str]) -> Path:
    override = env.get("ORCH_LOG_DIR")
    if override:
        candidate = Path(override).expanduser().resolve()
    else:
        candidate = base_dir

    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        candidate = base_dir

    filename = env.get("ORCH_LOG_FILE", ORCHESTRATOR_LOG_FILE_DEFAULT)
    log_path = candidate / filename

    try:
        if not log_path.exists():
            log_path.touch()
    except OSError:
        # If the file cannot be created now, the logger will surface the error later.
        pass

    return log_path


def _validate_url(url: str, variable_name: str) -> str:
    """Validate that a string is a well-formed URL.

    Args:
        url: The URL string to validate
        variable_name: Name of the environment variable for error messages

    Returns:
        The validated URL string

    Raises:
        ConfigurationError: If the URL is invalid
    """
    url = url.strip()
    if not url:
        raise ConfigurationError(f"{variable_name} cannot be empty")

    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            schemes_str = " or ".join(f"{s}://" for s in ALLOWED_URL_SCHEMES)
            raise ConfigurationError(
                f"{variable_name} must include a scheme ({schemes_str})"
            )
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            schemes_str = " or ".join(ALLOWED_URL_SCHEMES)
            raise ConfigurationError(f"{variable_name} must use {schemes_str} scheme")
    except Exception as exc:
        raise ConfigurationError(f"{variable_name} is not a valid URL: {exc}") from exc

    return url


def _get_internal_api_token_from_db(env_values: dict[str, str], secret_key: str) -> str:
    """Get INTERNAL_API_TOKEN from database (SystemSecrets table).

    The orchestrator reads the token from the same PostgreSQL database as the vault.
    The token is encrypted in the database and decrypted using SECRET_KEY.

    Args:
        env_values: Dictionary containing environment variables
        secret_key: Secret key for decrypting the token

    Returns:
        The internal API token string, or empty string if not available
    """
    import os

    # Check environment variable first (explicit override)
    internal_api_token = env_values.get("INTERNAL_API_TOKEN", "")
    if not internal_api_token:
        internal_api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    # If explicitly set in environment, use it
    if internal_api_token:
        return internal_api_token

    # Try to read from database using SQLAlchemy directly (no dependency on vault module)
    try:
        from sqlalchemy import create_engine, text
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.backends import default_backend
        import base64

        # Build PostgreSQL connection URL from environment
        postgres_host = env_values.get("POSTGRES_HOST", "postgres")
        postgres_port = env_values.get("POSTGRES_PORT", "5432")
        postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
        postgres_user = env_values.get("POSTGRES_USER", "leyzen")
        postgres_password = env_values.get("POSTGRES_PASSWORD", "")

        if not postgres_password:
            # Password required for connection
            return ""

        # Create SQLAlchemy engine
        postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        engine = create_engine(postgres_url, pool_pre_ping=True)

        try:
            with engine.connect() as conn:
                # First check if table exists
                table_check = conn.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'system_secrets'
                        )
                    """
                    )
                )
                table_exists = table_check.fetchone()[0]

                if not table_exists:
                    # Table doesn't exist - token hasn't been generated yet
                    return ""

                # Query for the encrypted token value
                result = conn.execute(
                    text("SELECT encrypted_value FROM system_secrets WHERE key = :key"),
                    {"key": "internal_api_token"},
                )
                row = result.fetchone()

                if not row:
                    # Token not found in database - table exists but token not generated yet
                    return ""

                encrypted_value = row[0]

                # Derive Fernet key from SECRET_KEY for decryption
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"leyzen-vault-internal-token-v1",
                    iterations=100000,
                    backend=default_backend(),
                )
                fernet_key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
                cipher = Fernet(fernet_key)

                # Decrypt and return the token
                try:
                    decrypted_token = cipher.decrypt(encrypted_value.encode()).decode()
                    return decrypted_token
                except Exception as e:
                    # Decryption failed - token may be corrupted
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to decrypt INTERNAL_API_TOKEN from database: {e}. "
                        "Orchestrator will wait for vault to generate the token."
                    )
                    return ""
        finally:
            engine.dispose()

    except Exception as e:
        # Database access failed - return empty string
        # Orchestrator can still work, but internal API calls will fail until token is available
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to read INTERNAL_API_TOKEN from database: {e}. "
            "Orchestrator will wait for vault to generate the token. "
            "Set INTERNAL_API_TOKEN environment variable to bypass database lookup."
        )
        return ""


def load_settings() -> Settings:
    """Load orchestrator settings from environment variables.

    All environment variables are loaded from the .env file (or LEYZEN_ENV_FILE override)
    via load_env_with_override() and accessed through the env_values dictionary for
    consistency. The dictionary is used directly instead of os.environ to avoid side effects.
    """

    # Use the shared ORCHESTRATOR_DIR constant from common.constants
    base_dir = ORCHESTRATOR_DIR
    root_dir = base_dir.parent

    env_values = load_env_with_override(root_dir)
    # Merge with actual os.environ to allow runtime overrides
    env_values.update(os.environ)

    # Synchronize with Go validation in tools/cli/cmd/validate.go::parseTemplate()
    # These variables are required at runtime and must be present and non-empty.
    # When modifying this list, update the Go implementation to match.
    _ensure_required_variables(
        ["ORCH_USER", "ORCH_PASS", "SECRET_KEY"],
        env_values,
    )

    timezone = parse_timezone(env_values, allow_fallback=False)

    raw_containers = os.environ.get("ORCH_WEB_CONTAINERS")
    web_containers = parse_container_names(raw_containers)
    if not web_containers:
        # Default: generate vault_web1, vault_web2, vault_web3
        replicas_raw = env_values.get("WEB_REPLICAS", "3").strip()
        try:
            replicas = max(2, int(replicas_raw))  # Minimum 2 replicas
        except ValueError:
            replicas = 3
        web_containers = [f"vault_web{i+1}" for i in range(replicas)]

    if not web_containers:
        raise ConfigurationError(
            "No web containers configured; set WEB_REPLICAS (containers are auto-generated)"
        )

    if len(web_containers) < 2:
        raise ConfigurationError(
            f"Leyzen Vault requires minimum 2 replicas for rotation, got {len(web_containers)} containers: {', '.join(web_containers)}"
        )

    username = env_values.get("ORCH_USER", "")
    if not username:
        raise ConfigurationError(
            "ORCH_USER is required and cannot be empty. "
            "Set a non-default username in your .env file."
        )
    password = env_values.get("ORCH_PASS") or ""

    # Validate that credentials are not default values in production
    validate_default_credentials(username, password, env_values)

    password_hash = generate_password_hash(password)

    proxy_trust_count = parse_int_env_var(
        "PROXY_TRUST_COUNT", PROXY_TRUST_COUNT_DEFAULT, env_values, min_value=0
    )

    rotation_interval = parse_int_env_var(
        "ROTATION_INTERVAL", ROTATION_INTERVAL_DEFAULT, env_values, min_value=1
    )

    html_dir = base_dir
    log_file = _determine_log_file(base_dir, env_values)

    captcha_length = parse_int_env_var(
        "CAPTCHA_LENGTH", CAPTCHA_LENGTH_DEFAULT, env_values
    )

    captcha_store_ttl = parse_int_env_var(
        "CAPTCHA_STORE_TTL_SECONDS", CAPTCHA_STORE_TTL_SECONDS_DEFAULT, env_values
    )

    login_csrf_ttl = parse_int_env_var(
        "LOGIN_CSRF_TTL_SECONDS",
        LOGIN_CSRF_TTL_SECONDS_DEFAULT,
        env_values,
        min_value=60,
    )

    csp_report_max_size = parse_int_env_var(
        "CSP_REPORT_MAX_SIZE",
        CSP_REPORT_MAX_SIZE_DEFAULT,
        env_values,
        min_value=0,
        strip_quotes=True,
    )

    csp_report_rate_limit = parse_int_env_var(
        "CSP_REPORT_RATE_LIMIT",
        CSP_REPORT_RATE_LIMIT_DEFAULT,
        env_values,
        min_value=1,
        strip_quotes=True,
    )

    csp_report_rate_window = timedelta(seconds=CSP_REPORT_RATE_WINDOW_SECONDS)

    docker_proxy_url_raw = (
        env_values.get("DOCKER_PROXY_URL") or DOCKER_PROXY_BASE_URL_DEFAULT
    )
    docker_proxy_url = _validate_url(docker_proxy_url_raw, "DOCKER_PROXY_URL").rstrip(
        "/"
    )

    secret_key = env_values.get("SECRET_KEY", "")
    validate_secret_entropy(secret_key, min_length=32, secret_name="SECRET_KEY")

    # Generate docker proxy token automatically from SECRET_KEY
    docker_proxy_token = derive_docker_proxy_token(secret_key)

    # Internal API token derived deterministically from SECRET_KEY (like DOCKER_PROXY_TOKEN)
    # This avoids database dependency and ensures vault and orchestrator use the same token
    internal_api_token = env_values.get("INTERNAL_API_TOKEN", "")
    if not internal_api_token:
        internal_api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    # If not explicitly set, derive from SECRET_KEY
    if not internal_api_token:
        internal_api_token = derive_internal_api_token(secret_key)

    sse_stream_interval_ms = parse_int_env_var(
        "ORCH_SSE_INTERVAL_MS",
        SSE_INTERVAL_MS_DEFAULT,
        env_values,
        min_value=SSE_INTERVAL_MS_MINIMUM,
    )

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

    orchestrator_port = parse_int_env_var(
        "ORCH_PORT",
        ORCHESTRATOR_PORT_DEFAULT,
        env_values,
        min_value=1,
        max_value=65535,
    )

    return Settings(
        timezone=timezone,
        username=username,
        password_hash=password_hash,
        proxy_trust_count=proxy_trust_count,
        docker_proxy_url=docker_proxy_url,
        docker_proxy_token=docker_proxy_token,
        internal_api_token=internal_api_token,
        web_containers=list(web_containers),
        rotation_interval=rotation_interval,
        log_file=log_file,
        html_dir=html_dir,
        secret_key=secret_key,
        captcha_length=captcha_length,
        captcha_store_ttl=captcha_store_ttl,
        login_csrf_ttl=login_csrf_ttl,
        csp_report_max_size=csp_report_max_size,
        csp_report_rate_limit=csp_report_rate_limit,
        csp_report_rate_window=csp_report_rate_window,
        sse_stream_interval_ms=sse_stream_interval_ms,
        session_cookie_secure=session_cookie_secure,
        orchestrator_port=orchestrator_port,
    )


def reload_internal_api_token_from_db(settings: Settings) -> str:
    """Reload INTERNAL_API_TOKEN from database.

    This is a helper function for services that need to reload the token
    dynamically after initial settings load.

    Args:
        settings: Current orchestrator settings

    Returns:
        The internal API token string, or empty string if not available
    """
    import os
    from common.env import load_env_with_override

    # Load environment values
    root_dir = settings.html_dir.parent.parent
    env_values = load_env_with_override(root_dir)
    env_values.update(os.environ)

    # Get token from database
    return _get_internal_api_token_from_db(env_values, settings.secret_key)


__all__ = ["Settings", "load_settings", "reload_internal_api_token_from_db"]
