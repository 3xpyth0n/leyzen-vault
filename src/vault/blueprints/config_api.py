"""Configuration API routes for exposing vault settings to frontend."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

config_api_bp = Blueprint("config_api", __name__, url_prefix="/api/v2")


@config_api_bp.route("/config", methods=["GET"])
def get_config():
    """Get public configuration values for the frontend.

    Returns:
        JSON with vault_url (or null if not configured)
    """
    try:
        settings = current_app.config.get("VAULT_SETTINGS")
        vault_url = None
        if settings and hasattr(settings, "vault_url") and settings.vault_url:
            vault_url = settings.vault_url.rstrip("/")

        return jsonify({"vault_url": vault_url})
    except Exception as e:
        # If there's an error, return null for vault_url
        current_app.logger.warning(f"Error getting vault_url from config: {e}")
        return jsonify({"vault_url": None})
