"""Vault orchestrator application factory."""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from flask import Flask, jsonify, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from common.constants import SESSION_MAX_AGE_SECONDS
from .blueprints.auth import auth_bp
from .blueprints.dashboard import dashboard_bp
from .config import Settings, load_settings
from .extensions import csrf
from .services.docker_proxy import DockerProxyService
from common.services.logging import FileLogger
from .services.rotation import RotationService
from .services.storage_cleanup import StorageCleanupService


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()

    app = Flask(
        __name__,
        template_folder=str(settings.html_dir / "templates"),
        static_folder=str(settings.html_dir / "static"),
        static_url_path="/orchestrator/static",
    )
    app.wsgi_app = ProxyFix(  # type: ignore[assignment]
        app.wsgi_app,
        x_for=settings.proxy_trust_count,
        x_proto=settings.proxy_trust_count,
        x_host=settings.proxy_trust_count,
        x_port=settings.proxy_trust_count,
    )
    app.secret_key = settings.secret_key
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    )

    from common.env import load_env_with_priority

    env_values = load_env_with_priority()
    leyzen_env = env_values.get("LEYZEN_ENVIRONMENT", "").strip().lower()
    is_production = leyzen_env not in ("dev", "development")

    # Configure root logger level
    import logging as log_module

    root_logger = log_module.getLogger()
    if not is_production:
        root_logger.setLevel(log_module.DEBUG)
    else:
        root_logger.setLevel(log_module.WARNING)

    logger = FileLogger(settings, is_production=is_production)
    docker_service = DockerProxyService(settings, logger)
    rotation_service = RotationService(settings, docker_service, logger)
    storage_cleanup_service = StorageCleanupService(settings, logger)

    app.config["SETTINGS"] = settings
    app.config["LOGGER"] = logger
    app.config["ROTATION_SERVICE"] = rotation_service
    app.config["STORAGE_CLEANUP_SERVICE"] = storage_cleanup_service

    # Initialize database if VAULT_DB_URI is available
    db_uri = env_values.get("VAULT_DB_URI")
    if db_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        try:
            from vault.database.schema import db

            db.init_app(app)
        except ImportError:
            # Fallback if vault schema is not available
            pass

    csrf.init_app(app)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/healthz")
    def healthz():
        """Health check endpoint that doesn't require authentication or trigger before_request hooks."""
        return jsonify({"status": "ok"}), 200

    @app.after_request
    def add_csp_headers(response):
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' https://static.cloudflareinsights.com",
            "style-src 'self' https://fonts.googleapis.com",
            "img-src 'self' data: blob:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests",
            "report-uri /orchestrator/csp-violation-report-endpoint",
            "report-to orchestrator-csp",
        ]
        new_csp_policy = "; ".join(csp_directives)
        if existing_csp := response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = (
                f"{existing_csp}; {new_csp_policy}"
            )
        else:
            response.headers["Content-Security-Policy"] = new_csp_policy

        report_to = {
            "group": "orchestrator-csp",
            "max_age": SESSION_MAX_AGE_SECONDS,
            "endpoints": [
                {"url": url_for("dashboard.csp_violation_report", _external=True)}
            ],
        }
        response.headers["Report-To"] = json.dumps(report_to)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    return app


__all__ = ["create_app"]
