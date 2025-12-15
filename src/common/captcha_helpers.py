"""CAPTCHA helper functions for managing stores with application settings.

This module provides helper functions to work with CAPTCHA stores and CSRF stores
using application settings (VaultSettings or Settings). It centralizes the logic
for initializing stores and managing CAPTCHA nonces across different applications.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Callable

from flask import session

from common.captcha import (
    CaptchaStore,
    DatabaseCaptchaStore,
    LoginCSRFStore,
    build_captcha_image,
    generate_captcha_text,
)

from flask import current_app

if TYPE_CHECKING:
    from typing import Any

    from vault.config import VaultSettings
    from orchestrator.config import Settings


def get_captcha_store_for_app(
    settings: VaultSettings | Settings,
) -> CaptchaStore | DatabaseCaptchaStore:
    """Get or create a CAPTCHA store configured with application settings.

    Args:
        settings: Application settings (VaultSettings or Settings) with captcha_store_ttl attribute

    Returns:
        Configured CaptchaStore or DatabaseCaptchaStore instance
    """
    ttl = getattr(settings, "captcha_store_ttl", 300)
    # Use DatabaseCaptchaStore for multi-worker support
    # Try to use database store, fallback to in-memory if database is not available
    try:
        app = current_app._get_current_object()
        # Check if database is available by trying to import the model
        try:
            from vault.database.schema import CaptchaEntry

            # Database is available, use DatabaseCaptchaStore
            return DatabaseCaptchaStore(ttl, app=app)
        except (ImportError, RuntimeError):
            # Database not available (e.g., orchestrator without shared DB), use in-memory
            return CaptchaStore(ttl)
    except RuntimeError:
        # No application context, fallback to in-memory store
        return CaptchaStore(ttl)


def get_login_csrf_store_for_app(settings: VaultSettings | Settings) -> LoginCSRFStore:
    """Get or create a login CSRF store configured with application settings.

    Args:
        settings: Application settings (VaultSettings or Settings) with login_csrf_ttl attribute

    Returns:
        Configured LoginCSRFStore instance
    """
    ttl = getattr(settings, "login_csrf_ttl", 900)
    return LoginCSRFStore(ttl)


def refresh_captcha_with_store(
    store: CaptchaStore | DatabaseCaptchaStore,
    settings: VaultSettings | Settings,
    session_obj: dict[str, Any],
    *,
    on_svg_warning: Callable[[str], None] | None = None,
) -> str:
    """Generate a new CAPTCHA and store it with the given store.

    Args:
        store: CaptchaStore or DatabaseCaptchaStore instance to store the CAPTCHA
        settings: Application settings with captcha_length attribute
        session_obj: Flask session dictionary (used to get session_id)
        on_svg_warning: Optional callback to log SVG fallback warnings

    Returns:
        Generated nonce string
    """
    captcha_length = getattr(settings, "captcha_length", 6)
    text = generate_captcha_text(captcha_length)
    nonce = secrets.token_urlsafe(8)

    # Get or create session_id
    session_id = session_obj.get("_id")
    if not session_id:
        session_id = secrets.token_urlsafe(16)
        session_obj["_id"] = session_id

    # Store with session_id if using DatabaseCaptchaStore
    if isinstance(store, DatabaseCaptchaStore):
        store.store(nonce, text, session_id)
    else:
        store.store(nonce, text)

    return nonce


def get_captcha_nonce_with_store(
    store: CaptchaStore | DatabaseCaptchaStore,
    session_obj: dict[str, Any],
    settings: VaultSettings | Settings,
    *,
    on_svg_warning: Callable[[str], None] | None = None,
) -> str:
    """Get existing CAPTCHA nonce from store or create a new one.

    Args:
        store: CaptchaStore or DatabaseCaptchaStore instance to store/retrieve the CAPTCHA
        session_obj: Flask session dictionary (used to get session_id)
        settings: Application settings with captcha_length attribute
        on_svg_warning: Optional callback to log SVG fallback warnings

    Returns:
        CAPTCHA nonce string
    """
    return refresh_captcha_with_store(
        store, settings, session_obj, on_svg_warning=on_svg_warning
    )


def build_captcha_image_with_settings(
    text: str,
    settings: VaultSettings | Settings,
    *,
    on_svg_warning: Callable[[str], None] | None = None,
) -> tuple[bytes, str]:
    """Build a CAPTCHA image using settings for configuration.

    Args:
        text: CAPTCHA text to render
        settings: Application settings with captcha_length attribute
        on_svg_warning: Optional callback to log SVG fallback warnings

    Returns:
        Tuple of (image_bytes, mime_type)
    """
    captcha_length = getattr(settings, "captcha_length", 6)
    return build_captcha_image(text, captcha_length, on_svg_warning=on_svg_warning)


__all__ = [
    "get_captcha_store_for_app",
    "get_login_csrf_store_for_app",
    "refresh_captcha_with_store",
    "get_captcha_nonce_with_store",
    "build_captcha_image_with_settings",
]
