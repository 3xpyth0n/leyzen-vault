"""Shared constants across Leyzen Vault components."""

from __future__ import annotations

from pathlib import Path

# ============================================================================
# Configurable Constants (via environment variables)
# ============================================================================
# Constants with _DEFAULT suffix are configurable via environment variables.
# These values are used as defaults when the corresponding environment variable
# is not set or is invalid. The actual configuration loading happens in
# src/orchestrator/config.py::load_settings().

# CAPTCHA configuration defaults
CAPTCHA_LENGTH_DEFAULT = 6

# TTL configuration defaults (in seconds)
CAPTCHA_STORE_TTL_SECONDS_DEFAULT = 300
LOGIN_CSRF_TTL_SECONDS_DEFAULT = 900

# Environment variable defaults
TIMEZONE_DEFAULT = "UTC"
ROTATION_INTERVAL_DEFAULT = 600
DOCKER_PROXY_TIMEOUT_DEFAULT = 30
DOCKER_PROXY_LOG_LEVEL_DEFAULT = "INFO"

# CSP configuration defaults
CSP_REPORT_MAX_SIZE_DEFAULT = 4096
CSP_REPORT_RATE_LIMIT_DEFAULT = 5

# SSE stream configuration defaults
SSE_INTERVAL_MS_DEFAULT = 500

# Proxy configuration defaults
PROXY_TRUST_COUNT_DEFAULT = 1

# Docker configuration defaults
DOCKER_SOCKET_PATH_DEFAULT = "/var/run/docker.sock"
DOCKER_PROXY_BASE_URL_DEFAULT = "http://docker-proxy:2375"
DOCKER_PROXY_PORT_DEFAULT = 2375  # Default port for docker-proxy service

# Orchestrator configuration defaults
ORCHESTRATOR_PORT_DEFAULT = 80
ORCHESTRATOR_LOG_FILE_DEFAULT = "orchestrator.log"

# ============================================================================
# Fixed Constants (not user-configurable)
# ============================================================================
# Constants without _DEFAULT suffix are fixed security/behavioral constants
# that are hardcoded in the application logic and cannot be changed via
# environment variables. These represent security boundaries, rate limits,
# or behavioral constraints that are intentionally immutable.

# Login security configuration
MAX_LOGIN_ATTEMPTS = 5
LOGIN_BLOCK_WINDOW_MINUTES = 5

# CSP configuration
CSP_REPORT_RATE_WINDOW_SECONDS = 60

# SSE stream configuration
SSE_INTERVAL_MS_MINIMUM = 50

# ============================================================================
# Internal Constants (not user-configurable, implementation details)
# ============================================================================
# These constants are used internally by the application logic and represent
# implementation-specific values that don't need to be configurable.

# Docker proxy client configuration
DOCKER_PROXY_CLIENT_TIMEOUT_DEFAULT = (
    20.0  # Default timeout for HTTP requests (seconds)
)
DOCKER_PROXY_INSPECT_CACHE_TTL = 2.0  # Cache TTL for docker inspect results (seconds)

# Rotation service configuration
ROTATION_MAX_WORKERS = (
    8  # Maximum number of worker threads for parallel container stats retrieval
)
ROTATION_RETRY_INTERVAL = (
    2.0  # Interval between retries when docker proxy is unavailable (seconds)
)
ROTATION_QUIET_PERIOD = 5.0  # Quiet period before logging retry attempts (seconds)
ROTATION_WAIT_LOG_INTERVAL = 10.0  # Interval between wait log messages (seconds)

# Docker proxy service health check configuration
DOCKER_PROXY_HEALTH_CHECK_INTERVAL = 2  # Interval between health checks (seconds)
DOCKER_PROXY_HEALTH_LOG_INTERVAL = (
    30  # Interval between health check log messages (seconds)
)
DOCKER_PROXY_ERROR_LOG_INTERVAL = 5.0  # Interval between error log messages (seconds)

