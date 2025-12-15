"""CAPTCHA generation utilities shared across Leyzen Vault components."""

from __future__ import annotations

import html
import random
import secrets
import string
import time
from datetime import datetime, timezone
from io import BytesIO
from threading import Lock
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

from common.constants import (
    CAPTCHA_DISTRACTION_LINES,
    CAPTCHA_FONT_SIZE,
    CAPTCHA_LENGTH_DEFAULT,
    CAPTCHA_NOISE_PIXELS,
    CAPTCHA_SVG_FONT_SIZE,
)

# Try to import PIL (optional dependency)
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont  # type: ignore[import-not-found]
except ModuleNotFoundError as exc:
    Image = ImageDraw = ImageFilter = ImageFont = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    _PIL_IMPORT_ERROR = None

# Global state for SVG warning (shared across instances)
_svg_warning_emitted = False


def generate_captcha_text(length: int) -> str:
    """Generate a random CAPTCHA text string.

    Args:
        length: Length of the CAPTCHA text

    Returns:
        Random string of uppercase letters and digits
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def random_color(min_value: int = 0, max_value: int = 255) -> tuple[int, int, int]:
    """Generate a random RGB color tuple.

    Args:
        min_value: Minimum RGB value (0-255)
        max_value: Maximum RGB value (0-255)

    Returns:
        Tuple of (R, G, B) values
    """
    r = random.randint(min_value, max_value)
    g = random.randint(min_value, max_value)
    b = random.randint(min_value, max_value)
    return (r, g, b)


def load_captcha_font(size: int = CAPTCHA_FONT_SIZE) -> ImageFont.ImageFont | None:
    """Load a PIL ImageFont with the specified size.

    Falls back to default font if font_variant is not available.

    Args:
        size: Font size

    Returns:
        PIL ImageFont object or None if PIL is not available
    """
    if ImageFont is None:
        return None

    base_font = ImageFont.load_default()
    try:
        return base_font.font_variant(size=size)  # type: ignore[attr-defined]
    except AttributeError:
        return base_font


def build_captcha_image(
    text: str,
    captcha_length: int = CAPTCHA_LENGTH_DEFAULT,
    on_svg_warning: Callable[[str], None] | None = None,
) -> tuple[bytes, str]:
    """Build a CAPTCHA image (PNG or SVG fallback).

    Args:
        text: CAPTCHA text to render
        captcha_length: Length of CAPTCHA (used for dimensions)
        on_svg_warning: Optional callback to log SVG fallback warning

    Returns:
        Tuple of (image_bytes, mime_type)
    """
    # Calculate dimensions based on CAPTCHA length
    # Width: ~35px per character + padding
    width = captcha_length * 35 + 20
    # Height: fixed at 70px
    height = 70

    if (
        Image is not None
        and ImageDraw is not None
        and ImageFilter is not None
        and ImageFont is not None
    ):
        image = Image.new("RGB", (width, height), random_color(200, 255))
        draw = ImageDraw.Draw(image)

        for _ in range(CAPTCHA_DISTRACTION_LINES):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=random_color(80, 200), width=2)

        font = load_captcha_font()
        if font is None:
            # Fallback to SVG if font loading fails
            return build_svg_captcha(text, width, height, on_svg_warning)

        char_spacing = width // (len(text) + 1)
        for index, character in enumerate(text):
            position = (
                15 + index * char_spacing + random.randint(-5, 5),
                random.randint(5, height - 45),
            )
            draw.text(
                position,
                character,
                font=font,
                fill=random_color(10, 70),
                stroke_width=2,
                stroke_fill=(0, 0, 0),
            )

        for _ in range(CAPTCHA_NOISE_PIXELS):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            image.putpixel((x, y), random_color(0, 255))

        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read(), "image/png"

    return build_svg_captcha(text, width, height, on_svg_warning)


def build_svg_captcha(
    text: str,
    width: int,
    height: int,
    on_svg_warning: Callable[[str], None] | None = None,
) -> tuple[bytes, str]:
    """Build a CAPTCHA SVG image (fallback when PIL is not available).

    Args:
        text: CAPTCHA text to render
        width: Image width
        height: Image height
        on_svg_warning: Optional callback to log SVG fallback warning

    Returns:
        Tuple of (svg_bytes, "image/svg+xml")
    """
    global _svg_warning_emitted

    # The SVG fallback intentionally mirrors the noise pattern of the Pillow
    # version to remain resistant to trivial OCR when Pillow is unavailable.
    background = random_color(220, 255)
    svg_lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        f"<rect width='100%' height='100%' fill='rgb{background}' />",
    ]

    for _ in range(CAPTCHA_DISTRACTION_LINES):
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        end_x = random.randint(0, width)
        end_y = random.randint(0, height)
        color = random_color(80, 200)
        svg_lines.append(
            f"<line x1='{start_x}' y1='{start_y}' x2='{end_x}' y2='{end_y}' stroke='rgb{color}' stroke-width='2' />"
        )

    char_spacing = width // (len(text) + 1)
    for index, character in enumerate(text):
        x = 15 + index * char_spacing + random.randint(-5, 5)
        y = random.randint(height // 2, height - 10)
        fill_color = random_color(10, 70)
        svg_lines.append(
            "<text "
            "font-family='monospace' "
            f"font-size='{CAPTCHA_SVG_FONT_SIZE}' "
            "stroke='black' stroke-width='1' "
            f"fill='rgb{fill_color}' x='{x}' y='{y}'>"
            f"{html.escape(character)}</text>"
        )

    for _ in range(CAPTCHA_NOISE_PIXELS):
        x = random.randint(0, width)
        y = random.randint(0, height)
        color = random_color(0, 255)
        svg_lines.append(f"<circle cx='{x}' cy='{y}' r='1' fill='rgb{color}' />")

    svg_lines.append("</svg>")
    svg_content = "".join(svg_lines).encode("utf-8")

    # Log warning once if PIL is not available
    if _PIL_IMPORT_ERROR is not None and not _svg_warning_emitted and on_svg_warning:
        on_svg_warning(
            f"Pillow not available, serving SVG captcha fallback. Install Pillow to restore PNG captcha rendering: {_PIL_IMPORT_ERROR}"
        )
        _svg_warning_emitted = True

    return svg_content, "image/svg+xml"


class CaptchaStore:
    """Thread-safe CAPTCHA store for managing CAPTCHA nonces and text."""

    def __init__(self, ttl_seconds: int) -> None:
        """Initialize CAPTCHA store.

        Args:
            ttl_seconds: Time-to-live for CAPTCHA entries in seconds
        """
        self._store: dict[str, tuple[str, float, int]] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._last_prune_time: float = 0.0
        self._prune_interval: float = 60.0  # Prune at most once per minute

    def store(self, nonce: str, text: str) -> None:
        """Store a CAPTCHA entry.

        Args:
            nonce: Nonce identifier
            text: CAPTCHA text
        """
        if not nonce:
            return
        now = time.time()
        with self._lock:
            self._store[nonce] = (text, now, 0)
        # Only prune if enough time has passed since last prune
        # This reduces race conditions and improves performance
        if now - self._last_prune_time >= self._prune_interval:
            self.prune(now)
            self._last_prune_time = now

    def get(self, nonce: str | None) -> str | None:
        """Get CAPTCHA text by nonce.

        Args:
            nonce: Nonce identifier

        Returns:
            CAPTCHA text or None if not found or expired
        """
        if not nonce:
            return None
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._lock:
            entry = self._store.get(nonce)
            if not entry:
                return None
            text, timestamp, attempts = entry
            # Add a small grace period (5 seconds) to handle timing issues
            # This prevents premature expiration due to clock skew or timing variations
            grace_period = 5.0
            if timestamp < (cutoff - grace_period):
                return None
            return text

    def get_attempts(self, nonce: str | None) -> int:
        """Get the number of failed attempts for a CAPTCHA.

        Args:
            nonce: Nonce identifier

        Returns:
            Number of failed attempts, or 0 if not found or expired
        """
        if not nonce:
            return 0
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._lock:
            entry = self._store.get(nonce)
            if not entry:
                return 0
            text, timestamp, attempts = entry
            # Check expiration but don't delete here - let prune handle cleanup
            if timestamp < cutoff:
                return 0
            return attempts

    def increment_attempts(self, nonce: str | None) -> int:
        """Increment failed validation attempts for a CAPTCHA.

        Args:
            nonce: Nonce identifier

        Returns:
            New attempt count, or 0 if not found or expired
        """
        if not nonce:
            return 0
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._lock:
            entry = self._store.get(nonce)
            if not entry:
                return 0
            text, timestamp, attempts = entry
            # Check expiration but don't delete here - let prune handle cleanup
            if timestamp < cutoff:
                return 0
            new_attempts = attempts + 1
            self._store[nonce] = (text, timestamp, new_attempts)
            return new_attempts

    def drop(self, nonce: str | None) -> None:
        """Drop a CAPTCHA entry.

        Args:
            nonce: Nonce identifier
        """
        if not nonce:
            return
        with self._lock:
            self._store.pop(nonce, None)

    def prune(self, now: float | None = None) -> None:
        """Prune expired CAPTCHA entries.

        Args:
            now: Current time (defaults to time.time())
        """
        cutoff = (now or time.time()) - self._ttl_seconds
        with self._lock:
            expired = [key for key, (_, ts, _) in self._store.items() if ts < cutoff]
            for key in expired:
                self._store.pop(key, None)


class DatabaseCaptchaStore:
    """Database-backed CAPTCHA store for multi-worker synchronization."""

    def __init__(self, ttl_seconds: int, app: Flask | None = None) -> None:
        """Initialize database CAPTCHA store.

        Args:
            ttl_seconds: Time-to-live for CAPTCHA entries in seconds
            app: Flask application instance (defaults to current_app)
        """
        from flask import current_app

        self._app = app or current_app
        self._ttl_seconds = ttl_seconds
        self._last_prune_time: float = 0.0
        self._prune_interval: float = 60.0  # Prune at most once per minute
        self._lock = Lock()

    def _get_db(self):
        """Get database instance from Flask app."""
        try:
            from vault.database.schema import db

            return db
        except ImportError:
            # Orchestrator context - try to import from app context
            # The database should be available through the app
            from flask import current_app

            if (
                hasattr(current_app, "extensions")
                and "sqlalchemy" in current_app.extensions
            ):
                return current_app.extensions["sqlalchemy"].db
            raise RuntimeError("Database not available in current application context")

    def _get_model(self):
        """Get CaptchaEntry model."""
        try:
            from vault.database.schema import CaptchaEntry

            return CaptchaEntry
        except ImportError:
            # Try to get from app context if available
            from flask import current_app

            if (
                hasattr(current_app, "extensions")
                and "sqlalchemy" in current_app.extensions
            ):
                # Try to get model from app registry
                from sqlalchemy import inspect

                db = self._get_db()
                # Get model from metadata
                for table_name, table in db.metadata.tables.items():
                    if table_name == "captcha_entries":
                        # Return the model class if we can find it
                        for mapper in db.Model.registry.mappers:
                            if mapper.class_.__tablename__ == "captcha_entries":
                                return mapper.class_
            raise RuntimeError(
                "CaptchaEntry model not available in current application context"
            )

    def store(self, nonce: str, text: str, session_id: str) -> None:
        """Store a CAPTCHA entry.

        Args:
            nonce: Nonce identifier
            text: CAPTCHA text
            session_id: Session identifier for user isolation
        """
        if not nonce or not session_id:
            return

        db = self._get_db()
        CaptchaEntry = self._get_model()
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(
            time.time() + self._ttl_seconds, tz=timezone.utc
        )

        with self._app.app_context():
            # Delete any existing entry with same nonce (shouldn't happen but be safe)
            db.session.query(CaptchaEntry).filter_by(nonce=nonce).delete()

            entry = CaptchaEntry(
                nonce=nonce,
                session_id=session_id,
                text=text,
                attempts=0,
                created_at=now,
                expires_at=expires_at,
            )
            db.session.add(entry)
            db.session.commit()

        # Only prune if enough time has passed since last prune
        now_ts = time.time()
        if now_ts - self._last_prune_time >= self._prune_interval:
            self.prune(now_ts)
            self._last_prune_time = now_ts

    def get(self, nonce: str | None, session_id: str | None) -> str | None:
        """Get CAPTCHA text by nonce and session_id.

        Args:
            nonce: Nonce identifier
            session_id: Session identifier (must match)

        Returns:
            CAPTCHA text or None if not found, expired, or session mismatch
        """
        if not nonce or not session_id:
            return None

        db = self._get_db()
        CaptchaEntry = self._get_model()
        now = datetime.now(timezone.utc)

        with self._app.app_context():
            entry = (
                db.session.query(CaptchaEntry)
                .filter_by(nonce=nonce, session_id=session_id)
                .first()
            )

            if not entry:
                return None

            # Check expiration with grace period (5 seconds)
            grace_period = 5.0
            cutoff = datetime.fromtimestamp(
                time.time() - self._ttl_seconds - grace_period, tz=timezone.utc
            )

            if entry.created_at < cutoff:
                return None

            return entry.text

    def get_attempts(self, nonce: str | None, session_id: str | None) -> int:
        """Get the number of failed attempts for a CAPTCHA.

        Args:
            nonce: Nonce identifier
            session_id: Session identifier (must match)

        Returns:
            Number of failed attempts, or 0 if not found or expired
        """
        if not nonce or not session_id:
            return 0

        db = self._get_db()
        CaptchaEntry = self._get_model()
        now = datetime.now(timezone.utc)

        with self._app.app_context():
            entry = (
                db.session.query(CaptchaEntry)
                .filter_by(nonce=nonce, session_id=session_id)
                .first()
            )

            if not entry:
                return 0

            # Check expiration but don't delete here - let prune handle cleanup
            cutoff = datetime.fromtimestamp(
                time.time() - self._ttl_seconds, tz=timezone.utc
            )

            if entry.created_at < cutoff:
                return 0

            return entry.attempts

    def increment_attempts(self, nonce: str | None, session_id: str | None) -> int:
        """Increment failed validation attempts for a CAPTCHA.

        Args:
            nonce: Nonce identifier
            session_id: Session identifier (must match)

        Returns:
            New attempt count, or 0 if not found or expired
        """
        if not nonce or not session_id:
            return 0

        db = self._get_db()
        CaptchaEntry = self._get_model()
        now = datetime.now(timezone.utc)

        with self._app.app_context():
            entry = (
                db.session.query(CaptchaEntry)
                .filter_by(nonce=nonce, session_id=session_id)
                .first()
            )

            if not entry:
                return 0

            # Check expiration but don't delete here - let prune handle cleanup
            cutoff = datetime.fromtimestamp(
                time.time() - self._ttl_seconds, tz=timezone.utc
            )

            if entry.created_at < cutoff:
                return 0

            entry.attempts += 1
            db.session.commit()
            return entry.attempts

    def drop(self, nonce: str | None, session_id: str | None) -> None:
        """Drop a CAPTCHA entry.

        Args:
            nonce: Nonce identifier
            session_id: Session identifier (must match for security)
        """
        if not nonce or not session_id:
            return

        db = self._get_db()
        CaptchaEntry = self._get_model()

        with self._app.app_context():
            db.session.query(CaptchaEntry).filter_by(
                nonce=nonce, session_id=session_id
            ).delete()
            db.session.commit()

    def prune(self, now: float | None = None) -> None:
        """Prune expired CAPTCHA entries.

        Args:
            now: Current time (defaults to time.time())
        """
        db = self._get_db()
        CaptchaEntry = self._get_model()
        cutoff = datetime.fromtimestamp(
            (now or time.time()) - self._ttl_seconds, tz=timezone.utc
        )

        with self._app.app_context():
            db.session.query(CaptchaEntry).filter(
                CaptchaEntry.expires_at < cutoff
            ).delete()
            db.session.commit()


class LoginCSRFStore:
    """Thread-safe login CSRF token store."""

    def __init__(self, ttl_seconds: int) -> None:
        """Initialize login CSRF store.

        Args:
            ttl_seconds: Time-to-live for CSRF tokens in seconds
        """
        self._store: dict[str, float] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

    def issue(self) -> str:
        """Issue a new CSRF token.

        Returns:
            New CSRF token
        """
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._store[token] = now
        self.prune(now)
        return token

    def touch(self, token: str | None) -> bool:
        """Touch (validate and update) a CSRF token.

        Args:
            token: CSRF token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if not token:
            return False
        now = time.time()
        cutoff = now - self._ttl_seconds
        with self._lock:
            timestamp = self._store.get(token)
            if not timestamp or timestamp < cutoff:
                self._store.pop(token, None)
                return False
            self._store[token] = now
            return True

    def consume(self, token: str | None) -> None:
        """Consume (remove) a CSRF token.

        Args:
            token: CSRF token to remove
        """
        if not token:
            return
        with self._lock:
            self._store.pop(token, None)

    def prune(self, now: float | None = None) -> None:
        """Prune expired CSRF tokens.

        Args:
            now: Current time (defaults to time.time())
        """
        now = now or time.time()
        cutoff = now - self._ttl_seconds
        with self._lock:
            expired = [token for token, ts in self._store.items() if ts < cutoff]
            for token in expired:
                self._store.pop(token, None)


__all__ = [
    "generate_captcha_text",
    "random_color",
    "load_captcha_font",
    "build_captcha_image",
    "build_svg_captcha",
    "CaptchaStore",
    "LoginCSRFStore",
]
