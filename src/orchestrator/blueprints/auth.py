"""Authentication and captcha routes."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

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

# PIL imports are now handled in common.captcha
from werkzeug.security import check_password_hash

from common.captcha_helpers import (
    build_captcha_image_with_settings,
    get_captcha_nonce_with_store,
    get_captcha_store_for_app,
    get_login_csrf_store_for_app,
    refresh_captcha_with_store,
)
from common.constants import (
    LOGIN_BLOCK_WINDOW_MINUTES,
    MAX_LOGIN_ATTEMPTS,
)

from ..extensions import csrf
from common.services.logging import FileLogger
from .utils import _settings, get_client_ip

auth_bp = Blueprint("auth", __name__, url_prefix="/orchestrator")

login_attempts: defaultdict[str | None, deque] = defaultdict(
    lambda: deque(maxlen=MAX_LOGIN_ATTEMPTS)
)
BLOCK_WINDOW = timedelta(minutes=LOGIN_BLOCK_WINDOW_MINUTES)

# Global stores (will be initialized lazily with settings values)
_captcha_store = None
_login_csrf_store = None
_captcha_store_lock = Lock()
_login_csrf_store_lock = Lock()


def _logger() -> FileLogger:
    """Get logger from Flask app config."""
    return current_app.config["LOGGER"]


def _get_captcha_store():
    """Get or create CAPTCHA store with current settings TTL."""
    global _captcha_store
    if _captcha_store is None:
        with _captcha_store_lock:
            if _captcha_store is None:
                settings = _settings()
                _captcha_store = get_captcha_store_for_app(settings)
    return _captcha_store


def _get_login_csrf_store():
    """Get or create login CSRF store with current settings TTL."""
    global _login_csrf_store
    if _login_csrf_store is None:
        with _login_csrf_store_lock:
            if _login_csrf_store is None:
                settings = _settings()
                _login_csrf_store = get_login_csrf_store_for_app(settings)
    return _login_csrf_store


def _build_captcha_image(text: str) -> tuple[bytes, str]:
    """Build CAPTCHA image using settings."""
    settings = _settings()

    def on_svg_warning(msg: str) -> None:
        _logger().log(msg)

    return build_captcha_image_with_settings(
        text, settings, on_svg_warning=on_svg_warning
    )


def _store_captcha_entry(nonce: str, text: str) -> None:
    """Store CAPTCHA entry in store."""
    _get_captcha_store().store(nonce, text)


def _get_captcha_from_store(nonce: str | None) -> str | None:
    """Get CAPTCHA from store."""
    return _get_captcha_store().get(nonce)


def _drop_captcha_from_store(nonce: str | None) -> None:
    """Drop CAPTCHA from store."""
    _get_captcha_store().drop(nonce)


def _issue_login_csrf_token() -> str:
    """Issue login CSRF token."""
    return _get_login_csrf_store().issue()


def _touch_login_csrf_token(token: str | None) -> bool:
    """Touch login CSRF token."""
    return _get_login_csrf_store().touch(token)


def _consume_login_csrf_token(token: str | None) -> None:
    """Consume login CSRF token."""
    _get_login_csrf_store().consume(token)


def _refresh_captcha() -> str:
    """Generate a new CAPTCHA and store it."""
    settings = _settings()
    store = _get_captcha_store()

    def on_svg_warning(msg: str) -> None:
        _logger().log(msg)

    return refresh_captcha_with_store(
        store, settings, session, on_svg_warning=on_svg_warning
    )


def _get_captcha_nonce() -> str:
    """Get existing CAPTCHA nonce from session or create a new one."""
    settings = _settings()
    store = _get_captcha_store()

    def on_svg_warning(msg: str) -> None:
        _logger().log(msg)

    return get_captcha_nonce_with_store(
        store, session, settings, on_svg_warning=on_svg_warning
    )


def is_blocked(ip: str | None, current_time: datetime | None = None) -> bool:
    attempts = login_attempts[ip]
    now = current_time or datetime.now()
    while attempts and now - attempts[0] > BLOCK_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


def register_failed_attempt(
    ip: str | None, attempt_time: datetime | None = None
) -> None:
    login_attempts[ip].append(attempt_time or datetime.now())


def is_safe_redirect(target: str | None) -> bool:
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
    captcha_nonce: str | None = None
    login_csrf_token: str | None = None

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

        if not captcha_nonce_field:
            error = (
                "CAPTCHA nonce is required. Please refresh the CAPTCHA and try again."
            )
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
            session.permanent = True
            if captcha_nonce_field:
                _drop_captcha_from_store(captcha_nonce_field)
            _logger().log(
                "[AUTH SUCCESS] Login allowed",
                context={"username": username, "client_ip": client_ip},
            )
            next_url = request.args.get("next")
            if not is_safe_redirect(next_url):
                next_url = url_for("dashboard.dashboard")
            session.pop("captcha_nonce", None)
            return redirect(next_url)

        register_failed_attempt(client_ip)
        _logger().log(
            "[AUTH FAIL] Invalid credentials",
            context={"username": username, "client_ip": client_ip},
        )
        error = "Invalid username or password."
        if captcha_nonce_field:
            _drop_captcha_from_store(captcha_nonce_field)
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
    text: str | None = None

    if renew:
        _drop_captcha_from_store(nonce_param)
        nonce_param = _refresh_captcha()
        text = _get_captcha_from_store(nonce_param)
    else:
        # Try to get CAPTCHA from store if nonce provided
        if nonce_param:
            text = _get_captcha_from_store(nonce_param)

        # If no nonce provided or CAPTCHA not found, generate a new one
        if not text:
            nonce_param = _refresh_captcha()
            text = _get_captcha_from_store(nonce_param)

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