# Rotation service loop configuration
ROTATION_LOOP_SLEEP_INTERVAL = 1.0  # Sleep interval in main rotation loop (seconds)
ROTATION_ERROR_RETRY_SLEEP = 2.0  # Sleep interval after errors (seconds)
ROTATION_LONG_SLEEP = 5.0  # Long sleep interval for pause/resume operations (seconds)
ROTATION_METRICS_MIN_INTERVAL = 0.2  # Minimum interval for metrics collection (seconds)
ROTATION_DELAY_MIN = 0.05  # Minimum delay between operations (seconds)
ROTATION_SNAPSHOT_MIN_INTERVAL = 0.1  # Minimum interval for snapshot refresh (seconds)
ROTATION_FRESHNESS_BASE = 0.5  # Base freshness window multiplier (seconds)
ROTATION_FRESHNESS_MULTIPLIER = 2.5  # Multiplier for freshness window calculation
ROTATION_METRICS_REPORT_INTERVAL = 60.0  # Interval between metrics reports (seconds)

# Telemetry configuration
TELEMETRY_METRICS_WINDOW_SECONDS = 60.0  # Metrics history window (seconds)
TELEMETRY_CONTAINER_WINDOW_SECONDS = 300.0  # Container history window (seconds)
TELEMETRY_METRICS_CAP = 1800  # Maximum entries in metrics history
TELEMETRY_CONTAINER_CAP = 1200  # Maximum entries in container history
TELEMETRY_HISTORY_MIN_INTERVAL = (
    0.05  # Minimum interval for history calculation (seconds)
)
TELEMETRY_HISTORY_BUFFER = 2  # Buffer added to history maxlen calculation

# CAPTCHA generation constants (moved from auth.py)
CAPTCHA_NOISE_PIXELS = 300  # Number of noise pixels to add
CAPTCHA_DISTRACTION_LINES = 6  # Number of random lines to add
CAPTCHA_FONT_SIZE = 22  # Default font size for PIL
CAPTCHA_SVG_FONT_SIZE = 32  # Font size for SVG fallback

# Logging configuration
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # Maximum log file size (10MB)
LOG_FILE_BACKUP_COUNT = 5  # Number of backup log files to keep

# Cache configuration
STATIC_CACHE_MAX_AGE = 3600  # Cache max-age for static files (seconds)
SESSION_MAX_AGE_SECONDS = 108864  # Session max-age (seconds, ~30 days)

# URL validation
ALLOWED_URL_SCHEMES = ("http", "https")

# ============================================================================
# Path Constants (calculated at import time)
# ============================================================================
# These paths are calculated relative to this file's location to ensure they
# work regardless of the current working directory when the module is imported.

# Repository root path
# This path is calculated relative to this file's location (src/common/constants.py)
# to ensure it works regardless of the current working directory when the module is imported.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Source directory paths
# These paths are calculated relative to the repository root to ensure they work
# regardless of the current working directory when the module is imported.
SRC_DIR = REPO_ROOT / "src"

# Detect if we're running in a Docker container where orchestrator is mounted at /app
# More robust detection: check for multiple orchestrator-specific files/directories
# to avoid false positives (vault container also has /app but different structure)
_docker_app_path = Path("/app")
_orchestrator_indicators = [
    _docker_app_path / "__init__.py",  # Orchestrator has __init__.py at root
    _docker_app_path / "blueprints",  # Orchestrator-specific directory
    _docker_app_path / "templates" / "login.html",  # Orchestrator template
]

_is_orchestrator_container = _docker_app_path.exists() and all(
    indicator.exists() for indicator in _orchestrator_indicators
)

if _is_orchestrator_container:
    # Running in Docker container: orchestrator is mounted at /app
    ORCHESTRATOR_DIR = _docker_app_path
else:
    # Local development: use calculated path relative to repository root
    ORCHESTRATOR_DIR = SRC_DIR / "orchestrator"

DOCKER_PROXY_DIR = REPO_ROOT / "infra" / "docker-proxy"

