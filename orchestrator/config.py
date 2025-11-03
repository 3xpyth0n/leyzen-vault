"""Configuration loading for the vault orchestrator application."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import pytz
from werkzeug.security import generate_password_hash

from leyzen_common.env import load_env_with_override, parse_container_names
from leyzen_common.exceptions import ConfigurationError
from vault_plugins.registry import get_active_plugin


@dataclass(frozen=True)
class Settings:
    """Application settings derived from environment variables."""

    timezone: pytz.BaseTzInfo
    username: str
    password_hash: str
    proxy_trust_count: int
    docker_proxy_url: str
    docker_proxy_token: str
    web_containers: List[str]
    rotation_interval: int
    log_file: Path
    html_dir: Path
    secret_key: str
    captcha_image_width: int
    captcha_image_height: int
    captcha_length: int
    captcha_store_ttl: int
    login_csrf_ttl: int
    csp_report_max_size: int
    csp_report_rate_limit: int
    csp_report_rate_window: timedelta
    sse_stream_interval_ms: int
    session_cookie_secure: bool

    @property
    def log_dir(self) -> Path:
        return self.log_file.parent

    @property
    def sse_stream_interval_seconds(self) -> float:
        """Return the SSE stream interval expressed in seconds."""

        return max(0.05, self.sse_stream_interval_ms / 1000.0)


def _ensure_required_variables(required: List[str]) -> None:
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(sorted(missing))}"
        )


def _determine_log_file(base_dir: Path) -> Path:
    override = os.environ.get("ORCHESTRATOR_LOG_DIR")
    if override:
        candidate = Path(override).expanduser().resolve()
    else:
        candidate = base_dir

    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        candidate = base_dir

    filename = os.environ.get("ORCHESTRATOR_LOG_FILE", "orchestrator.log")
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


def _parse_bool(value: Optional[str], *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    return default


def load_settings() -> Settings:
    """Load orchestrator settings from environment variables."""

    base_dir = Path(__file__).resolve().parent
    root_dir = base_dir.parent

    env_values = load_env_with_override(root_dir)
    for key, val in env_values.items():
        os.environ[key] = val

    _ensure_required_variables(
        ["VAULT_USER", "VAULT_PASS", "VAULT_SECRET_KEY", "DOCKER_PROXY_TOKEN"]
    )

    timezone_name = os.getenv("TIMEZONE", "UTC")
    try:
        timezone = pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError as exc:
        raise ConfigurationError(f"Unknown timezone '{timezone_name}'") from exc

    raw_containers = os.environ.get("VAULT_WEB_CONTAINERS")
    web_containers = parse_container_names(raw_containers)
    if not web_containers:
        try:
            plugin = get_active_plugin(os.environ)
            web_containers = list(plugin.get_containers())
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning(
                "Failed to determine web containers from plugin: %s", exc, exc_info=True
            )
            raise ConfigurationError(
                "Unable to determine web containers; set VAULT_WEB_CONTAINERS"
            ) from exc

    if not web_containers:
        raise ConfigurationError(
            "No web containers configured; set VAULT_WEB_CONTAINERS or VAULT_SERVICE"
        )

    username = os.environ.get("VAULT_USER", "admin")
    password = os.environ.get("VAULT_PASS") or ""
    password_hash = generate_password_hash(password)

    proxy_trust_raw = os.environ.get("PROXY_TRUST_COUNT", "1").strip()
    try:
        proxy_trust_count = max(0, int(proxy_trust_raw))
    except ValueError:
        proxy_trust_count = 1

    rotation_raw = os.environ.get("VAULT_ROTATION_INTERVAL", "120").strip('"')
    try:
        rotation_interval = max(1, int(rotation_raw))
    except ValueError:
        rotation_interval = 120

    html_dir = base_dir
    log_file = _determine_log_file(base_dir)

    captcha_image_width = int(os.getenv("CAPTCHA_IMAGE_WIDTH", "220"))
    captcha_image_height = int(os.getenv("CAPTCHA_IMAGE_HEIGHT", "70"))
    captcha_length = int(os.getenv("CAPTCHA_LENGTH", "6"))
    captcha_store_ttl = int(os.getenv("CAPTCHA_STORE_TTL_SECONDS", "300"))
    login_csrf_ttl = max(60, int(os.getenv("LOGIN_CSRF_TTL_SECONDS", "900")))

    csp_report_max_default = 4096
    csp_report_max_raw = os.environ.get(
        "CSP_REPORT_MAX_SIZE", str(csp_report_max_default)
    ).strip()
    try:
        csp_report_max_size = max(0, int(csp_report_max_raw.strip('"')))
    except ValueError:
        csp_report_max_size = csp_report_max_default

    csp_rate_limit_default = 5
    csp_rate_limit_raw = os.environ.get(
        "CSP_REPORT_RATE_LIMIT", str(csp_rate_limit_default)
    ).strip()
    try:
        csp_report_rate_limit = max(1, int(csp_rate_limit_raw.strip('"')))
    except ValueError:
        csp_report_rate_limit = csp_rate_limit_default

    csp_report_rate_window = timedelta(seconds=60)

    docker_proxy_url = (
        os.environ.get("DOCKER_PROXY_URL") or "http://docker-proxy:2375"
    ).rstrip("/")
    docker_proxy_token = os.environ.get("DOCKER_PROXY_TOKEN", "")

    secret_key = os.environ.get("VAULT_SECRET_KEY", "")

    try:
        sse_stream_interval_ms = max(
            50, int(os.getenv("ORCHESTRATOR_SSE_INTERVAL_MS", "500"))
        )
    except ValueError:
        sse_stream_interval_ms = 500

    session_cookie_secure = _parse_bool(
        os.environ.get("VAULT_SESSION_COOKIE_SECURE"), default=True
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
        captcha_image_width=captcha_image_width,
        captcha_image_height=captcha_image_height,
        captcha_length=captcha_length,
        captcha_store_ttl=captcha_store_ttl,
        login_csrf_ttl=login_csrf_ttl,
        csp_report_max_size=csp_report_max_size,
        csp_report_rate_limit=csp_report_rate_limit,
        csp_report_rate_window=csp_report_rate_window,
        sse_stream_interval_ms=sse_stream_interval_ms,
        session_cookie_secure=session_cookie_secure,
    )


__all__ = ["Settings", "load_settings"]
