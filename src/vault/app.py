"""Flask application for Leyzen Vault backend."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, render_template

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

bootstrap_entry_point()

from .blueprints.auth import auth_bp  # noqa: E402
from .blueprints.files import files_bp  # noqa: E402
from .blueprints.security import security_bp  # noqa: E402
from .config import VaultSettings, load_settings  # noqa: E402
from .extensions import csrf  # noqa: E402
from .models import FileDatabase  # noqa: E402
from .services.audit import AuditService  # noqa: E402
from .services.logging import FileLogger  # noqa: E402
from .services.rate_limiter import RateLimiter  # noqa: E402
from .services.share_service import ShareService  # noqa: E402
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

    # Require environment variables - no hardcoded secrets
    username = os.environ.get("VAULT_USER", "").strip()
    if not username:
        raise ConfigurationError(
            "VAULT_USER is required. Fallback mode requires environment variables to be set. "
            "This function should NOT be used in production."
        )

    password = os.environ.get("VAULT_PASS", "").strip()
    if not password:
        raise ConfigurationError(
            "VAULT_PASS is required. Fallback mode requires environment variables to be set. "
            "This function should NOT be used in production."
        )

    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError(
            "SECRET_KEY is required (minimum 12 characters). Fallback mode requires environment variables to be set. "
            "This function should NOT be used in production."
        )

    if len(secret_key) < 12:
        raise ConfigurationError(
            "SECRET_KEY must be at least 12 characters long. "
            "Fallback mode requires environment variables to be set."
        )

    from werkzeug.security import generate_password_hash

    return VaultSettings(
        username=username,
        password_hash=generate_password_hash(password),
        secret_key=secret_key,
        timezone=fallback_timezone,
        proxy_trust_count=1,
        captcha_length=6,
        captcha_store_ttl=300,
        login_csrf_ttl=900,
        log_file=Path("/tmp/vault.log"),
        session_cookie_secure=False,
        max_file_size_mb=100,
        max_uploads_per_hour=50,
        audit_retention_days=90,
    )


def create_app(
    storage_dir: Path | None = None,
    database_path: Path | None = None,
    *args: object,
    **kwargs: object,
) -> Flask:
    """Create and configure the Flask application."""
    # Get the directory containing this file
    vault_dir = Path(__file__).parent

    app = Flask(
        __name__,
        template_folder=str(vault_dir / "templates"),
        static_folder=str(vault_dir / "static"),
        static_url_path="/static",
    )

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
    except Exception as exc:
        # Fallback for development/testing
        # Note: This fallback now requires environment variables to be set
        # Hardcoded secrets have been removed for security
        fallback_settings = _create_fallback_settings()
        app.config["SECRET_KEY"] = fallback_settings.secret_key
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=False,
        )
        app.config["VAULT_SETTINGS"] = fallback_settings
        app.config["LOGGER"] = FileLogger(fallback_settings)

    # Initialize CSRF protection
    csrf.init_app(app)

    # Configure CSRF to accept tokens in FormData for multipart/form-data requests
    # Flask-WTF automatically checks request.form for CSRF tokens in POST requests
    # No additional configuration needed for FormData uploads

    # Default paths - ensure they are Path objects
    if storage_dir is None:
        storage_dir = Path("/data/files")
    elif not isinstance(storage_dir, Path):
        # Convert to Path if it's not already a Path object
        storage_dir = Path(str(storage_dir))

    # Database paths - check environment variables first
    env_values = {}
    try:
        from common.env import load_env_with_override
        import os

        env_values = load_env_with_override()
        env_values.update(os.environ)
    except Exception:
        pass

    if database_path is None:
        # Check for VAULT_DB_PATH environment variable
        db_path_env = env_values.get("VAULT_DB_PATH", "/data/vault.db")
        database_path = Path(db_path_env)
    elif not isinstance(database_path, Path):
        # Convert to Path if it's not already a Path object
        database_path = Path(str(database_path))

    # Initialize storage and database
    storage = FileStorage(storage_dir)
    database = FileDatabase(database_path)

    # Initialize audit service
    audit_db_path_env = env_values.get("VAULT_AUDIT_DB_PATH")
    if audit_db_path_env:
        audit_db_path = Path(audit_db_path_env)
    else:
        audit_db_path = database_path.parent / "audit.db"
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            audit_service = AuditService(
                audit_db_path,
                timezone=settings.timezone,
                retention_days=settings.audit_retention_days,
            )
        else:
            # Fallback: use UTC and default retention
            from zoneinfo import ZoneInfo

            audit_service = AuditService(
                audit_db_path, timezone=ZoneInfo("UTC"), retention_days=90
            )
    except Exception:
        # Fallback: use UTC and default retention
        from zoneinfo import ZoneInfo

        audit_service = AuditService(
            audit_db_path, timezone=ZoneInfo("UTC"), retention_days=90
        )

    # Initialize share service
    share_db_path_env = env_values.get("VAULT_SHARES_DB_PATH")
    if share_db_path_env:
        share_db_path = Path(share_db_path_env)
    else:
        share_db_path = database_path.parent / "shares.db"
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            share_service = ShareService(share_db_path, timezone=settings.timezone)
        else:
            # Fallback: use UTC
            from zoneinfo import ZoneInfo

            share_service = ShareService(share_db_path, timezone=ZoneInfo("UTC"))
    except Exception:
        # Fallback: use UTC
        from zoneinfo import ZoneInfo

        share_service = ShareService(share_db_path, timezone=ZoneInfo("UTC"))

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

    app.config["VAULT_STORAGE"] = storage
    app.config["VAULT_DATABASE"] = database
    app.config["VAULT_AUDIT"] = audit_service
    app.config["VAULT_SHARE"] = share_service
    app.config["VAULT_RATE_LIMITER"] = rate_limiter

    # Start background thread for automatic audit log cleanup
    def _audit_cleanup_worker() -> None:
        """Background worker to periodically clean up old audit logs."""
        import time
        import logging

        logger = logging.getLogger(__name__)
        while True:
            try:
                time.sleep(3600)  # Run every hour
                deleted_count = audit_service.cleanup_old_logs()
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old audit log entries")
            except Exception as e:
                logger.error(f"Error during audit log cleanup: {e}", exc_info=True)

    import threading

    cleanup_thread = threading.Thread(target=_audit_cleanup_worker, daemon=True)
    cleanup_thread.start()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(security_bp)

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

    @app.after_request
    def add_security_headers(response):
        """Add strict security headers including CSP."""
        import json
        from flask import request
        from common.constants import SESSION_MAX_AGE_SECONDS

        # Content Security Policy - enhanced with trusted types and reporting
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data: blob:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests",
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
        try:
            from flask import request

            orchestrator_url = f"{request.scheme}://{request.host}/orchestrator/csp-violation-report-endpoint"
        except Exception:
            # Fallback: use relative URL if request context unavailable
            orchestrator_url = "/orchestrator/csp-violation-report-endpoint"

        report_to = {
            "group": "vault-csp",
            "max_age": SESSION_MAX_AGE_SECONDS,
            "endpoints": [{"url": orchestrator_url}],
        }

        response.headers["Report-To"] = json.dumps(report_to)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
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
        """Health check endpoint."""
        return {"status": "ok"}, 200

    @app.route("/share/<link_token>")
    def share_with_token(link_token: str):
        """Serve the share page for downloading files via share token."""
        share_service = app.config["VAULT_SHARE"]
        is_valid, error_msg = share_service.validate_share_link(link_token)

        if not is_valid:
            return (
                render_template("share.html", error=error_msg or "Invalid share link"),
                404,
            )

        share_link = share_service.get_share_link(link_token)
        if not share_link:
            return render_template("share.html", error="Share link not found"), 404

        return render_template(
            "share.html", link_token=link_token, file_id=share_link.file_id
        )

    @app.route("/share")
    def share():
        """Serve the share page for downloading files (no auth required)."""
        return render_template("share.html")

    return app


# For Gunicorn
application = create_app()


__all__ = ["create_app", "application"]