# HAProxy configuration
# These paths are calculated relative to the repository root to ensure they work
# regardless of the current working directory when the module is imported.
HAPROXY_CONFIG_PATH = REPO_ROOT / "infra/haproxy/haproxy.cfg"
HAPROXY_404_ERROR_PATH = REPO_ROOT / "infra/haproxy/404.http"
HAPROXY_503_ERROR_PATH = REPO_ROOT / "infra/haproxy/503.http"

__all__ = [
    "CAPTCHA_LENGTH_DEFAULT",
    "MAX_LOGIN_ATTEMPTS",
    "LOGIN_BLOCK_WINDOW_MINUTES",
    "TIMEZONE_DEFAULT",
    "ROTATION_INTERVAL_DEFAULT",
    "DOCKER_PROXY_TIMEOUT_DEFAULT",
    "DOCKER_PROXY_LOG_LEVEL_DEFAULT",
    "CSP_REPORT_MAX_SIZE_DEFAULT",
    "CSP_REPORT_RATE_LIMIT_DEFAULT",
    "CSP_REPORT_RATE_WINDOW_SECONDS",
    "SSE_INTERVAL_MS_DEFAULT",
    "SSE_INTERVAL_MS_MINIMUM",
    "CAPTCHA_STORE_TTL_SECONDS_DEFAULT",
    "LOGIN_CSRF_TTL_SECONDS_DEFAULT",
    "PROXY_TRUST_COUNT_DEFAULT",
    "DOCKER_SOCKET_PATH_DEFAULT",
    "DOCKER_PROXY_BASE_URL_DEFAULT",
    "DOCKER_PROXY_PORT_DEFAULT",
    "ALLOWED_URL_SCHEMES",
    "ORCHESTRATOR_PORT_DEFAULT",
    "ORCHESTRATOR_LOG_FILE_DEFAULT",
    "DOCKER_PROXY_CLIENT_TIMEOUT_DEFAULT",
    "DOCKER_PROXY_INSPECT_CACHE_TTL",
    "ROTATION_MAX_WORKERS",
    "ROTATION_RETRY_INTERVAL",
    "ROTATION_QUIET_PERIOD",
    "ROTATION_WAIT_LOG_INTERVAL",
    "DOCKER_PROXY_HEALTH_CHECK_INTERVAL",
    "DOCKER_PROXY_HEALTH_LOG_INTERVAL",
    "DOCKER_PROXY_ERROR_LOG_INTERVAL",
    "ROTATION_LOOP_SLEEP_INTERVAL",
    "ROTATION_ERROR_RETRY_SLEEP",
    "ROTATION_LONG_SLEEP",
    "ROTATION_METRICS_MIN_INTERVAL",
    "ROTATION_DELAY_MIN",
    "ROTATION_SNAPSHOT_MIN_INTERVAL",
    "ROTATION_FRESHNESS_BASE",
    "ROTATION_FRESHNESS_MULTIPLIER",
    "ROTATION_METRICS_REPORT_INTERVAL",
    "TELEMETRY_METRICS_WINDOW_SECONDS",
    "TELEMETRY_CONTAINER_WINDOW_SECONDS",
    "TELEMETRY_METRICS_CAP",
    "TELEMETRY_CONTAINER_CAP",
    "TELEMETRY_HISTORY_MIN_INTERVAL",
    "TELEMETRY_HISTORY_BUFFER",
    "CAPTCHA_NOISE_PIXELS",
    "CAPTCHA_DISTRACTION_LINES",
    "CAPTCHA_FONT_SIZE",
    "CAPTCHA_SVG_FONT_SIZE",
    "LOG_FILE_MAX_BYTES",
    "LOG_FILE_BACKUP_COUNT",
    "STATIC_CACHE_MAX_AGE",
    "SESSION_MAX_AGE_SECONDS",
    "REPO_ROOT",
    "SRC_DIR",
    "ORCHESTRATOR_DIR",
    "DOCKER_PROXY_DIR",
    "HAPROXY_CONFIG_PATH",
    "HAPROXY_404_ERROR_PATH",
    "HAPROXY_503_ERROR_PATH",
]
