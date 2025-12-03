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
    LoginCSRFStore,
    build_captcha_image,
    generate_captcha_text,
)

if TYPE_CHECKING:
    from typing import Any

    from vault.config import VaultSettings
    from orchestrator.config import Settings


def get_captcha_store_for_app(settings: VaultSettings | Settings) -> CaptchaStore:
    """Get or create a CAPTCHA store configured with application settings.

    Args:
        settings: Application settings (VaultSettings or Settings) with captcha_store_ttl attribute

    Returns:
        Configured CaptchaStore instance
    """
    ttl = getattr(settings, "captcha_store_ttl", 300)
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
    store: CaptchaStore,
    settings: VaultSettings | Settings,
    session_obj: dict[str, Any],
    *,
    on_svg_warning: Callable[[str], None] | None = None,
) -> str:
    """Generate a new CAPTCHA and store it with the given store.

    Args:
        store: CaptchaStore instance to store the CAPTCHA
        settings: Application settings with captcha_length attribute
        session_obj: Flask session dictionary (kept for compatibility, not used)
        on_svg_warning: Optional callback to log SVG fallback warnings

    Returns:
        Generated nonce string
    """
    captcha_length = getattr(settings, "captcha_length", 6)
    text = generate_captcha_text(captcha_length)
    nonce = secrets.token_urlsafe(8)
    store.store(nonce, text)
    return nonce


def get_captcha_nonce_with_store(
    store: CaptchaStore,
    session_obj: dict[str, Any],
    settings: VaultSettings | Settings,
    *,
    on_svg_warning: Callable[[str], None] | None = None,
) -> str:
    """Get existing CAPTCHA nonce from store or create a new one.

    Args:
        store: CaptchaStore instance to store/retrieve the CAPTCHA
        session_obj: Flask session dictionary (kept for compatibility, not used)
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
