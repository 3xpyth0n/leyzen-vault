"""Configuration loading for the vault orchestrator application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

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


@dataclass(frozen=True)
class Settings:
    """Application settings derived from environment variables."""

    timezone: ZoneInfo
    username: str
    password_hash: str
    proxy_trust_count: int
    docker_proxy_url: str
    docker_proxy_token: str
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


def _parse_int_env_var(
    name: str,
    default: int,
    env: dict[str, str],
    min_value: int | None = None,
    max_value: int | None = None,
    *,
    strip_quotes: bool = False,
) -> int:
    """Parse an integer environment variable with optional min/max constraints.

    Args:
        name: Environment variable name
        default: Default value if variable is missing or invalid
        env: Dictionary containing environment variables
        min_value: Minimum value if specified (inclusive), None otherwise
        max_value: Maximum value if specified (inclusive), None otherwise
        strip_quotes: If True, strip matching quotes from the value

    Returns:
        Parsed integer value, or default if parsing fails
    """
    raw_value = env.get(name, str(default)).strip()
    if strip_quotes:
        raw_value = raw_value.strip('"').strip("'")
    try:
        value = int(raw_value)
        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value
    except ValueError:
        return default


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


_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    return default


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


def _validate_secret_length(var_name: str, value: str, min_length: int = 12) -> None:
    """Validate that a cryptographic secret meets minimum length requirements.

    Args:
        var_name: Name of the environment variable for error messages
        value: The secret value to validate
        min_length: Minimum required length (default: 12)

    Raises:
        ConfigurationError: If the secret is too short
    """
    if len(value) < min_length:
        raise ConfigurationError(
            f"{var_name} must be at least {min_length} characters long "
            f"for security (got {len(value)} characters)"
        )


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
        ["ORCH_USER", "ORCH_PASS", "SECRET_KEY", "DOCKER_PROXY_TOKEN"],
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
    password_hash = generate_password_hash(password)

    proxy_trust_count = _parse_int_env_var(
        "PROXY_TRUST_COUNT", PROXY_TRUST_COUNT_DEFAULT, env_values, min_value=0
    )

    rotation_interval = _parse_int_env_var(
        "ROTATION_INTERVAL", ROTATION_INTERVAL_DEFAULT, env_values, min_value=1
    )

    html_dir = base_dir
    log_file = _determine_log_file(base_dir, env_values)

    captcha_length = _parse_int_env_var(
        "CAPTCHA_LENGTH", CAPTCHA_LENGTH_DEFAULT, env_values
    )

    captcha_store_ttl = _parse_int_env_var(
        "CAPTCHA_STORE_TTL_SECONDS", CAPTCHA_STORE_TTL_SECONDS_DEFAULT, env_values
    )

    login_csrf_ttl = _parse_int_env_var(
        "LOGIN_CSRF_TTL_SECONDS",
        LOGIN_CSRF_TTL_SECONDS_DEFAULT,
        env_values,
        min_value=60,
    )

    csp_report_max_size = _parse_int_env_var(
        "CSP_REPORT_MAX_SIZE",
        CSP_REPORT_MAX_SIZE_DEFAULT,
        env_values,
        min_value=0,
        strip_quotes=True,
    )

    csp_report_rate_limit = _parse_int_env_var(
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
    docker_proxy_token = env_values.get("DOCKER_PROXY_TOKEN", "")
    _validate_secret_length("DOCKER_PROXY_TOKEN", docker_proxy_token)

    secret_key = env_values.get("SECRET_KEY", "")
    _validate_secret_length("SECRET_KEY", secret_key)

    sse_stream_interval_ms = _parse_int_env_var(
        "ORCH_SSE_INTERVAL_MS",
        SSE_INTERVAL_MS_DEFAULT,
        env_values,
        min_value=SSE_INTERVAL_MS_MINIMUM,
    )

    session_cookie_secure = _parse_bool(
        env_values.get("SESSION_COOKIE_SECURE"), default=True
    )

    orchestrator_port = _parse_int_env_var(
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


__all__ = ["Settings", "load_settings"]
