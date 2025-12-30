"""Authentication API routes for Leyzen Vault."""

from __future__ import annotations

from threading import Lock

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    make_response,
    request,
    session,
    url_for,
)

from vault.database.schema import GlobalRole
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.auth_service import AuthService
from vault.services.vaultspace_service import VaultSpaceService
from vault.blueprints.validators import validate_email
from vault.blueprints.utils import _settings
from .utils import get_client_ip
from common.captcha_helpers import (
    build_captcha_image_with_settings,
    get_captcha_store_for_app,
    get_login_csrf_store_for_app,
    refresh_captcha_with_store,
)
from common.captcha import DatabaseCaptchaStore
from common.services.logging import FileLogger

auth_api_bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")

# Global stores (will be initialized lazily with settings values)
_captcha_store = None
_login_csrf_store = None
_captcha_store_lock = Lock()
_login_csrf_store_lock = Lock()


def _logger() -> FileLogger:
    """Get logger from Flask app config."""
    return current_app.config["LOGGER"]


def _get_audit():
    """Get audit service from Flask app config."""

    return current_app.config.get("VAULT_AUDIT")


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


def _touch_login_csrf_token(token: str | None) -> bool:
    """Touch login CSRF token."""
    return _get_login_csrf_store().touch(token)


def _refresh_captcha() -> str:
    """Generate a new CAPTCHA and store it."""
    settings = _settings()
    store = _get_captcha_store()

    def on_svg_warning(msg: str) -> None:
        _logger().log(msg)

    return refresh_captcha_with_store(
        store, settings, session, on_svg_warning=on_svg_warning
    )


def _get_auth_service() -> AuthService:
    """Get AuthService instance."""
    secret_key = current_app.config.get("SECRET_KEY", "")
    settings = _settings()
    return AuthService(secret_key, jwt_expiration_hours=settings.jwt_expiration_hours)


