"""Flask application for Leyzen Vault backend."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask

# Bootstrap common modules
_COMMON_DIR = Path("/common")
if _COMMON_DIR.exists() and _COMMON_DIR.is_dir():
    root_path = str(_COMMON_DIR.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
else:
    _SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point  # noqa: E402
from common.token_utils import derive_internal_api_token  # noqa: E402

bootstrap_entry_point()


def _normalize_origin(origin: str | None) -> str | None:
    """Return normalized scheme://host[:port] representation for an origin."""
    if not origin:
        return None
    origin = origin.strip()
    if not origin:
        return None

    try:
        parsed = urlsplit(origin)
    except Exception:
        return None

    if not parsed.scheme or not parsed.netloc:
        return None

    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return normalized.rstrip("/")


from .blueprints.admin import admin_api_bp  # noqa: E402
from .blueprints.auth import auth_bp  # noqa: E402
from .blueprints.auth_api import auth_api_bp  # noqa: E402
from .blueprints.files_api_v2 import files_api_bp  # noqa: E402
from .blueprints.internal_api import internal_api_bp  # noqa: E402
from .blueprints.quota_api import quota_api_bp as quota_api_v2_bp  # noqa: E402
from .blueprints.search_api import search_api_bp  # noqa: E402
from .blueprints.security import security_bp  # noqa: E402
from .blueprints.sharing_api import sharing_api_bp  # noqa: E402
from .blueprints.sso_api import sso_api_bp  # noqa: E402
from .blueprints.thumbnail_api import thumbnail_api_bp  # noqa: E402
from .blueprints.trash_api import trash_api_bp  # noqa: E402
from .blueprints.vaultspaces import vaultspace_api_bp  # noqa: E402
from .config import (
    VaultSettings,
    get_postgres_url,
    is_setup_complete,
    load_settings,
)  # noqa: E402
from .database import db, init_db  # noqa: E402
from .services.totp_service import init_totp_service  # noqa: E402

# CSRF disabled - using JWT-only authentication
# from .extensions import csrf  # noqa: E402

from .services.audit import AuditService  # noqa: E402
from common.services.logging import FileLogger  # noqa: E402
from .services.rate_limiter import RateLimiter  # noqa: E402
from .services.share_link_service import ShareService  # noqa: E402
from .storage import FileStorage  # noqa: E402


def _create_fallback_settings() -> VaultSettings:
    """Create fallback VaultSettings for development/testing.

    This function creates default settings when the main configuration
    cannot be loaded. It attempts to read the timezone from environment
    variables, falling back to UTC if not available or invalid.

    ⚠️ WARNING: This fallback mode requires environment variables to be set.
    Hardcoded secrets have been removed for security. This function should
    NOT be used in production.

    Raises:
        ConfigurationError: If required environment variables are missing

    Returns:
        VaultSettings with values from environment variables
    """
    import os
    from common.env import parse_timezone
    from common.exceptions import ConfigurationError

    # Try to get timezone from environment even in fallback
    # Use allow_fallback=True to gracefully fall back to UTC on error
    fallback_timezone = parse_timezone(allow_fallback=True)

    # Secret key (required)
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError(
            "SECRET_KEY is required (minimum 32 characters). Fallback mode requires environment variables to be set. "
            "This function should NOT be used in production."
        )

    if len(secret_key) < 32:
        raise ConfigurationError(
            "SECRET_KEY must be at least 32 characters long. "
            "Generate a secure key with: openssl rand -hex 32"
        )

    return VaultSettings(
        secret_key=secret_key,
        timezone=fallback_timezone,
        proxy_trust_count=1,
        captcha_length=6,
        captcha_store_ttl=300,
        login_csrf_ttl=900,
        log_file=Path("/dev/shm/vault.log"),
        session_cookie_secure=False,
        max_file_size_mb=100,
        max_uploads_per_hour=50,
        audit_retention_days=90,
    )


