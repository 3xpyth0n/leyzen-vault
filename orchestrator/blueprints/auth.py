"""Authentication and captcha routes."""

from __future__ import annotations

import random
import secrets
import string
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from io import BytesIO
from threading import Lock
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except (
    ModuleNotFoundError
) as exc:  # pragma: no cover - fallback path for optional dependency
    Image = ImageDraw = ImageFilter = ImageFont = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR: Optional[ModuleNotFoundError] = exc
else:  # pragma: no branch
    _PIL_IMPORT_ERROR = None
from werkzeug.security import check_password_hash

from ..extensions import csrf
from ..services.logging import FileLogger
from .utils import get_client_ip

auth_bp = Blueprint("auth", __name__, url_prefix="/orchestrator")

CAPTCHA_IMAGE_WIDTH_DEFAULT = 220
CAPTCHA_IMAGE_HEIGHT_DEFAULT = 70
CAPTCHA_LENGTH_DEFAULT = 6

login_attempts: defaultdict[str | None, deque] = defaultdict(lambda: deque(maxlen=10))
MAX_ATTEMPTS = 5
BLOCK_WINDOW = timedelta(minutes=5)

captcha_store: Dict[str, Tuple[str, float]] = {}
captcha_store_lock = Lock()
login_csrf_store: Dict[str, float] = {}
login_csrf_lock = Lock()


def _logger() -> FileLogger:
    return current_app.config["LOGGER"]


def _settings():
    return current_app.config["SETTINGS"]


def _generate_captcha_text(length: int) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _random_color(min_value: int = 0, max_value: int = 255) -> tuple[int, int, int]:
    return tuple(random.randint(min_value, max_value) for _ in range(3))


def _load_captcha_font(size: int = 22):
    base_font = ImageFont.load_default()
    try:
        return base_font.font_variant(size=size)
    except AttributeError:
        return base_font


def _build_captcha_image(text: str) -> tuple[bytes, str]:
    settings = _settings()
    width = getattr(settings, "captcha_image_width", CAPTCHA_IMAGE_WIDTH_DEFAULT)
    height = getattr(settings, "captcha_image_height", CAPTCHA_IMAGE_HEIGHT_DEFAULT)

    if (
        Image is not None
        and ImageDraw is not None
        and ImageFilter is not None
        and ImageFont is not None
    ):
        image = Image.new("RGB", (width, height), _random_color(200, 255))
        draw = ImageDraw.Draw(image)

        for _ in range(6):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=_random_color(80, 200), width=2)

        font = _load_captcha_font()
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
                fill=_random_color(10, 70),
                stroke_width=2,
                stroke_fill=(0, 0, 0),
            )

        for _ in range(300):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            image.putpixel((x, y), _random_color(0, 255))

        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read(), "image/png"

    return _build_svg_captcha(text, width, height)


_svg_warning_emitted = False


