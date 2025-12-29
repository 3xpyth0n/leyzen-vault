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
from common.captcha import DatabaseCaptchaStore
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


def _get_session_id() -> str:
    """Get or create session ID for CAPTCHA isolation."""
    if "_id" not in session:
        import secrets

        session["_id"] = secrets.token_urlsafe(16)
    return session["_id"]


def _store_captcha_entry(nonce: str, text: str) -> None:
    """Store CAPTCHA entry in store."""
    store = _get_captcha_store()
    session_id = _get_session_id()
    if isinstance(store, DatabaseCaptchaStore):
        store.store(nonce, text, session_id)
    else:
        store.store(nonce, text)


def _get_captcha_from_store(nonce: str | None) -> str | None:
    """Get CAPTCHA from store."""
    store = _get_captcha_store()
    session_id = _get_session_id()
    if isinstance(store, DatabaseCaptchaStore):
        return store.get(nonce, session_id)
    else:
        return store.get(nonce)


def _drop_captcha_from_store(nonce: str | None) -> None:
    """Drop CAPTCHA from store."""
    store = _get_captcha_store()
    session_id = _get_session_id()
    if isinstance(store, DatabaseCaptchaStore):
        store.drop(nonce, session_id)
    else:
        store.drop(nonce)


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
        _logger().error("[ERROR] check_password_hash failure")
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
            _logger().warning(
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
            _logger().warning(
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
            # Increment attempt counter and drop if limit reached
            if captcha_nonce_field:
                captcha_store = _get_captcha_store()
                session_id = _get_session_id()
                if isinstance(captcha_store, DatabaseCaptchaStore):
                    attempts = captcha_store.increment_attempts(
                        captcha_nonce_field, session_id
                    )
                    if attempts >= 2:
                        _drop_captcha_from_store(captcha_nonce_field)
                else:
                    attempts = captcha_store.increment_attempts(captcha_nonce_field)
                    if attempts >= 2:
                        _drop_captcha_from_store(captcha_nonce_field)
                if attempts >= 2:
                    error = "Too many failed attempts. Please refresh the CAPTCHA and try again."
                    captcha_nonce = _refresh_captcha()
                else:
                    error = "Incorrect captcha response."
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
            error = "Incorrect captcha response."
            captcha_nonce = _get_captcha_nonce()
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
            _logger().warning(
                "[AUTH SUCCESS] Login allowed",
                context={"username": username, "client_ip": client_ip},
            )
            next_url = request.args.get("next")
            if not is_safe_redirect(next_url):
                next_url = url_for("dashboard.dashboard")
            session.pop("captcha_nonce", None)
            return redirect(next_url)

        register_failed_attempt(client_ip)
        _logger().warning(
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
    """Get CAPTCHA image.

    Query parameters:
        - renew: If "1", generate a new CAPTCHA
        - nonce: Optional CAPTCHA nonce

    Returns:
        CAPTCHA image (PNG or SVG)
        Includes X-Captcha-Nonce header only when a new CAPTCHA is generated
        (when renew=1 or no nonce provided)

    Core principle: One nonce = one image. Never auto-generate when nonce is provided.
    """
    renew = request.args.get("renew") == "1"
    nonce_param = request.args.get("nonce", "").strip()
    text: str | None = None
    new_captcha_generated = False

    if renew:
        # Force generation of new CAPTCHA
        _drop_captcha_from_store(nonce_param)
        nonce_param = _refresh_captcha()
        text = _get_captcha_from_store(nonce_param)
        new_captcha_generated = True
    elif nonce_param:
        # Nonce provided - return that specific CAPTCHA or error
        text = _get_captcha_from_store(nonce_param)
        if not text:
            # Nonce not found or expired - return error, DON'T generate new one
            abort(404, description="CAPTCHA not found or expired")
    else:
        # No nonce provided - generate new CAPTCHA
        nonce_param = _refresh_captcha()
        text = _get_captcha_from_store(nonce_param)
        new_captcha_generated = True

    # Ensure we have valid text
    if not text:
        # This should never happen, but handle gracefully
        _logger().error("[ERROR] Failed to get CAPTCHA text")
        abort(500, description="Failed to generate CAPTCHA")

    image_bytes, mimetype = _build_captcha_image(str(text))

    response = make_response(image_bytes)
    response.headers["Content-Type"] = mimetype
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    # Only include nonce in header if a new CAPTCHA was generated
    if new_captcha_generated and nonce_param:
        response.headers["X-Captcha-Nonce"] = nonce_param

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
