"""Configuration API routes for exposing vault settings to frontend."""

from __future__ import annotations

import os
from flask import Blueprint, current_app, jsonify
from vault.config import is_setup_complete
from vault.extensions import csrf

config_api_bp = Blueprint("config_api", __name__, url_prefix="/api/v2")


@config_api_bp.route("/config", methods=["GET"])
@csrf.exempt  # Public endpoint
def get_config():
    """Get configuration values for the frontend.

    Returns:
        JSON with vault_url (public), timezone, is_production (public),
        is_setup_complete (public), allow_signup (public),
        password_authentication_enabled (public), and orchestrator_enabled (admin only)
    """
    try:
        from vault.database.schema import SystemSettings, db

        # Get setup status
        setup_complete = is_setup_complete(current_app)
        current_app.logger.info(f"Setup check: {setup_complete}")

        # Get all auth-related settings
        settings_query = (
            db.session.query(SystemSettings)
            .filter(
                SystemSettings.key.in_(
                    ["allow_signup", "password_authentication_enabled"]
                )
            )
            .all()
        )
        settings_dict = {s.key: s.value for s in settings_query}

        # Get allow_signup (default: True)
        allow_signup = True
        if "allow_signup" in settings_dict:
            allow_signup = settings_dict["allow_signup"].lower() == "true"

        # Get password_authentication_enabled (default: True)
        password_auth_enabled = True
        if "password_authentication_enabled" in settings_dict:
            password_auth_enabled = (
                settings_dict["password_authentication_enabled"].lower() == "true"
            )

        # Get timezone directly from os.environ (Docker container env vars)
        timezone_env = os.environ.get("TIMEZONE")
        timezone = str(timezone_env).strip() if timezone_env else "UTC"
        if not timezone:
            timezone = "UTC"

        settings = current_app.config.get("VAULT_SETTINGS")
        vault_url = None
        if settings and hasattr(settings, "vault_url") and settings.vault_url:
            vault_url = settings.vault_url.rstrip("/")
        else:
            # Fallback to environment variable if not in settings
            vault_url_env = os.environ.get("VAULT_URL")
            if vault_url_env:
                vault_url = str(vault_url_env).strip().rstrip("/")
                if not vault_url:
                    vault_url = None

        # Get IS_PRODUCTION from app config (set during app initialization)
        is_production = current_app.config.get("IS_PRODUCTION", True)

        # Get orchestrator_enabled from env var (default: False)
        # This is the ONLY source of truth for this feature flag
        orchestrator_enabled = (
            os.environ.get("ORCHESTRATOR_ENABLED", "false").lower() == "true"
        )

        # Build the response object carefully to avoid any serialization issues
        # Use simple types for all fields
        result = {
            "vault_url": str(vault_url) if vault_url else None,
            "timezone": str(timezone) if timezone else "UTC",
            "is_production": bool(is_production),
            "is_setup_complete": bool(setup_complete),
            "allow_signup": bool(allow_signup),
            "password_authentication_enabled": bool(password_auth_enabled),
            "orchestrator_enabled": bool(orchestrator_enabled),
        }

        return jsonify(result)
    except Exception as e:
        # If there's an error, return basic config and default to production
        current_app.logger.warning(f"Error getting config: {e}")
        return jsonify(
            {
                "vault_url": None,
                "timezone": "UTC",
                "is_production": True,
                "is_setup_complete": True,
                "allow_signup": False,
                "password_authentication_enabled": True,
            }
        )