def _build_svg_captcha(text: str, width: int, height: int) -> tuple[bytes, str]:
    import html

    # The SVG fallback intentionally mirrors the noise pattern of the Pillow
    # version to remain resistant to trivial OCR when Pillow is unavailable.
    background = _random_color(220, 255)
    svg_lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        f"<rect width='100%' height='100%' fill='rgb{background}' />",
    ]

    for _ in range(6):
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        end_x = random.randint(0, width)
        end_y = random.randint(0, height)
        color = _random_color(80, 200)
        svg_lines.append(
            f"<line x1='{start_x}' y1='{start_y}' x2='{end_x}' y2='{end_y}' stroke='rgb{color}' stroke-width='2' />"
        )

    char_spacing = width // (len(text) + 1)
    for index, character in enumerate(text):
        x = 15 + index * char_spacing + random.randint(-5, 5)
        y = random.randint(height // 2, height - 10)
        fill_color = _random_color(10, 70)
        svg_lines.append(
            "<text "
            "font-family='monospace' "
            "font-size='32' "
            "stroke='black' stroke-width='1' "
            f"fill='rgb{fill_color}' x='{x}' y='{y}'>"
            f"{html.escape(character)}</text>"
        )

    for _ in range(300):
        x = random.randint(0, width)
        y = random.randint(0, height)
        color = _random_color(0, 255)
        svg_lines.append(f"<circle cx='{x}' cy='{y}' r='1' fill='rgb{color}' />")

    svg_lines.append("</svg>")
    svg_content = "".join(svg_lines).encode("utf-8")
    global _svg_warning_emitted
    if _PIL_IMPORT_ERROR is not None and not _svg_warning_emitted:
        _logger().warning(
            "Pillow not available, serving SVG captcha fallback. Install Pillow to restore PNG captcha rendering: %s",
            _PIL_IMPORT_ERROR,
        )
        _svg_warning_emitted = True
    return svg_content, "image/svg+xml"


def _settings_captcha_length() -> int:
    settings = _settings()
    return getattr(settings, "captcha_length", CAPTCHA_LENGTH_DEFAULT)


def _captcha_store_ttl() -> int:
    settings = _settings()
    return getattr(settings, "captcha_store_ttl", 300)


def _login_csrf_ttl() -> int:
    settings = _settings()
    return getattr(settings, "login_csrf_ttl", 900)


def _prune_captcha_store(now: Optional[float] = None) -> None:
    cutoff = (now or time.time()) - _captcha_store_ttl()
    with captcha_store_lock:
        expired = [key for key, (_, ts) in captcha_store.items() if ts < cutoff]
        for key in expired:
            captcha_store.pop(key, None)


def _store_captcha_entry(nonce: str, text: str) -> None:
    if not nonce:
        return
    now = time.time()
    with captcha_store_lock:
        captcha_store[nonce] = (text, now)
    _prune_captcha_store(now)


def _get_captcha_from_store(nonce: Optional[str]) -> Optional[str]:
    if not nonce:
        return None
    cutoff = time.time() - _captcha_store_ttl()
    with captcha_store_lock:
        entry = captcha_store.get(nonce)
        if not entry:
            return None
        text, timestamp = entry
        if timestamp < cutoff:
            captcha_store.pop(nonce, None)
            return None
        return text


def _drop_captcha_from_store(nonce: Optional[str]) -> None:
    if not nonce:
        return
    with captcha_store_lock:
        captcha_store.pop(nonce, None)


def _prune_login_csrf_store(now: Optional[float] = None) -> None:
    now = now or time.time()
    cutoff = now - _login_csrf_ttl()
    with login_csrf_lock:
        expired = [token for token, ts in login_csrf_store.items() if ts < cutoff]
        for token in expired:
            login_csrf_store.pop(token, None)


def _issue_login_csrf_token() -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with login_csrf_lock:
        login_csrf_store[token] = now
    _prune_login_csrf_store(now)
    return token


def _touch_login_csrf_token(token: Optional[str]) -> bool:
    if not token:
        return False
    now = time.time()
    cutoff = now - _login_csrf_ttl()
    with login_csrf_lock:
        timestamp = login_csrf_store.get(token)
        if not timestamp or timestamp < cutoff:
            login_csrf_store.pop(token, None)
            return False
        login_csrf_store[token] = now
        return True


def _consume_login_csrf_token(token: Optional[str]) -> None:
    if not token:
        return
    with login_csrf_lock:
        login_csrf_store.pop(token, None)


def _refresh_captcha() -> str:
    text = _generate_captcha_text(_settings_captcha_length())
    nonce = secrets.token_urlsafe(8)
    session["captcha_text"] = text
    session["captcha_nonce"] = nonce
    _store_captcha_entry(nonce, text)
    return nonce


def _get_captcha_nonce() -> str:
    text = session.get("captcha_text")
    nonce = session.get("captcha_nonce")
    if not text or not nonce:
        nonce = _refresh_captcha()
    else:
        _store_captcha_entry(str(nonce), str(text))
    return nonce


def is_blocked(ip: str | None, current_time: Optional[datetime] = None) -> bool:
    attempts = login_attempts[ip]
    now = current_time or datetime.now()
    while attempts and now - attempts[0] > BLOCK_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_ATTEMPTS


def register_failed_attempt(
    ip: str | None, attempt_time: Optional[datetime] = None
) -> None:
    login_attempts[ip].append(attempt_time or datetime.now())


def is_safe_redirect(target: Optional[str]) -> bool:
    if not target:
        return False

    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(urljoin(request.host_url, target))

    return (
        test_url.scheme in {"http", "https"}
        and ref_url.netloc == test_url.netloc
        and test_url.path.startswith("/")
    )


def verify_credentials(username: str, password: str) -> bool:
    settings = _settings()
    if username != settings.username:
        return False
    try:
        return check_password_hash(settings.password_hash, password)
    except Exception:
        _logger().log("[ERROR] check_password_hash failure")
        return False


@auth_bp.route("/login", methods=["GET", "POST"])
@csrf.exempt
def login():
    error = None
    client_ip = get_client_ip()
    captcha_nonce: Optional[str] = None
    login_csrf_token: Optional[str] = None

    if request.method == "POST":
        submitted_login_csrf = request.form.get("login_csrf_token", "").strip()
        if not _touch_login_csrf_token(submitted_login_csrf):
            _logger().log(
                "[AUTH FAIL] Missing or expired login CSRF token",
                context={"client_ip": client_ip},
            )
            error = "Your session expired. Please try again."
            captcha_nonce = _refresh_captcha()
            login_csrf_token = _issue_login_csrf_token()
            return (
                render_template(
                    "login.html",
                    error=error,
                    captcha_nonce=captcha_nonce,
                    login_csrf_token=login_csrf_token,
                ),
                400,
            )

        _consume_login_csrf_token(submitted_login_csrf)
        if is_blocked(client_ip):
            _logger().log(
                "[AUTH BLOCKED] Too many attempts",
                context={"client_ip": client_ip},
            )
            error = "Too many attempts, try again later."
            captcha_nonce = _refresh_captcha()
            login_csrf_token = _issue_login_csrf_token()
            return (
                render_template(
                    "login.html",
                    error=error,
                    captcha_nonce=captcha_nonce,
                    login_csrf_token=login_csrf_token,
                ),
                429,
            )

        username = request.form.get("username", "")
        password = request.form.get("password", "")
        captcha_response = request.form.get("captcha", "").strip().upper()
        captcha_nonce_field = request.form.get("captcha_nonce", "").strip()
        expected_captcha = session.get("captcha_text")
        if not expected_captcha:
            expected_captcha = _get_captcha_from_store(captcha_nonce_field)

        if not expected_captcha or captcha_response != str(expected_captcha).upper():
            register_failed_attempt(client_ip)
            error = "Invalid captcha response."
            _drop_captcha_from_store(captcha_nonce_field)
            captcha_nonce = _refresh_captcha()
            login_csrf_token = _issue_login_csrf_token()
            return (
                render_template(
                    "login.html",
                    error=error,
                    captcha_nonce=captcha_nonce,
                    login_csrf_token=login_csrf_token,
                ),
                400,
            )

        if verify_credentials(username, password):
            session["logged_in"] = True
            session.permanent = False
            _drop_captcha_from_store(
                captcha_nonce_field or session.get("captcha_nonce")
            )
            _logger().log(
                "[AUTH SUCCESS] Login allowed",
                context={"username": username, "client_ip": client_ip},
            )
            next_url = request.args.get("next")
            if not is_safe_redirect(next_url):
                next_url = url_for("dashboard.dashboard")
            session.pop("captcha_nonce", None)
            session.pop("captcha_text", None)
            return redirect(next_url)

        register_failed_attempt(client_ip)
        _logger().log(
            "[AUTH FAIL] Invalid credentials",
            context={"username": username, "client_ip": client_ip},
        )
        error = "Invalid username or password."
        _drop_captcha_from_store(captcha_nonce_field or session.get("captcha_nonce"))
        captcha_nonce = _refresh_captcha()
        login_csrf_token = _issue_login_csrf_token()

    if captcha_nonce is None:
        captcha_nonce = _get_captcha_nonce()
    if login_csrf_token is None:
        login_csrf_token = _issue_login_csrf_token()

    return render_template(
        "login.html",
        error=error,
        captcha_nonce=captcha_nonce,
        login_csrf_token=login_csrf_token,
    )


@auth_bp.route("/captcha-image", methods=["GET"])
def captcha_image():
    renew = request.args.get("renew") == "1"
    nonce_param = request.args.get("nonce", "").strip()
    text: Optional[str] = None

    if renew:
        _drop_captcha_from_store(nonce_param)
        nonce_param = _refresh_captcha()
        text = session.get("captcha_text", "")
    else:
        if nonce_param:
            text = _get_captcha_from_store(nonce_param)

        if not text:
            session_text = session.get("captcha_text")
            session_nonce = session.get("captcha_nonce")
            if (
                session_text
                and session_nonce
                and (not nonce_param or nonce_param == session_nonce)
            ):
                nonce_param = session_nonce
                text = str(session_text)
                _store_captcha_entry(nonce_param, str(session_text))

        if not text:
            nonce_param = _refresh_captcha()
            text = session.get("captcha_text", "")

    image_bytes, mimetype = _build_captcha_image(str(text))

    response = make_response(image_bytes)
    response.headers["Content-Type"] = mimetype
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@auth_bp.route("/captcha-refresh", methods=["POST"])
@csrf.exempt
def captcha_refresh():
    submitted_login_csrf = (
        request.headers.get("X-Login-CSRF", "").strip()
        or request.form.get("login_csrf_token", "").strip()
    )
    if not _touch_login_csrf_token(submitted_login_csrf):
        abort(400, description="Invalid or expired login session.")
    nonce = _refresh_captcha()
    image_url = url_for("auth.captcha_image", nonce=nonce)
    response = jsonify({"nonce": nonce, "image_url": image_url})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@auth_bp.route("/logout", methods=["GET"], endpoint="logout_get")
def logout_get():
    abort(405)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


__all__ = [
    "auth_bp",
    "is_blocked",
    "register_failed_attempt",
    "verify_credentials",
]
