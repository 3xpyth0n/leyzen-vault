"""CAPTCHA generation utilities shared across Leyzen Vault components."""

from __future__ import annotations

import html
import random
import secrets
import string
import time
from io import BytesIO
from threading import Lock
from typing import Callable

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
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

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
            self._store[nonce] = (text, now)
        self.prune(now)

    def get(self, nonce: str | None) -> str | None:
        """Get CAPTCHA text by nonce.

        Args:
            nonce: Nonce identifier

        Returns:
            CAPTCHA text or None if not found or expired
        """
        if not nonce:
            return None
        cutoff = time.time() - self._ttl_seconds
        with self._lock:
            entry = self._store.get(nonce)
            if not entry:
                return None
            text, timestamp = entry
            if timestamp < cutoff:
                self._store.pop(nonce, None)
                return None
            return text

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
            expired = [key for key, (_, ts) in self._store.items() if ts < cutoff]
            for key in expired:
                self._store.pop(key, None)


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
