"""Configuration API routes for exposing vault settings to frontend."""

from __future__ import annotations

import os
from flask import Blueprint, current_app, jsonify

config_api_bp = Blueprint("config_api", __name__, url_prefix="/api/v2")


@config_api_bp.route("/config", methods=["GET"])
def get_config():
    """Get configuration values for the frontend.

    Returns:
        JSON with vault_url (public), timezone, is_production (public), and orchestrator_enabled (admin only)
        - vault_url: Always included (public, for share links)
        - timezone: Always included (public)
        - is_production: Always included (public, indicates backend production mode)
        - orchestrator_enabled: Only included if user is authenticated and admin/superadmin
    """
    try:
        # Get timezone directly from os.environ (Docker container env vars)
        timezone_env = os.environ.get("TIMEZONE")
        if timezone_env:
            timezone = str(timezone_env).strip()
            if not timezone:
                timezone = "UTC"
        else:
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
            else:
                vault_url = None

        # Get IS_PRODUCTION from app config (set during app initialization)
        is_production = current_app.config.get("IS_PRODUCTION", True)

        result = {
            "vault_url": vault_url,
            "timezone": timezone,
            "is_production": is_production,
        }

        # Check if user is authenticated and admin to expose orchestrator_enabled
        # This information should only be visible to admins for security reasons
        # We manually verify JWT token here (without @jwt_required) to keep vault_url public
        orchestrator_enabled = None
        try:
            from flask import request
            from vault.database.schema import GlobalRole
            from vault.services.auth_service import AuthService
            from vault.services.api_key_service import ApiKeyService

            # Try to get JWT token from Authorization header
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix

                # Verify token using AuthService
                secret_key = current_app.config.get("SECRET_KEY")
                if secret_key:
                    settings = current_app.config.get("VAULT_SETTINGS")
                    jwt_expiration_hours = (
                        settings.jwt_expiration_hours if settings else 120
                    )
                    auth_service = AuthService(
                        secret_key, jwt_expiration_hours=jwt_expiration_hours
                    )
                    current_user = auth_service.verify_token(token)

                    # If JWT authentication failed, try API key authentication
                    if not current_user:
                        api_key_service = ApiKeyService(secret_key=secret_key)
                        current_user = api_key_service.verify_api_key(token)

                    # Check if user is admin/superadmin
                    if current_user and current_user.global_role in (
                        GlobalRole.ADMIN,
                        GlobalRole.SUPERADMIN,
                    ):
                        # Read ORCHESTRATOR_ENABLED from environment
                        # Use proper priority: .env file overrides os.environ
                        from common.env import load_env_with_priority

                        env_values = load_env_with_priority()
                        orchestrator_enabled_raw = (
                            env_values.get("ORCHESTRATOR_ENABLED", "true")
                            .strip()
                            .lower()
                        )
                        orchestrator_enabled = orchestrator_enabled_raw in (
                            "true",
                            "1",
                            "yes",
                            "on",
                        )
                        result["orchestrator_enabled"] = orchestrator_enabled
        except Exception:
            # If check fails (user not authenticated, not admin, or error),
            # orchestrator_enabled is not exposed (remains None)
            pass

        return jsonify(result)
    except Exception as e:
        # If there's an error, return null for vault_url, default timezone, and default to production
        current_app.logger.warning(f"Error getting vault_url from config: {e}")
        return jsonify({"vault_url": None, "timezone": "UTC", "is_production": True})