def _get_or_generate_internal_api_token(
    env_values: dict[str, str],
    secret_key: str | None = None,
    logger=None,
) -> str:
    """Get or generate INTERNAL_API_TOKEN from environment or SECRET_KEY.

    This function centralizes the logic for obtaining the INTERNAL_API_TOKEN.
    It first checks environment variables, then generates from SECRET_KEY if needed.

    Args:
        env_values: Dictionary containing environment variables
        secret_key: Optional secret key to use for token generation
        logger: Optional logger instance for warning messages

    Returns:
        The internal API token string
    """
    import os

    # Check environment variables first
    internal_api_token = env_values.get("INTERNAL_API_TOKEN", "")
    if not internal_api_token:
        internal_api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    # If not set, generate automatically from SECRET_KEY
    if not internal_api_token and secret_key:
        internal_api_token = derive_internal_api_token(secret_key)
    elif not internal_api_token and logger:
        logger.log(
            "[WARNING] INTERNAL_API_TOKEN not set and SECRET_KEY not available. "
            "Internal API endpoints will be disabled."
        )

    return internal_api_token or ""


def create_app(
    storage_dir: Path | None = None,
    *args: object,
    **kwargs: object,
) -> Flask:
    """Create and configure the Flask application."""
    # Get the directory containing this file
    vault_dir = Path(__file__).parent

    # Check if dist/ exists (production build) or use static/ (development)
    static_dir = vault_dir / "static" / "dist"
    if not static_dir.exists():
        static_dir = vault_dir / "static"

    # Also keep reference to original static folder for fallback
    original_static_dir = vault_dir / "static"

    # Don't use Flask's default static folder mechanism - we'll handle it manually
    app = Flask(
        __name__,
        template_folder=str(vault_dir / "templates"),
        static_folder=None,  # Disable default static file serving
        static_url_path=None,
    )

    # Load environment values first
    # Import os here (already imported at top level) - this import is redundant but kept for clarity
    import os

    env_values = {}
    try:
        # Import here to avoid circular dependency with common.env during module initialization
        from common.env import load_env_with_override

        env_values = load_env_with_override()
        env_values.update(os.environ)
    except Exception:
        pass

    # Detect production environment
    # Default to production for security (hide error details by default)
    leylen_env = env_values.get("LEYZEN_ENVIRONMENT", "").strip().lower()
    is_production = leylen_env not in ("dev", "development")
    app.config["IS_PRODUCTION"] = is_production

    # Load settings
    try:
        settings = load_settings()
        app.config["VAULT_SETTINGS"] = settings
        app.config["SECRET_KEY"] = settings.secret_key
        # Configure session cookies
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        )
        # Initialize logger
        logger = FileLogger(settings)
        app.config["LOGGER"] = logger

        # Internal API token for orchestrator operations
        # Auto-generate from SECRET_KEY if not explicitly set
        internal_api_token = _get_or_generate_internal_api_token(
            env_values, settings.secret_key, logger
        )
        app.config["INTERNAL_API_TOKEN"] = internal_api_token

        # Configure PostgreSQL database
        try:
            postgres_url = get_postgres_url(env_values)
            app.config["SQLALCHEMY_DATABASE_URI"] = postgres_url
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            app.config["SQLALCHEMY_COMMIT_ON_TEARDOWN"] = (
                False  # Explicitly disable auto-commit on teardown
            )
            init_db(app)
            logger.log("[INIT] PostgreSQL database initialized")

            # Initialize TOTP service for 2FA
            init_totp_service(settings.secret_key)
            logger.log("[INIT] TOTP service initialized")

            # Check if setup is complete
            try:
                if not is_setup_complete(app):
                    logger.log(
                        "[WARNING] Setup not complete. Visit /setup to create superadmin account."
                    )
                else:
                    logger.log("[INIT] Setup complete - users exist in database")
            except Exception as setup_check_error:
                logger.log(
                    f"[WARNING] Failed to check setup status: {setup_check_error}"
                )
        except Exception as db_exc:
            # Log the error with full details
            # Import traceback here to avoid importing it at module level if not needed
            import traceback

            error_details = (
                f"Failed to initialize PostgreSQL: {db_exc}\n{traceback.format_exc()}"
            )
            logger.log(f"[ERROR] {error_details}")

            # In production, fail startup if PostgreSQL is unavailable
            # In development mode, allow fallback for testing
            if is_production:
                raise RuntimeError(
                    "PostgreSQL database initialization failed. "
                    "Leyzen Vault requires PostgreSQL to run in production mode. "
                    "Please ensure PostgreSQL is available and properly configured. "
                    "Set LEYZEN_ENVIRONMENT=dev only for development/testing."
                ) from db_exc
            else:
                # Development mode: log warning but continue
                logger.log(
                    "[WARNING] Continuing without PostgreSQL (development mode only). "
                    "This is not recommended for production use."
                )
                # Continue without PostgreSQL for development/testing only
    except Exception as exc:
        # Fallback for development/testing only - NOT allowed in production
        # Note: This fallback now requires environment variables to be set
        # Hardcoded secrets have been removed for security

        # SECURITY: Prevent fallback mode in production
        # If we're in production mode, fail fast rather than using fallback settings
        if is_production:
            raise RuntimeError(
                "Cannot start in production mode without valid configuration. "
                "The application failed to load settings and fallback mode is not allowed in production. "
                "Please check your environment variables and configuration files. "
                "Set LEYZEN_ENVIRONMENT=dev only for development/testing."
            ) from exc

        # Set IS_PRODUCTION if not already set (default to False for fallback mode)
        if "IS_PRODUCTION" not in app.config:
            app.config["IS_PRODUCTION"] = is_production

        fallback_settings = _create_fallback_settings()
        app.config["SECRET_KEY"] = fallback_settings.secret_key
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=False,
        )
        app.config["VAULT_SETTINGS"] = fallback_settings
        app.config["LOGGER"] = FileLogger(fallback_settings)
        # Internal API token for orchestrator operations
        # Auto-generate from SECRET_KEY if available
        internal_api_token = _get_or_generate_internal_api_token(
            env_values, fallback_settings.secret_key, None
        )
        app.config["INTERNAL_API_TOKEN"] = internal_api_token

    # Configure allowed origins (CORS + Origin validation)
    vault_settings = app.config.get("VAULT_SETTINGS")
    allowed_origins_value = (
        env_values.get("VAULT_ALLOWED_ORIGINS")
        or env_values.get("ALLOWED_ORIGINS")
        or env_values.get("CORS_ALLOWED_ORIGINS")
    )
    allowed_origins: list[str] = []
    if allowed_origins_value:
        for origin in allowed_origins_value.split(","):
            normalized = origin.strip()
            if normalized:
                allowed_origins.append(normalized.rstrip("/"))
    elif vault_settings and vault_settings.vault_url:
        allowed_origins.append(vault_settings.vault_url.rstrip("/"))

    app.config["ALLOWED_ORIGINS"] = allowed_origins
    app.config["ALLOWED_ORIGINS_NORMALIZED"] = {
        normalized
        for normalized in (_normalize_origin(origin) for origin in allowed_origins)
        if normalized
    }
    # Default list of headers allowed for CORS requests
    app.config.setdefault(
        "ALLOWED_CORS_HEADERS",
        "Authorization, Content-Type, X-Requested-With, Accept, X-CSRF-Token",
    )

    # CSRF protection disabled - using JWT-only authentication
    # JWT tokens in Authorization headers are protected by Same-Origin Policy
    # Additional security provided by Origin/Referer validation in jwt_required decorator
    # csrf.init_app(app)  # Disabled - not needed for JWT-based API
    # No additional configuration needed for FormData uploads

    # Default paths - ensure they are Path objects
    if storage_dir is None:
        storage_dir = Path("/data")
    elif not isinstance(storage_dir, Path):
        # Convert to Path if it's not already a Path object
        storage_dir = Path(str(storage_dir))

    # Source directory for persistent storage (mounted from vault-data-source volume)
    # Note: source_dir should point to the parent directory, FileStorage will handle /files subdirectory
    source_dir = Path("/data-source") if Path("/data-source").exists() else None

    # Initialize storage with primary directory (tmpfs) and source directory (persistent)
    # FileStorage will check source_dir/files if file is not found in storage_dir/files
    storage = FileStorage(storage_dir, source_dir=source_dir)

    # Initialize audit service (uses PostgreSQL)
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            audit_service = AuditService(
                timezone=settings.timezone,
                retention_days=settings.audit_retention_days,
            )
        else:
            # Fallback: use UTC and default retention
            from zoneinfo import ZoneInfo

            audit_service = AuditService(timezone=ZoneInfo("UTC"), retention_days=90)
    except Exception:
        # Fallback: use UTC and default retention
        from zoneinfo import ZoneInfo

        audit_service = AuditService(timezone=ZoneInfo("UTC"), retention_days=90)

    # Initialize share service (uses PostgreSQL)
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            share_service = ShareService(timezone=settings.timezone)
        else:
            # Fallback: use UTC
            from zoneinfo import ZoneInfo

            share_service = ShareService(timezone=ZoneInfo("UTC"))
    except Exception:
        # Fallback: use UTC
        from zoneinfo import ZoneInfo

        share_service = ShareService(timezone=ZoneInfo("UTC"))

    # Initialize rate limiter
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            rate_limiter = RateLimiter(settings)
        else:
            # Fallback: create with default settings
            fallback_settings = _create_fallback_settings()
            rate_limiter = RateLimiter(fallback_settings)
    except Exception:
        # Fallback rate limiter
        fallback_settings = _create_fallback_settings()
        rate_limiter = RateLimiter(fallback_settings)

    # Store services in app config
    app.config["VAULT_STORAGE"] = storage
    app.config["VAULT_AUDIT"] = audit_service
    app.config["VAULT_SHARE"] = share_service
    app.config["VAULT_RATE_LIMITER"] = rate_limiter
    # Internal API token for orchestrator operations
    # Auto-generate from SECRET_KEY if not explicitly set
    secret_key = app.config.get("SECRET_KEY") or env_values.get("SECRET_KEY", "")
    internal_api_token = _get_or_generate_internal_api_token(
        env_values, secret_key, None
    )
    app.config["INTERNAL_API_TOKEN"] = internal_api_token

    # Start background thread for automatic audit log cleanup
    def _audit_cleanup_worker() -> None:
        """Background worker to periodically clean up old audit logs."""
        # Import here to avoid importing at module level if worker thread is not started
        import time
        import logging

        logger = logging.getLogger(__name__)
        while True:
            try:
                time.sleep(3600)  # Run every hour
                # Use application context for database operations
                with app.app_context():
                    deleted_count = audit_service.cleanup_old_logs()
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old audit log entries")
            except Exception as e:
                logger.error(f"Error during audit log cleanup: {e}", exc_info=True)

    # Import threading here to avoid importing at module level if cleanup thread is not started
    import threading

    cleanup_thread = threading.Thread(target=_audit_cleanup_worker, daemon=True)
    cleanup_thread.start()

    # NOTE: Storage cleanup worker is now in orchestrator (not vault)
    # This avoids issues with MTD container restarts every 2 minutes
    # Storage cleanup is triggered via internal API endpoint from orchestrator

    def _origin_is_allowed_for_request(origin: str | None) -> bool:
        """Check if the provided Origin header is allowed for this request."""
        if not origin:
            return False

        normalized_origin = _normalize_origin(origin)
        if not normalized_origin:
            return False

        from flask import request

        host_origin = _normalize_origin(f"{request.scheme}://{request.host}")
        allowed_set = app.config.get("ALLOWED_ORIGINS_NORMALIZED", set())

        if host_origin and normalized_origin == host_origin:
            return True

        return normalized_origin in allowed_set

    # Register blueprints
    app.register_blueprint(admin_api_bp)  # Admin API
    app.register_blueprint(
        auth_bp
    )  # Legacy auth (session-based, for CAPTCHA/logout until fully migrated)
    app.register_blueprint(auth_api_bp)  # JWT-based auth API
    app.register_blueprint(files_api_bp)  # Advanced files API v2

    # Debug: Log upload routes registration
    import logging

    logger = logging.getLogger(__name__)
    upload_routes = [r.rule for r in app.url_map.iter_rules() if "upload" in r.rule]
    if upload_routes:
        logger.info(f"Registered upload routes: {upload_routes}")
    app.register_blueprint(internal_api_bp)  # Internal API for orchestrator
    app.register_blueprint(search_api_bp)  # Search API
    app.register_blueprint(sso_api_bp)  # SSO API (SAML, OAuth2, OIDC)
    app.register_blueprint(trash_api_bp)  # Trash API v2
    app.register_blueprint(quota_api_v2_bp)  # Quota API v2
    app.register_blueprint(sharing_api_bp)  # Advanced Sharing API v2
    app.register_blueprint(thumbnail_api_bp)  # Thumbnail API v2
    app.register_blueprint(security_bp)  # Security stats
    app.register_blueprint(vaultspace_api_bp)  # VaultSpaces API

    # Route registration complete - no debug logging in production

    # Custom static file handler - check dist/ first, then fallback to static/
    # This must be registered AFTER blueprints to have priority
    @app.route("/static/<path:filename>")
    def serve_static_fallback(filename):
        """Serve static files from dist/ first, then fallback to static/.

        Optimized to use try/except instead of exists() checks for better performance.
        This prevents HAProxy from returning 503 due to slow file system operations.
        """
        from flask import send_from_directory, abort
        from werkzeug.exceptions import NotFound
        import logging

        logger = logging.getLogger(__name__)

        # If filename starts with "assets/", it's from Vue.js build
        # Request: /static/assets/index-BNuRR0jV.js
        # Should serve: dist/assets/index-BNuRR0jV.js
        if filename.startswith("assets/"):
            dist_dir = vault_dir / "static" / "dist"
            if dist_dir.exists():
                try:
                    # Try to serve directly - faster than checking existence first
                    response = send_from_directory(str(dist_dir), filename)
                    # Add cache headers for static assets
                    response.cache_control.public = True
                    response.cache_control.max_age = 31536000  # 1 year
                    return response
                except NotFound:
                    # File doesn't exist in dist/assets/, continue to next check
                    pass
                except Exception as e:
                    logger.error(f"Error serving asset {filename}: {e}", exc_info=True)
                    abort(500)

        # Try dist/ first (for Vue.js build assets and index.html)
        try:
            response = send_from_directory(str(static_dir), filename)
            # Add cache headers for static assets
            response.cache_control.public = True
            response.cache_control.max_age = 31536000  # 1 year
            return response
        except NotFound:
            # File doesn't exist in dist/, try static/ fallback
            pass
        except Exception as e:
            logger.error(f"Error serving file {filename} from dist: {e}", exc_info=True)
            abort(500)

        # Fallback to original static/ (for legacy files like vault.css, vault.js, etc.)
        try:
            response = send_from_directory(str(original_static_dir), filename)
            # Add cache headers for static assets
            response.cache_control.public = True
            response.cache_control.max_age = 31536000  # 1 year
            return response
        except NotFound:
            # File not found anywhere
            logger.warning(f"Static file not found: {filename}")
            abort(404)
        except Exception as e:
            logger.error(
                f"Error serving file {filename} from static: {e}", exc_info=True
            )
            abort(500)

    @app.after_request
    def save_session(response):
        """Ensure session is saved before sending response."""
        # Flask sessions are automatically saved, but explicitly mark as modified
        # to ensure it persists before redirects
        from flask import session

        if session.get("logged_in") and session.modified:
            # Session will be automatically saved by Flask
            pass
        return response

    @app.before_request
    def handle_cors_preflight():
        """Handle restrictive CORS preflight checks."""
        from flask import make_response, jsonify, request

        if request.method != "OPTIONS":
            return None

        origin = request.headers.get("Origin")
        if origin and _origin_is_allowed_for_request(origin):
            response = make_response("", 204)
            response.headers["Content-Length"] = "0"
            return response

        if origin:
            return jsonify({"error": "CORS origin not allowed"}), 403

        return None

    @app.before_request
    def generate_csp_nonce():
        """Generate CSP nonce for each request and make it available to templates."""
        # Import secrets here to avoid importing at module level if not needed
        import secrets
        from flask import g

        # Debug: Log API upload requests to see if they reach Flask
        from flask import request

        if request.path.startswith("/api/") and "upload" in request.path:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"API upload request received: {request.method} {request.path}, "
                f"Content-Length: {request.headers.get('Content-Length', 'unknown')}"
            )

        # Generate a secure random nonce (base64url encoded, 16 bytes = 128 bits)
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_csp_nonce():
        """Make CSP nonce available to all templates."""
        from flask import g

        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def add_security_headers(response):
        """Add strict security headers including CSP."""
        # Import json here to avoid importing at module level if not needed
        import json
        from flask import current_app, g, request
        from common.constants import SESSION_MAX_AGE_SECONDS

        # Get CSP nonce for this request
        csp_nonce = getattr(g, "csp_nonce", "")

        # Content Security Policy - enhanced with trusted types and reporting
        csp_directives = [
            "default-src 'self'",
            (
                f"script-src 'self' 'nonce-{csp_nonce}' https://static.cloudflareinsights.com"
                if csp_nonce
                else "script-src 'self' https://static.cloudflareinsights.com"
            ),
            "style-src 'self' https://fonts.googleapis.com",
            "img-src 'self' data: blob:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://static.cloudflareinsights.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests",
            "trusted-types vault-html notifications-html vault-script-url vue goog#html",
            "require-trusted-types-for 'script'",
            "report-uri /orchestrator/csp-violation-report-endpoint",
            "report-to vault-csp",
        ]
        csp_policy = "; ".join(csp_directives)

        # Add or merge CSP policy
        if existing_csp := response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = (
                f"{existing_csp}; {csp_policy}"
            )
        else:
            response.headers["Content-Security-Policy"] = csp_policy

        # Add Report-To header pointing to orchestrator CSP endpoint
        # Use the same format as orchestrator for consistency
        # Construct orchestrator URL from current request
        orchestrator_url = None
        use_fallback = False
        try:
            from flask import request
            from urllib.parse import urlparse

            # Construct URL from request context
            constructed_url = f"{request.scheme}://{request.host}/orchestrator/csp-violation-report-endpoint"
            # Validate URL format
            parsed = urlparse(constructed_url)
            if parsed.scheme and parsed.netloc:
                orchestrator_url = constructed_url
            else:
                use_fallback = True
        except Exception:
            # Fallback: use relative URL if request context unavailable or URL invalid
            use_fallback = True

        if use_fallback or not orchestrator_url:
            orchestrator_url = "/orchestrator/csp-violation-report-endpoint"
            # Log warning if fallback is used (only in development to avoid log spam)
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                current_app.logger.debug(
                    "CSP Report-To: Using fallback relative URL (request context unavailable or invalid)"
                )

        report_to = {
            "group": "vault-csp",
            "max_age": SESSION_MAX_AGE_SECONDS,
            "endpoints": [{"url": orchestrator_url}],
        }

        response.headers["Report-To"] = json.dumps(report_to)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers["X-Frame-Options"] = "DENY"

        # Enforce additional security headers
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        # Strict-Transport-Security (only when HTTPS is expected)
        settings = current_app.config.get("VAULT_SETTINGS")
        enforce_https = bool(settings and settings.session_cookie_secure)
        if enforce_https or request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )

        # Restrictive CORS headers
        origin_header = request.headers.get("Origin")
        allowed_cors_headers = current_app.config.get(
            "ALLOWED_CORS_HEADERS",
            "Authorization, Content-Type, X-Requested-With, Accept, X-CSRF-Token",
        )
        if origin_header and _origin_is_allowed_for_request(origin_header):
            response.headers["Access-Control-Allow-Origin"] = origin_header
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET,POST,PUT,PATCH,DELETE,OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = allowed_cors_headers
            response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers.add("Vary", "Origin")
        elif request.method == "OPTIONS" and origin_header:
            # Preflight request from disallowed origin -> ensure browsers fail fast
            response.status_code = 403

        return response

    @app.route("/favicon.ico")
    def favicon():
        """Serve favicon."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static"), "favicon.png", mimetype="image/png"
        )

    @app.route("/healthz")
    def healthz():
        """Health check endpoint - must respond quickly for HAProxy."""
        # Return immediately without any database checks to ensure fast response
        # This prevents HAProxy from marking the backend as down
        from flask import Response

        return Response('{"status":"ok"}', mimetype="application/json", status=200)

    # All frontend routes (/share) are handled by Vue.js SPA
    # Share route is now handled by Vue Router at /share/:token

    @app.route("/")
    def serve_vue_app_root():
        """Serve Vue.js SPA root - return index.html."""
        from flask import send_file

        dist_index = static_dir / "index.html"
        if dist_index.exists():
            return send_file(str(dist_index))

        # Frontend must be built - return error
        return (
            "<html><body><h1>Leyzen Vault</h1><p>Frontend not built. Run 'npm run build' in src/vault/static/</p></body></html>",
            404,
        )

    def _is_spa_route(path: str) -> bool:
        """Check if a path matches a valid Vue Router route pattern.

        Returns True if the path should be handled by Vue Router (SPA),
        False if it's a real 404 that should be handled by HAProxy.
        """
        import re

        # Exact routes in Vue Router
        exact_routes = {
            "/",
            "/setup",
            "/login",
            "/register",
            "/verify-email",
            "/accept-invitation",
            "/dashboard",
            "/trash",
            "/starred",
            "/recent",
            "/shared",
            "/account",
            "/admin",
        }

        if path in exact_routes:
            return True

        # Routes with dynamic parameters
        # /sso/callback/:providerId - matches /sso/callback/ followed by any non-slash chars
        if re.match(r"^/sso/callback/[^/]+", path):
            return True

        # /share/:token - matches /share/ followed by any non-slash chars
        if re.match(r"^/share/[^/]+", path):
            return True

        # /vaultspace/:id - matches /vaultspace/ followed by any non-slash chars
        if re.match(r"^/vaultspace/[^/]+", path):
            return True

        return False

    @app.errorhandler(404)
    def serve_vue_app_for_404(e):
        """Serve Vue.js SPA for 404 errors (Vue Router will handle client-side routing)."""
        from flask import request, send_file, jsonify, make_response, current_app

        # Import sys here (already imported at top level) - this import is redundant but kept for clarity
        import sys

        # Return JSON for API endpoints
        if request.path.startswith("/api/"):
            # Log 404 for API endpoints to help debug
            print(
                f"404 for API endpoint: {request.path} {request.method}",
                file=sys.stderr,
            )
            current_app.logger.error(
                f"404 for API endpoint: {request.path} {request.method}",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "full_url": request.url,
                    "headers": dict(request.headers),
                },
            )
            # Check if route exists in url_map
            matching_rules = [
                rule
                for rule in current_app.url_map.iter_rules()
                if rule.rule == request.path
                or request.path.startswith(
                    rule.rule.replace("<file_id>", "").replace("<link_token>", "")
                )
            ]
            if matching_rules:
                print(
                    f"Matching rules found: {[r.rule for r in matching_rules]}",
                    file=sys.stderr,
                )
            else:
                print(f"No matching rules found for {request.path}", file=sys.stderr)
            return jsonify({"error": "Not found", "path": request.path}), 404

        # Don't intercept static files
        if request.path.startswith("/static/"):
            return e

        # Check if this is a valid SPA route (should be handled by Vue Router)
        dist_index = static_dir / "index.html"
        if dist_index.exists():
            if _is_spa_route(request.path):
                # Valid SPA route - serve index.html with 200 so Vue Router can handle it
                return send_file(str(dist_index))
            else:
                # Invalid route - serve index.html with 404 so HAProxy can intercept
                # This allows HAProxy to intercept and serve its custom 404 page
                response = make_response(send_file(str(dist_index)))
                response.status_code = 404
                return response

        # Return original 404
        return e

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler - return JSON for API routes, HTML for others."""
        # Import traceback here to avoid importing at module level if not needed
        import traceback
        from flask import request, jsonify, current_app
        from werkzeug.exceptions import HTTPException

        # Handle Werkzeug HTTPException
        if isinstance(e, HTTPException):
            if request.path.startswith("/api/"):
                return jsonify({"error": e.description or str(e)}), e.code
            return e

        # Determine if we're in production mode
        is_production = current_app.config.get("IS_PRODUCTION", True)

        # Log the error with full details (always log details server-side)
        error_details = f"Unhandled exception: {e}\n{traceback.format_exc()}"
        current_app.logger.error(error_details)

        # If this is an API route, return JSON error
        if request.path.startswith("/api/"):
            # In production, return generic error message to avoid information disclosure
            # In development, return detailed error message for debugging
            if is_production:
                error_message = "An internal error occurred"
            else:
                error_message = str(e) if str(e) else "An internal error occurred"

            status_code = getattr(e, "code", 500)
            if not isinstance(status_code, int) or status_code < 400:
                status_code = 500
            return jsonify({"error": error_message}), status_code

        # For non-API routes, let Flask handle it (will show HTML error page)
        # But we still want to log it
        return e

    return app


# For Gunicorn
application = create_app()


__all__ = ["create_app", "application"]
