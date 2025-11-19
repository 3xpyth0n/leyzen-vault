"""
Legacy authentication endpoints for session-based auth.

⚠️ DEPRECATION WARNING:
This module is maintained for backward compatibility only.
All new code should use auth_api.py with JWT authentication.

This module will be removed in a future version. Migrate to:
- auth_api.py for JWT-based authentication
- Use @jwt_required decorator instead of @login_required
- Use get_current_user() from middleware.jwt_auth instead of session-based auth

See docs/AUTHENTICATION.md for migration guide.
"""

from __future__ import annotations

import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from urllib.parse import urljoin, urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    session,
    url_for,
)

from vault.middleware.jwt_auth import jwt_required

from vault.services.auth_service import AuthService

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
from ..models import User
from ..database.schema import User as UserModel, db
from common.services.logging import FileLogger
from .utils import _settings, get_client_ip

auth_bp = Blueprint("auth", __name__, url_prefix="")

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


def _get_auth_service() -> AuthService:
    """Get AuthService instance."""
    secret_key = current_app.config.get("SECRET_KEY", "")
    return AuthService(secret_key)


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
    now = current_time or datetime.now(timezone.utc)
    while attempts and now - attempts[0] > BLOCK_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


def register_failed_attempt(
    ip: str | None, attempt_time: datetime | None = None
) -> None:
    login_attempts[ip].append(attempt_time or datetime.now(timezone.utc))


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


def verify_credentials(username: str, password: str) -> tuple[bool, User | None]:
    """Verify user credentials and return user if valid.

    Uses PostgreSQL-based authentication with Argon2 password hashing.
    """
    # Query user from PostgreSQL by email (username is email in v2.0.0)
    user_model = db.session.query(UserModel).filter_by(email=username).first()
    if user_model:
        try:
            auth_service = _get_auth_service()
            result = auth_service.authenticate(username, password)
            if result:
                user, token = result
                # Update last login (already done by AuthService, but ensure it's saved)
                user_model.last_login = datetime.now(timezone.utc)
                db.session.commit()
                # Convert to User dataclass for compatibility
                return True, User(
                    user_id=user_model.id,
                    username=user_model.email,  # Use email as username
                    password_hash=user_model.password_hash,
                    email=user_model.email,
                    created_at=user_model.created_at,
                    last_login=user_model.last_login,
                    is_admin=user_model.global_role.value == "admin",
                )
        except ValueError as e:
            # Email not verified or other validation error
            _logger().log(f"[ERROR] Authentication error: {e}")
        except Exception as e:
            _logger().log(f"[ERROR] Authentication failure: {e}")
        return False, None

    return False, None


# All frontend routes (/login, /register) are handled by Vue.js SPA
# Only API routes remain here (already in auth_api.py)


@auth_bp.route("/captcha-image", methods=["GET"])
def captcha_image():
    renew = request.args.get("renew") == "1"
    nonce_param = request.args.get("nonce", "").strip()
    text: str | None = None

    if renew:
        _drop_captcha_from_store(nonce_param)
        nonce_param = _refresh_captcha()
        text = session.get("captcha_text", "")
    else:
        # Try to get CAPTCHA from store if nonce provided
        if nonce_param:
            text = _get_captcha_from_store(nonce_param)
            # If found in store, ensure it's also in session for API fallback
            if text:
                session["captcha_text"] = text
                session["captcha_nonce"] = nonce_param

        # Fallback to session-based CAPTCHA
        if not text:
            session_text = session.get("captcha_text")
            session_nonce = session.get("captcha_nonce")
            if session_text:
                text = str(session_text)
                # If nonce was provided, store it in the store for consistency
                if nonce_param and nonce_param != session_nonce:
                    # Nonce mismatch - store the session CAPTCHA with the provided nonce
                    _store_captcha_entry(nonce_param, text)
                elif not nonce_param and session_nonce:
                    # No nonce provided but session has one - use session nonce
                    nonce_param = session_nonce
                    _store_captcha_entry(nonce_param, text)
                elif not nonce_param:
                    # No nonce at all - create one and store
                    if not session_nonce:
                        session_nonce = secrets.token_urlsafe(8)
                        session["captcha_nonce"] = session_nonce
                    nonce_param = session_nonce
                    _store_captcha_entry(nonce_param, text)

        # Last resort: create new CAPTCHA only if absolutely nothing exists
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
    # CSRF token is optional for captcha refresh (public endpoint before login)
    # If provided, validate it; if not, still allow refresh (session-based)
    submitted_login_csrf = (
        request.headers.get("X-Login-CSRF", "").strip()
        or request.form.get("login_csrf_token", "").strip()
    )
    # Only validate CSRF if provided (for compatibility with orchestrator)
    # For API usage, CSRF is not required
    if submitted_login_csrf:
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
@jwt_required
def logout():
    """Logout user - blacklist JWT token.

    Note: This endpoint now uses JWT authentication instead of session-based auth.
    The client should discard the token after calling this endpoint.
    """
    from flask import jsonify
    from vault.middleware.jwt_auth import get_current_user
    from vault.services.auth_service import AuthService
    import jwt
    from datetime import datetime, timezone

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        # Get current user (already validated by jwt_required)
        user = get_current_user()

        if user and token:
            # Blacklist the token
            secret_key = current_app.config.get("SECRET_KEY")
            if secret_key:
                try:
                    # Decode token to get expiration
                    payload = jwt.decode(
                        token,
                        secret_key,
                        algorithms=["HS256"],
                        options={"verify_signature": False, "verify_exp": False},
                    )
                    expiration_time = datetime.fromtimestamp(
                        payload.get("exp", 0), tz=timezone.utc
                    )

                    # Blacklist token
                    auth_service = AuthService(secret_key)
                    auth_service.blacklist_token(token, expiration_time)
                except Exception:
                    # If token decode fails, still return success
                    # (token might already be invalid)
                    pass

    # Clear any session data (for backward compatibility)
    session.clear()

    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


__all__ = [
    "auth_bp",
    "is_blocked",
    "register_failed_attempt",
    "verify_credentials",
]