@auth_api_bp.route("/sso/providers", methods=["GET"])
@csrf.exempt  # Public endpoint
def list_sso_providers():
    """List all active SSO providers (public endpoint).

    Returns:
        JSON with list of active SSO providers
    """
    try:
        from vault.services.sso_service import SSOService
        from vault.database.schema import SSOProviderType

        sso_service = SSOService()
        providers = sso_service.list_providers()

        # Return provider info without sensitive config data
        providers_data = []
        for provider in providers:
            provider_dict = provider.to_dict()
            # Remove sensitive information from config
            config = provider_dict.get("config", {})
            # Only expose non-sensitive config fields
            safe_config = {}
            if provider.provider_type == SSOProviderType.SAML:
                safe_config = {
                    "entity_id": config.get("entity_id"),
                    "sso_url": config.get("sso_url"),
                }
            elif provider.provider_type in (
                SSOProviderType.OAUTH2,
                SSOProviderType.OIDC,
            ):
                safe_config = {
                    "authorization_url": config.get("authorization_url"),
                }
                if provider.provider_type == SSOProviderType.OIDC:
                    safe_config["issuer_url"] = config.get("issuer_url")

            providers_data.append(
                {
                    "id": provider_dict["id"],
                    "name": provider_dict["name"],
                    "provider_type": provider_dict["provider_type"],
                    "is_active": provider_dict["is_active"],
                    "config": safe_config,
                }
            )

        return jsonify({"providers": providers_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing SSO providers: {e}")
        return jsonify({"error": "Failed to list SSO providers"}), 500


@auth_api_bp.route("/signup", methods=["POST"])
@csrf.exempt  # Public endpoint, CSRF not needed for JWT-based auth
def signup():
    """Create a new user account and automatically create Personal VaultSpace.

    Request body:
        {
            "email": "user@example.com",
            "password": "securepassword",
            "encrypted_vaultspace_key": "encrypted-key" (optional, if provided will be stored)
        }

    Returns:
        JSON with user info, JWT token, and Personal VaultSpace info
    """

    # Rate limiting: 5 attempts per minute per IP
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        # For signup, we can't use user_id yet, but we can track by email
        # This provides some protection against distributed attacks
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="auth_signup",
            user_id=None,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    encrypted_vaultspace_key = data.get("encrypted_vaultspace_key", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    # Check if signup is allowed
    from vault.database.schema import SystemSettings, db

    setting = db.session.query(SystemSettings).filter_by(key="allow_signup").first()
    if setting:
        allow_signup = setting.value.lower() == "true"
    else:
        allow_signup = True

    if not allow_signup:
        return (
            jsonify(
                {
                    "error": "Public registration is disabled. Contact an administrator for an invitation."
                }
            ),
            403,
        )

    # Validate email domain against domain rules
    from vault.services.domain_service import DomainService

    domain_service = DomainService()
    is_allowed, error_message = domain_service.validate_email_domain(email)
    if not is_allowed:
        return jsonify({"error": error_message or "Domain not allowed"}), 403

    auth_service = _get_auth_service()
    vaultspace_service = VaultSpaceService()

    try:
        # Create user (email_verified will be False by default)
        user = auth_service.create_user(email, password, GlobalRole.USER)

        # Send verification email (always required)
        # VAULT_URL from settings will be used automatically
        from vault.services.email_verification_service import EmailVerificationService

        email_verification_service = EmailVerificationService()
        email_verification_service.send_verification_email(
            user_id=user.id,
            base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
        )

        # Create Personal VaultSpace automatically
        personal_vaultspace = vaultspace_service.create_vaultspace(
            name="My Drive",
            owner_user_id=user.id,
            encrypted_metadata=None,
        )

        if encrypted_vaultspace_key:
            from vault.services.encryption_service import EncryptionService

            encryption_service = EncryptionService()
            try:
                encryption_service.create_vaultspace_key_entry(
                    vaultspace_id=personal_vaultspace.id,
                    user_id=user.id,
                    encrypted_key=encrypted_vaultspace_key,
                )
            except ValueError as e:
                # Key already exists or error - log but don't fail signup
                current_app.logger.debug(f"Failed to store VaultSpace key: {e}")

        # Log signup
        client_ip = get_client_ip() or "unknown"
        audit = _get_audit()
        if audit:
            audit.log_action(
                action="auth_signup",
                user_ip=client_ip,
                details={
                    "email": email,
                    "user_id": user.id,
                    "email_verification_required": True,
                },
                success=True,
                user_id=user.id,
            )

        # Don't return token - user must verify email first
        return (
            jsonify(
                {
                    "user": user.to_dict(include_salt=False),
                    "email_verification_required": True,
                    "message": "Account created successfully. Please verify your email before logging in.",
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@auth_api_bp.route("/login", methods=["POST"])
@csrf.exempt  # Public endpoint, CSRF not needed for JWT-based auth
def login():
    """Authenticate user and return JWT token.

    Request body:
        {
            "email": "user@example.com",  # or "username" for legacy admin
            "password": "password",
            "captcha_nonce": "nonce" (optional),
            "captcha": "response" (optional)
        }

    Returns:
        JSON with user info and JWT token
    """
    try:
        from flask import session
        from vault.blueprints.utils import (
            _settings,
            register_failed_attempt,
        )
        from vault.database.schema import SystemSettings, db

        # Check if password authentication is enabled
        setting = (
            db.session.query(SystemSettings)
            .filter_by(key="password_authentication_enabled")
            .first()
        )
        password_auth_enabled = True  # Default
        if setting:
            password_auth_enabled = setting.value.lower() == "true"

        if not password_auth_enabled:
            return (
                jsonify(
                    {"error": "Password authentication is disabled. Please use SSO."}
                ),
                400,
            )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        username_or_email = (
            data.get("email", "").strip() or data.get("username", "").strip()
        )
        password = data.get("password", "").strip()

        # Rate limiting: 5 attempts per minute per IP and user
        rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
        client_ip = get_client_ip() or "unknown"
        if rate_limiter:

            user_id_for_rate_limit = None
            if username_or_email:
                from vault.database.schema import User, db

                existing_user = (
                    db.session.query(User).filter_by(email=username_or_email).first()
                )
                if existing_user:
                    user_id_for_rate_limit = existing_user.id
            is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
                client_ip,
                max_attempts=5,
                window_seconds=60,
                action_name="auth_login",
                user_id=user_id_for_rate_limit,
            )
            if not is_allowed:
                # Log rate limit exceeded
                audit = _get_audit()
                if audit:
                    audit.log_action(
                        action="auth_rate_limit_exceeded",
                        user_ip=client_ip,
                        details={
                            "username_or_email": username_or_email,
                            "reason": error_msg or "Too many attempts",
                        },
                        success=False,
                        user_id=user_id_for_rate_limit,
                    )
                return (
                    jsonify(
                        {
                            "error": error_msg
                            or "Too many attempts. Please try again later."
                        }
                    ),
                    429,
                )
        captcha_nonce = data.get("captcha_nonce", "").strip()
        # Get captcha response - can be None if not provided in request
        captcha_response_raw = data.get("captcha")
        # Handle both string and None values, and normalize whitespace
        if captcha_response_raw is None:
            captcha_response = ""
        else:
            captcha_response = str(captcha_response_raw).strip().upper()

        if not username_or_email or not password:
            return jsonify({"error": "Email/username and password are required"}), 400

        # Get settings and captcha store once
        _settings()
        captcha_store = _get_captcha_store()

        # Check if this is a 2FA verification step (credentials already validated)
        totp_token = data.get("totp_token", "").strip() or None
        session_2fa_validated = session.get("2fa_credentials_validated", {})
        is_2fa_step = (
            totp_token
            and session_2fa_validated.get("username") == username_or_email
            and session_2fa_validated.get("captcha_validated") is True
        )

        # CAPTCHA is REQUIRED for login (security requirement), but not for 2FA verification step
        if not is_2fa_step and not captcha_response:
            client_ip = get_client_ip()
            register_failed_attempt(client_ip)
            # Log for debugging (only in development)
            # SECURITY: Never log CAPTCHA details in production
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                # Only log in development mode, and never log actual CAPTCHA values
                current_app.logger.debug(
                    f"CAPTCHA missing: captcha_response_provided={captcha_response_raw is not None}, "
                    f"data keys={list(data.keys())}"
                )
            return jsonify({"error": "CAPTCHA response is required"}), 400

        # Verify CAPTCHA response (skip if this is a 2FA verification step)
        if not is_2fa_step:
            if not captcha_nonce:
                client_ip = get_client_ip()
                register_failed_attempt(client_ip)
                return (
                    jsonify(
                        {
                            "error": "CAPTCHA nonce is required. Please refresh the CAPTCHA and try again."
                        }
                    ),
                    400,
                )

            expected_captcha = _get_captcha_from_store(captcha_nonce)
            # SECURITY: Never log CAPTCHA values or nonces in production
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                # Only log lookup status in development, never actual values
                current_app.logger.debug(
                    f"CAPTCHA lookup by nonce: found={expected_captcha is not None}"
                )

            # Validate CAPTCHA response
            if not expected_captcha:
                client_ip = get_client_ip()
                register_failed_attempt(client_ip)
                # CAPTCHA not found in store
                # SECURITY: Never log CAPTCHA details in production
                is_production = current_app.config.get("IS_PRODUCTION", True)
                if not is_production:
                    # Only log status in development, never actual values
                    current_app.logger.debug("CAPTCHA not found in store")
                return (
                    jsonify(
                        {
                            "error": "CAPTCHA expired or invalid. Please refresh the CAPTCHA and try again."
                        }
                    ),
                    400,
                )

            # Normalize both for comparison (uppercase, strip whitespace)
            expected_normalized = str(expected_captcha).strip().upper()
            received_normalized = captcha_response.strip().upper()

            if received_normalized != expected_normalized:
                client_ip = get_client_ip() or "unknown"
                register_failed_attempt(client_ip)
                # Log CAPTCHA failure
                audit = _get_audit()
                if audit:
                    audit.log_action(
                        action="auth_captcha_failed",
                        user_ip=client_ip,
                        details={
                            "username_or_email": username_or_email,
                            "reason": "Incorrect captcha response",
                        },
                        success=False,
                    )
                # Increment attempt counter and drop if limit reached
                if captcha_nonce:
                    captcha_store = _get_captcha_store()
                    session_id = _get_session_id()
                    if isinstance(captcha_store, DatabaseCaptchaStore):
                        attempts = captcha_store.increment_attempts(
                            captcha_nonce, session_id
                        )
                        if attempts >= 2:
                            _drop_captcha_from_store(captcha_nonce)
                    else:
                        attempts = captcha_store.increment_attempts(captcha_nonce)
                        if attempts >= 2:
                            _drop_captcha_from_store(captcha_nonce)
                    if attempts >= 2:
                        return (
                            jsonify(
                                {
                                    "error": "Too many failed attempts. Please refresh the CAPTCHA and try again."
                                }
                            ),
                            400,
                        )
                # SECURITY: Never log CAPTCHA values in production
                is_production = current_app.config.get("IS_PRODUCTION", True)
                if not is_production:
                    # Only log mismatch status in development, never actual CAPTCHA values
                    current_app.logger.debug(
                        f"CAPTCHA mismatch: expected_len={len(expected_normalized)}, "
                        f"received_len={len(received_normalized)}"
                    )
                return jsonify({"error": "Incorrect captcha response"}), 400

            # Clean up captcha after successful verification
            if captcha_nonce:
                _drop_captcha_from_store(captcha_nonce)

        auth_service = _get_auth_service()

        # Get optional 2FA token from request (already retrieved above)
        # totp_token = data.get("totp_token", "").strip() or None

        try:
            result = auth_service.authenticate(username_or_email, password, totp_token)
        except ValueError as e:
            # Email not verified error
            return jsonify({"error": str(e)}), 403

        if not result:
            client_ip = get_client_ip() or "unknown"
            register_failed_attempt(client_ip)
            # Log authentication failure
            audit = _get_audit()
            if audit:

                user_id_for_log = None
                if username_or_email:
                    from vault.database.schema import User, db

                    existing_user = (
                        db.session.query(User)
                        .filter_by(email=username_or_email)
                        .first()
                    )
                    if existing_user:
                        user_id_for_log = existing_user.id
                audit.log_action(
                    action="auth_login_failed",
                    user_ip=client_ip,
                    details={
                        "username_or_email": username_or_email,
                        "reason": "Invalid credentials",
                    },
                    success=False,
                    user_id=user_id_for_log,
                )
            return jsonify({"error": "Invalid credentials"}), 401

        user, token = result

        # Check if 2FA is required (token is None but user is valid)
        if token is None:
            # 2FA is required - store that credentials were validated
            session["2fa_credentials_validated"] = {
                "username": username_or_email,
                "captcha_validated": True,
            }
            # Return special response
            return (
                jsonify(
                    {
                        "requires_2fa": True,
                        "message": "Two-factor authentication required",
                        "user_id": user.id,  # Frontend may need this for context
                    }
                ),
                200,
            )

        # Full authentication success - clear 2FA session data
        session.pop("2fa_credentials_validated", None)
        # Log successful authentication
        client_ip = get_client_ip() or "unknown"
        audit = _get_audit()
        if audit:
            audit.log_action(
                action="auth_login_success",
                user_ip=client_ip,
                details={
                    "username_or_email": username_or_email,
                    "user_id": user.id,
                    "has_2fa": user.totp_secret is not None,
                },
                success=True,
                user_id=user.id,
            )
        return (
            jsonify(
                {
                    "user": user.to_dict(
                        include_salt=True
                    ),  # Include salt for master key derivation
                    "token": token,
                }
            ),
            200,
        )
    except Exception as e:
        import traceback

        is_production = current_app.config.get("IS_PRODUCTION", True)
        current_app.logger.error(f"Login error: {type(e).__name__}")
        # Only log traceback in development mode to avoid information disclosure
        if not is_production:
            current_app.logger.debug(f"Login error traceback: {traceback.format_exc()}")
        return jsonify({"error": "An error occurred during authentication"}), 500


@auth_api_bp.route("/refresh", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
def refresh():
    """Refresh JWT token.

    Request headers:
        Authorization: Bearer <token>

    Returns:
        JSON with new JWT token
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header missing"}), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid authorization header format"}), 401

    token = parts[1]
    auth_service = _get_auth_service()

    # Validate token format before processing
    if not token or len(token) < 10:
        return jsonify({"error": "Invalid token format"}), 401

    result = auth_service.refresh_token(token)

    if not result:
        return jsonify({"error": "Invalid or expired token"}), 401

    user, new_token = result
    # Log token refresh
    client_ip = get_client_ip() or "unknown"
    audit = _get_audit()
    if audit:
        audit.log_action(
            action="auth_token_refresh",
            user_ip=client_ip,
            details={"user_id": user.id},
            success=True,
            user_id=user.id,
        )
    return (
        jsonify(
            {
                "user": user.to_dict(),
                "token": new_token,
            }
        ),
        200,
    )


@auth_api_bp.route("/me", methods=["GET"])
@jwt_required
def get_me():
    """Get current user profile.

    Request headers:
        Authorization: Bearer <token>

    Cookies:
        jwt_token: JWT token (used for SSO flows with HttpOnly cookies)

    Returns:
        JSON with user info and token (if available from cookie but not in header)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # For SSO flows: if token is in cookie but not in Authorization header,
    # include token in response so frontend can store it in localStorage
    # This allows isAuthenticated() to work correctly
    response_data = {"user": user.to_dict()}

    # Check if token came from cookie (for SSO) and Authorization header is missing
    auth_header = request.headers.get("Authorization")
    has_auth_header = auth_header and auth_header.startswith("Bearer ")
    has_cookie_token = request.cookies.get("jwt_token")

    # This happens during SSO callback flow
    if has_cookie_token and not has_auth_header:
        # Token is in cookie - include it in response so frontend can store in localStorage
        token = getattr(g, "current_token", None) or has_cookie_token
        response_data["token"] = token

    return jsonify(response_data), 200


@auth_api_bp.route("/check", methods=["GET"])
def check_auth():
    """Check if user is authenticated via cookie (for SSO flows).

    This endpoint allows the frontend to check authentication status
    when the token is only in an HttpOnly cookie (not accessible via JavaScript).

    Returns:
        JSON with authenticated status and token (if authenticated)
    """

    token = request.cookies.get("jwt_token")

    if not token:
        return jsonify({"authenticated": False}), 200

    # Verify token is valid
    try:
        # Manually verify token (simplified check)
        secret_key = current_app.config.get("SECRET_KEY")
        if not secret_key:
            return jsonify({"authenticated": False}), 200

        from vault.services.auth_service import AuthService

        settings = current_app.config.get("VAULT_SETTINGS")
        jwt_expiration_hours = settings.jwt_expiration_hours if settings else 120
        auth_service = AuthService(
            secret_key, jwt_expiration_hours=jwt_expiration_hours
        )
        user = auth_service.verify_token(token)

        if user:
            # User is authenticated - return token so frontend can store it in localStorage
            return jsonify({"authenticated": True, "token": token}), 200
        else:
            return jsonify({"authenticated": False}), 200
    except Exception:
        return jsonify({"authenticated": False}), 200


@auth_api_bp.route("/logout", methods=["POST"])
@jwt_required
def logout():
    """Logout user (client should discard token).

    Request headers:
        Authorization: Bearer <token>

    Returns:
        JSON with success message
    """
    # Get token from g (stored by jwt_required middleware) or fallback to header/cookie
    token = getattr(g, "current_token", None)
    if not token:
        # Fallback: try to get from Authorization header or cookie
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Fallback to cookie (for SSO flows using HttpOnly cookies)
            token = request.cookies.get("jwt_token")

    if token:
        try:
            import jwt
            from datetime import datetime

            # Validate token format first
            if not token or len(token) < 10:
                current_app.logger.warning("Invalid token format in logout request")
                return jsonify({"message": "Logged out successfully"}), 200

            secret_key = current_app.config.get("SECRET_KEY", "")
            if not secret_key:
                current_app.logger.error("SECRET_KEY not configured")
                return jsonify({"message": "Logged out successfully"}), 200

            # Decode token to get expiration time with strict validation
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=["HS256"],  # Explicitly require HS256
                options={
                    "verify_signature": True,
                    "verify_exp": False,  # Allow expired tokens to be blacklisted
                    "verify_iat": False,  # Allow old tokens to be blacklisted
                },
            )
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                expiration_time = datetime.utcfromtimestamp(exp_timestamp)
                # Add token to blacklist
                auth_service = _get_auth_service()
                auth_service.blacklist_token(token, expiration_time)
        except jwt.InvalidTokenError:
            # Token is invalid, but we still return success to avoid information leakage
            current_app.logger.debug(
                "Invalid token in logout request (already invalid)"
            )
        except Exception as e:
            current_app.logger.debug(f"Failed to blacklist token: {type(e).__name__}")

    # Create response and delete jwt_token cookie
    response = make_response(jsonify({"message": "Logged out successfully"}), 200)
    response.set_cookie("jwt_token", "", expires=0, path="/")

    return response


@auth_api_bp.route("/setup", methods=["POST"])
@csrf.exempt  # Public endpoint (first-run setup), CSRF not needed
def setup():
    """Create a user account with automatic superadmin role assignment if none exists.

    SECURITY REQUIREMENT: SMTP configuration is mandatory before creating the superadmin account.
    This ensures that email verification can be sent to the superadmin.

    Request body:
        {
            "email": "admin@example.com",
            "password": "securepassword",
            "encrypted_vaultspace_key": "encrypted-key" (optional, if provided will be stored)
        }

    Returns:
        JSON with user info and email verification requirement.
        Returns 400 error if SMTP is not configured or if email sending fails.

    Raises:
        400: If SMTP is not configured or email sending fails
        500: If account creation fails
    """

    # Rate limiting: 5 attempts per minute per IP
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="auth_setup",
            user_id=None,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    encrypted_vaultspace_key = data.get("encrypted_vaultspace_key", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    # Validate email domain against domain rules
    from vault.services.domain_service import DomainService

    domain_service = DomainService()
    is_allowed, error_message = domain_service.validate_email_domain(email)
    if not is_allowed:
        return jsonify({"error": error_message or "Domain not allowed"}), 403

    # SECURITY: SMTP configuration is mandatory before creating the superadmin account
    # This ensures email verification can be sent to the superadmin.
    # Without SMTP, the superadmin account cannot be created.
    settings = current_app.config.get("VAULT_SETTINGS")
    if (
        not settings
        or not hasattr(settings, "smtp_config")
        or settings.smtp_config is None
    ):
        return (
            jsonify(
                {
                    "error": "SMTP configuration is required before creating the superadmin account. Please configure SMTP settings in your .env file and restart the application."
                }
            ),
            400,
        )

    auth_service = _get_auth_service()
    vaultspace_service = VaultSpaceService()

    # Determine role: superadmin if none exists, otherwise user
    superadmin_count = auth_service.count_superadmins()
    user_role = GlobalRole.SUPERADMIN if superadmin_count == 0 else GlobalRole.USER

    try:
        # Create user
        user = auth_service.create_user(email, password, user_role)

        # Send verification email (always required)
        from vault.services.email_verification_service import EmailVerificationService

        email_verification_service = EmailVerificationService()
        email_sent = email_verification_service.send_verification_email(
            user_id=user.id,
            base_url=None,
        )

        # Verify that email was sent successfully
        if not email_sent:
            # Rollback user creation if email sending failed
            from vault.database.schema import db

            db.session.delete(user)
            db.session.commit()
            return (
                jsonify(
                    {
                        "error": "Failed to send verification email. Please check your SMTP configuration and try again."
                    }
                ),
                500,
            )

        # Create Personal VaultSpace automatically
        personal_vaultspace = vaultspace_service.create_vaultspace(
            name="My Drive",
            owner_user_id=user.id,
            encrypted_metadata=None,
        )

        if encrypted_vaultspace_key:
            from vault.services.encryption_service import EncryptionService

            encryption_service = EncryptionService()
            try:
                encryption_service.create_vaultspace_key_entry(
                    vaultspace_id=personal_vaultspace.id,
                    user_id=user.id,
                    encrypted_key=encrypted_vaultspace_key,
                )
            except ValueError as e:
                current_app.logger.debug(f"Failed to store VaultSpace key: {e}")

        # Return email_verification_required to show verification modal in frontend
        return (
            jsonify(
                {
                    "user": user.to_dict(include_salt=False),
                    "email_verification_required": True,
                    "message": "Account created successfully. A verification email has been sent to your email address.",
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Setup error: {e}")
        return jsonify({"error": "Failed to create account"}), 500


@auth_api_bp.route("/account/email", methods=["PUT"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
def update_email():
    """Update user email.

    Request headers:
        Authorization: Bearer <token>

    Request body:
        {
            "email": "newemail@example.com",
            "password": "current_password"
        }

    Returns:
        JSON with updated user info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    new_email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not new_email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not validate_email(new_email):
        return jsonify({"error": "Invalid email format"}), 400

    auth_service = _get_auth_service()

    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    client_ip = get_client_ip() or "unknown"
    if rate_limiter:
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="account_email_update",
            user_id=user.id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    # Verify current password
    result = auth_service.authenticate(user.email, password)
    if not result:
        return (
            jsonify({"error_code": "invalid_password", "error": "Invalid password"}),
            403,
        )

    try:
        # Update email
        updated_user = auth_service.update_user(user.id, email=new_email)
        if not updated_user:
            return jsonify({"error": "Failed to update email"}), 500

        return (
            jsonify(
                {
                    "user": updated_user.to_dict(),
                    "message": "Email updated successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating email: {e}")
        return jsonify({"error": "Failed to update email"}), 500


@auth_api_bp.route("/account/master-key-salt", methods=["GET"])
@jwt_required
def get_master_key_salt():
    """Get master key salt for current user.

    This endpoint is used by SSO users to retrieve their salt
    so they can derive their master key from their password.

    Request headers:
        Authorization: Bearer <token>

    Returns:
        JSON with master_key_salt
    """
    user = get_current_user()
    if not user:
        current_app.logger.warning(
            "get_master_key_salt: User not found in g.current_user"
        )
        return jsonify({"error": "User not found"}), 404

    if not user.master_key_salt:
        current_app.logger.warning(
            f"get_master_key_salt: Master key salt not available for user {user.id}"
        )
        return (
            jsonify(
                {
                    "error": "Master key salt not available. Please contact your administrator."
                }
            ),
            404,
        )

    return jsonify({"master_key_salt": user.master_key_salt}), 200


@auth_api_bp.route("/account/keys", methods=["GET"])
@jwt_required
def get_account_keys():
    """Get all encrypted VaultSpace keys for the current user.

    Returns:
        JSON with list of keys
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    auth_service = _get_auth_service()
    keys = auth_service.get_user_vaultspace_keys(user.id)

    return jsonify({"keys": keys}), 200


@auth_api_bp.route("/encryption/unlock-attempt", methods=["POST"])
@jwt_required
def encryption_unlock_attempt():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    client_ip = get_client_ip() or "unknown"
    if rate_limiter:
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="encryption_unlock",
            user_id=user.id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )
    return jsonify({"success": True}), 200


@auth_api_bp.route("/account/password", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
def change_password():
    """Change user password.

    Request headers:
        Authorization: Bearer <token>

    Request body:
        {
            "current_password": "old_password",
            "new_password": "new_secure_password",
            "reencrypted_keys": [
                {"vaultspace_id": "...", "encrypted_key": "..."}
            ]
        }

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()
    reencrypted_keys = data.get("reencrypted_keys")

    if not current_password or not new_password:
        return jsonify({"error": "Current password and new password are required"}), 400

    auth_service = _get_auth_service()

    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    client_ip = get_client_ip() or "unknown"
    if rate_limiter:
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="account_password_change",
            user_id=user.id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    # Verify current password
    result = auth_service.authenticate(user.email, current_password)
    if not result:
        return (
            jsonify({"error_code": "invalid_password", "error": "Invalid password"}),
            403,
        )

    try:
        # Update password
        updated_user = auth_service.update_user(
            user.id, password=new_password, reencrypted_keys=reencrypted_keys
        )
        if not updated_user:
            return jsonify({"error": "Failed to update password"}), 500

        return (
            jsonify(
                {
                    "message": "Password updated successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating password: {e}")
        return jsonify({"error": "Failed to update password"}), 500


@auth_api_bp.route("/account", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
def delete_account():
    """Delete user account (soft delete).

    Request headers:
        Authorization: Bearer <token>

    Request body:
        {
            "password": "user_password"
        }

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    password = data.get("password", "").strip()

    if not password:
        return jsonify({"error": "Password is required"}), 400

    auth_service = _get_auth_service()

    # Verify password
    result = auth_service.authenticate(user.email, password)
    if not result:
        return (
            jsonify({"error_code": "invalid_password", "error": "Invalid password"}),
            403,
        )

    try:
        # Delete account (soft delete)
        success = auth_service.delete_user(user.id)
        if not success:
            return jsonify({"error": "Failed to delete account"}), 500

        return (
            jsonify(
                {
                    "message": "Account deleted successfully",
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"Error deleting account: {e}")
        return jsonify({"error": "Failed to delete account"}), 500


@auth_api_bp.route("/account/verify/<token>", methods=["GET", "POST"])
@csrf.exempt  # Public endpoint
def verify_email(token: str):
    """Verify email address using verification token.

    Supports both authenticated and unauthenticated users.
    If user is authenticated, verifies that token belongs to them.

    Args:
        token: Verification token

    Returns:
        JSON with verification status and user_was_logged_in flag
    """
    from vault.services.email_verification_service import EmailVerificationService
    from vault.database.schema import EmailVerificationToken, db
    from vault.services.auth_service import AuthService

    email_verification_service = EmailVerificationService()

    # Check if user is authenticated (optional JWT)
    current_user = None
    user_was_logged_in = False
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                jwt_token = parts[1]
                secret_key = current_app.config.get("SECRET_KEY")
                if secret_key:
                    settings = _settings()
                    auth_service = AuthService(
                        secret_key, jwt_expiration_hours=settings.jwt_expiration_hours
                    )
                    current_user = auth_service.verify_token(jwt_token)
                    if current_user:
                        user_was_logged_in = True
        except Exception:

            pass

    if request.method == "POST":
        # Verify using token, with optional user validation
        expected_user_id = current_user.id if current_user else None
        success, user, error_message = email_verification_service.verify_token(
            token, expected_user_id=expected_user_id
        )
        if success:
            # Do NOT return a token - user must log in after email verification
            # This ensures master key initialization happens during login
            # Exception: If user is already logged in, they stay logged in
            return (
                jsonify(
                    {
                        "message": "Email verified successfully",
                        "user": user.to_dict(),
                        "user_was_logged_in": user_was_logged_in,
                    }
                ),
                200,
            )
        else:

            if user_was_logged_in and expected_user_id:
                return jsonify({"error": error_message or "Invalid token"}), 403
            return jsonify({"error": error_message or "Invalid token"}), 400
    else:
        # GET - return verification status
        verification_token = (
            db.session.query(EmailVerificationToken).filter_by(token=token).first()
        )
        if not verification_token:
            return jsonify({"error": "Invalid token"}), 404

        if verification_token.is_used():
            return jsonify({"error": "Token already used"}), 400

        if verification_token.is_expired():
            return jsonify({"error": "Token expired"}), 400

        if current_user and verification_token.user_id != current_user.id:
            return (
                jsonify({"error": "Token does not belong to the authenticated user"}),
                403,
            )

        from vault.database.schema import User

        user = db.session.query(User).filter_by(id=verification_token.user_id).first()
        return (
            jsonify(
                {
                    "message": "Valid token",
                    "email": user.email if user else None,
                    "user_was_logged_in": user_was_logged_in,
                }
            ),
            200,
        )


@auth_api_bp.route("/account/resend-verification", methods=["POST"])
@csrf.exempt  # Public endpoint
def resend_verification_email():
    """Resend verification email to user.

    Request body:
        {
            "user_id": "user-uuid" (optional if email provided)
            "email": "user@example.com" (optional if user_id provided)
        }

    Returns:
        JSON with success message and user_id
    """
    from vault.services.email_verification_service import EmailVerificationService
    from vault.database.schema import User, db
    from vault.blueprints.validators import validate_email

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    user_id = data.get("user_id", "").strip()
    email = data.get("email", "").strip()

    # Require either user_id or email
    if not user_id and not email:
        return jsonify({"error": "Either user_id or email is required"}), 400

    # SECURITY: Always return the same response to prevent account enumeration
    # Log server-side for audit purposes
    user = None
    email_sent = False

    try:
        # Find user by user_id or email
        if user_id:
            user = db.session.query(User).filter_by(id=user_id).first()
        elif email:
            if not validate_email(email):
                # Invalid email format - return uniform response
                current_app.logger.info(
                    f"Resend verification attempt with invalid email format: {email[:10]}..."
                )
                return (
                    jsonify({"message": "A verification email has been sent"}),
                    200,
                )
            user = db.session.query(User).filter_by(email=email).first()

        # Only send email if user exists and is not verified
        if user and not user.email_verified:
            email_verification_service = EmailVerificationService()
            # VAULT_URL from settings will be used automatically
            email_sent = email_verification_service.send_verification_email(
                user_id=user.id,
                base_url=None,  # Will use VAULT_URL from settings
            )
            if email_sent:
                current_app.logger.info(
                    f"Verification email sent successfully for user_id: {user.id}"
                )
            else:
                current_app.logger.warning(
                    f"Failed to send verification email for user_id: {user.id}"
                )
        elif user and user.email_verified:
            current_app.logger.info(
                f"Resend verification attempt for already verified user_id: {user.id}"
            )
        else:
            # User not found - log but don't reveal
            current_app.logger.info(
                f"Resend verification attempt for non-existent user: "
                f"{'user_id=' + user_id[:10] + '...' if user_id else 'email=' + email[:10] + '...'}"
            )
    except Exception as e:
        # Log error but still return uniform response
        current_app.logger.error(f"Error in resend_verification_email: {e}")

    # SECURITY: Always return the same message to prevent account enumeration
    return (
        jsonify({"message": "A verification email has been sent"}),
        200,
    )


@auth_api_bp.route("/invitations/accept/<token>", methods=["GET", "POST"])
@csrf.exempt  # Public endpoint
def accept_invitation(token: str):
    """Accept an invitation and create user account.

    GET: Get invitation details
    POST: Accept invitation and set password

    Args:
        token: Invitation token

    Returns:
        JSON with invitation details (GET) or user info (POST)
    """
    from vault.services.invitation_service import InvitationService

    invitation_service = InvitationService()

    if request.method == "GET":
        # Return invitation details
        invitation = invitation_service.get_invitation(token)
        if not invitation:
            return jsonify({"error": "Invitation not found"}), 404

        if invitation.is_accepted():
            return jsonify({"error": "Invitation already accepted"}), 400

        if invitation.is_expired():
            return jsonify({"error": "Invitation expired"}), 400

        return jsonify(invitation.to_dict()), 200

    else:
        # POST - Accept invitation
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        password = data.get("password", "").strip()
        if not password:
            return jsonify({"error": "Password is required"}), 400

        user, error_message = invitation_service.accept_invitation(token, password)
        if user:

            # They will need to verify email after first login
            # For now, we mark email as verified since admin invited them
            # Actually, no - email verification is always required

            return (
                jsonify(
                    {
                        "message": "Account created successfully. Please verify your email.",
                        "user": user.to_dict(),
                        "email_verification_required": True,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify({"error": error_message or "Failed to accept invitation"}),
                400,
            )


@auth_api_bp.route("/captcha-image", methods=["GET"])
@csrf.exempt  # Public endpoint
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
            # Log for debugging - this should not happen frequently
            current_app.logger.debug(
                f"CAPTCHA nonce not found: {nonce_param[:8]}... "
                f"(store size: {len(_get_captcha_store()._store)})"
            )
            from flask import abort

            abort(404, description="CAPTCHA not found or expired")
    else:
        # No nonce provided - generate new CAPTCHA
        nonce_param = _refresh_captcha()
        text = _get_captcha_from_store(nonce_param)
        new_captcha_generated = True

    # Ensure we have valid text
    if not text:
        # This should never happen, but handle gracefully
        current_app.logger.error("Failed to get CAPTCHA text")
        from flask import abort

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


@auth_api_bp.route("/captcha-refresh", methods=["POST"])
@csrf.exempt  # Public endpoint
def captcha_refresh():
    """Refresh CAPTCHA and get new nonce and image URL.

    Always generates a fresh, valid CAPTCHA. Drops any existing CAPTCHA
    associated with the request to ensure no stale entries.

    Request headers (optional):
        X-Login-CSRF: Login CSRF token

    Returns:
        JSON with nonce and image_url
    """
    # CSRF token is optional for captcha refresh (public endpoint before login)

    submitted_login_csrf = (
        request.headers.get("X-Login-CSRF", "").strip()
        or request.form.get("login_csrf_token", "").strip()
    )
    # Only validate CSRF if provided (for compatibility with orchestrator)
    # For API usage, CSRF is not required
    if submitted_login_csrf:
        if not _touch_login_csrf_token(submitted_login_csrf):
            from flask import abort

            abort(400, description="Invalid or expired login session.")

    # Always generate a fresh CAPTCHA (drop any existing one from query params if present)
    old_nonce = request.args.get("nonce", "").strip()
    if old_nonce:
        _drop_captcha_from_store(old_nonce)

    # Generate new CAPTCHA and verify it was stored correctly
    nonce = _refresh_captcha()

    # Verify the CAPTCHA was stored successfully
    stored_text = _get_captcha_from_store(nonce)
    if not stored_text:
        # This should never happen, but handle it gracefully
        current_app.logger.error("Generated CAPTCHA nonce but store lookup failed")
        # Retry once
        nonce = _refresh_captcha()
        stored_text = _get_captcha_from_store(nonce)
        if not stored_text:
            from flask import abort

            abort(500, description="Failed to generate valid CAPTCHA")

    image_url = url_for("auth_api.captcha_image", nonce=nonce)
    response = jsonify({"nonce": nonce, "image_url": image_url})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


# ========== Two-Factor Authentication (2FA/TOTP) Endpoints ==========


@auth_api_bp.route("/2fa/status", methods=["GET"])
@jwt_required
def get_2fa_status():
    """Get user's 2FA status.

    Returns:
        JSON with enabled status and setup date (if applicable)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    return jsonify(
        {
            "enabled": user.totp_enabled,
            "enabled_at": (
                user.totp_enabled_at.isoformat() if user.totp_enabled_at else None
            ),
        }
    )


@auth_api_bp.route("/2fa/setup", methods=["POST"])
@jwt_required
def setup_2fa():
    """Generate TOTP secret and QR code for 2FA setup.

    Returns:
        JSON with secret, provisioning_uri, and qr_code (base64 PNG)
    """
    from vault.services.totp_service import get_totp_service

    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    # Check if 2FA is already enabled
    if user.totp_enabled:
        return jsonify({"error": "Two-factor authentication is already enabled"}), 400

    totp_service = get_totp_service()

    # Generate new TOTP secret
    secret = totp_service.generate_secret()

    # Generate provisioning URI for QR code
    provisioning_uri = totp_service.generate_provisioning_uri(
        secret=secret, email=user.email, issuer="Leyzen Vault"
    )

    # Generate QR code
    qr_code = totp_service.generate_qr_code(provisioning_uri)

    # Store secret temporarily in session (will be saved after verification)
    session["totp_setup_secret"] = secret
    session.modified = True

    return jsonify(
        {"secret": secret, "provisioning_uri": provisioning_uri, "qr_code": qr_code}
    )


@auth_api_bp.route("/2fa/verify-setup", methods=["POST"])
@jwt_required
def verify_2fa_setup():
    """Verify TOTP token and enable 2FA.

    Request JSON:
        token: 6-digit TOTP token

    Returns:
        JSON with success status and backup codes
    """
    from vault.services.totp_service import get_totp_service

    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    # Check if 2FA is already enabled
    if user.totp_enabled:
        return jsonify({"error": "Two-factor authentication is already enabled"}), 400

    # Get secret from session
    secret = session.get("totp_setup_secret")
    if not secret:
        return (
            jsonify({"error": "No setup in progress. Please start 2FA setup first"}),
            400,
        )

    # Get token from request
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    token = data.get("token", "").strip()
    if not token:
        return jsonify({"error": "Missing token"}), 400

    totp_service = get_totp_service()

    # Verify token
    if not totp_service.verify_token(secret, token):
        return jsonify({"error": "Invalid token. Please try again"}), 400

    # Token is valid - enable 2FA
    # Generate backup codes
    backup_codes = totp_service.generate_backup_codes(count=10)
    hashed_codes = [totp_service.hash_backup_code(code) for code in backup_codes]

    # Encrypt secret and backup codes
    encrypted_secret = totp_service.encrypt_secret(secret)
    encrypted_backup_codes = totp_service.encrypt_backup_codes(hashed_codes)

    # Enable 2FA for user
    auth_service = _get_auth_service()
    auth_service.enable_totp(user.id, encrypted_secret, encrypted_backup_codes)

    # Clear session
    session.pop("totp_setup_secret", None)
    session.modified = True

    return jsonify(
        {
            "success": True,
            "message": "Two-factor authentication enabled successfully",
            "backup_codes": backup_codes,
        }
    )


@auth_api_bp.route("/2fa/disable", methods=["POST"])
@jwt_required
def disable_2fa():
    """Disable 2FA for the current user.

    Request JSON:
        password: User's password (for confirmation)

    Returns:
        JSON with success status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    # Check if 2FA is enabled
    if not user.totp_enabled:
        return jsonify({"error": "Two-factor authentication is not enabled"}), 400

    # Verify password for security
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    password = data.get("password", "").strip()
    if not password:
        return jsonify({"error": "Password required to disable 2FA"}), 400

    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    client_ip = get_client_ip() or "unknown"
    if rate_limiter:
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="2fa_disable",
            user_id=user.id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    # Verify password
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user.email, password)
    if not result:
        return (
            jsonify({"error_code": "invalid_password", "error": "Invalid password"}),
            403,
        )

    # Disable 2FA
    auth_service.disable_totp(user.id)

    return jsonify(
        {"success": True, "message": "Two-factor authentication disabled successfully"}
    )


@auth_api_bp.route("/2fa/regenerate-backup", methods=["POST"])
@jwt_required
def regenerate_backup_codes():
    """Regenerate backup recovery codes.

    Request JSON:
        password: User's password (for confirmation)

    Returns:
        JSON with new backup codes
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    # Check if 2FA is enabled
    if not user.totp_enabled:
        return jsonify({"error": "Two-factor authentication is not enabled"}), 400

    # Verify password for security
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    password = data.get("password", "").strip()
    if not password:
        return jsonify({"error": "Password required to regenerate backup codes"}), 400

    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    client_ip = get_client_ip() or "unknown"
    if rate_limiter:
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=60,
            action_name="2fa_regenerate_backup",
            user_id=user.id,
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

    # Verify password
    auth_service = _get_auth_service()
    result = auth_service.authenticate(user.email, password)
    if not result:
        return (
            jsonify({"error_code": "invalid_password", "error": "Invalid password"}),
            403,
        )

    # Regenerate backup codes
    new_codes = auth_service.regenerate_backup_codes(user.id)
    if not new_codes:
        return jsonify({"error": "Failed to regenerate backup codes"}), 500

    return jsonify({"success": True, "backup_codes": new_codes})
