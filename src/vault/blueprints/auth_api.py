"""Authentication API routes for Leyzen Vault."""

from __future__ import annotations

import secrets
from threading import Lock

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    request,
    session,
    url_for,
)

from vault.config import is_setup_complete
from vault.database.schema import GlobalRole
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.auth_service import AuthService
from vault.services.rate_limiter import RateLimiter
from vault.services.vaultspace_service import VaultSpaceService
from vault.blueprints.validators import validate_email
from vault.blueprints.utils import _settings
from common.captcha_helpers import (
    build_captcha_image_with_settings,
    get_captcha_store_for_app,
    get_login_csrf_store_for_app,
    refresh_captcha_with_store,
)
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
    return AuthService(secret_key)


@auth_api_bp.route("/signup/status", methods=["GET"])
@csrf.exempt  # Public endpoint
def signup_status():
    """Check if public signup is enabled.

    Returns:
        JSON with allow_signup status
    """
    from vault.database.schema import SystemSettings, db

    # First, try to get from database (takes precedence over config)
    setting = db.session.query(SystemSettings).filter_by(key="allow_signup").first()
    if setting:
        # Convert string to boolean
        allow_signup = setting.value.lower() == "true"
    else:
        # Fallback to config
        vault_settings = current_app.config.get("VAULT_SETTINGS")
        allow_signup = vault_settings.allow_signup if vault_settings else True

    return jsonify({"allow_signup": allow_signup}), 200


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
    from vault.blueprints.utils import get_client_ip

    # Rate limiting: 5 attempts per minute per IP
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip, max_attempts=5, window_seconds=60, action_name="auth_signup"
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

    # Check if signup is allowed (check database first, then config)
    from vault.database.schema import SystemSettings, db

    setting = db.session.query(SystemSettings).filter_by(key="allow_signup").first()
    if setting:
        # Convert string to boolean
        allow_signup = setting.value.lower() == "true"
    else:
        # Fallback to config
        vault_settings = current_app.config.get("VAULT_SETTINGS")
        allow_signup = vault_settings.allow_signup if vault_settings else True

    if not allow_signup:
        return (
            jsonify(
                {
                    "error": "Public registration is disabled. Contact an administrator for an invitation."
                }
            ),
            403,
        )

    # Validate email domain against SSO rules
    from vault.services.sso_domain_service import SSODomainService

    sso_domain_service = SSODomainService()
    is_allowed, error_message = sso_domain_service.validate_email_domain(email)
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

        # If encrypted VaultSpace key is provided, store it
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
                current_app.logger.warning(f"Failed to store VaultSpace key: {e}")

        # Note: User cannot login until email is verified
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
        from vault.blueprints.auth import register_failed_attempt
        from vault.blueprints.utils import _settings, get_client_ip
        from common.captcha_helpers import (
            get_captcha_store_for_app,
        )

        # Rate limiting: 5 attempts per minute per IP
        rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
        if rate_limiter:
            client_ip = get_client_ip() or "unknown"
            is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
                client_ip, max_attempts=5, window_seconds=60, action_name="auth_login"
            )
            if not is_allowed:
                return (
                    jsonify(
                        {
                            "error": error_msg
                            or "Too many attempts. Please try again later."
                        }
                    ),
                    429,
                )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        username_or_email = (
            data.get("email", "").strip() or data.get("username", "").strip()
        )
        password = data.get("password", "").strip()
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
        settings = _settings()
        captcha_store = get_captcha_store_for_app(settings)

        # CAPTCHA is REQUIRED for login (security requirement)
        if not captcha_response:
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

        # Verify CAPTCHA response
        expected_captcha = None
        # Try to get captcha from store if nonce provided
        if captcha_nonce:
            expected_captcha = captcha_store.get(captcha_nonce)
            # SECURITY: Never log CAPTCHA values or nonces in production
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                # Only log lookup status in development, never actual values
                current_app.logger.debug(
                    f"CAPTCHA lookup by nonce: found={expected_captcha is not None}"
                )

        # Fallback to session-based captcha (preferred for API)
        if not expected_captcha:
            session_text = session.get("captcha_text")
            session_nonce = session.get("captcha_nonce")
            if session_text:
                expected_captcha = str(session_text)
                # If nonce was provided, verify it matches session
                if captcha_nonce and session_nonce and session_nonce != captcha_nonce:
                    # Nonce mismatch - the provided nonce doesn't match session nonce
                    # This might happen if multiple CAPTCHAs were generated
                    # SECURITY: Never log nonce values in production
                    is_production = current_app.config.get("IS_PRODUCTION", True)
                    if not is_production:
                        # Only log mismatch status in development, never actual nonce values
                        current_app.logger.debug(
                            f"CAPTCHA nonce mismatch: using session CAPTCHA anyway"
                        )
                    # Still use session CAPTCHA even if nonce doesn't match
                    # (nonce is optional for session-based verification)
                elif captcha_nonce and not session_nonce:
                    # Nonce provided but no session nonce - this is OK, use session text
                    pass

        # Validate CAPTCHA response
        if not expected_captcha:
            client_ip = get_client_ip()
            register_failed_attempt(client_ip)
            # CAPTCHA not found in store or session
            # SECURITY: Never log CAPTCHA details in production
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                # Only log status in development, never actual values
                current_app.logger.debug(
                    f"CAPTCHA not found: session has captcha_text={session.get('captcha_text') is not None}, "
                    f"session has captcha_nonce={session.get('captcha_nonce') is not None}"
                )
            return (
                jsonify(
                    {
                        "error": "CAPTCHA session expired. Please refresh the page and try again."
                    }
                ),
                400,
            )

        # Normalize both for comparison (uppercase, strip whitespace)
        expected_normalized = str(expected_captcha).strip().upper()
        received_normalized = captcha_response.strip().upper()

        if received_normalized != expected_normalized:
            client_ip = get_client_ip()
            register_failed_attempt(client_ip)
            if captcha_nonce:
                captcha_store.drop(captcha_nonce)
            # SECURITY: Never log CAPTCHA values in production
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                # Only log mismatch status in development, never actual CAPTCHA values
                current_app.logger.debug(
                    f"CAPTCHA mismatch: expected_len={len(expected_normalized)}, "
                    f"received_len={len(received_normalized)}"
                )
            return jsonify({"error": "Invalid captcha response"}), 400

        # Clean up captcha after successful verification
        if captcha_nonce:
            captcha_store.drop(captcha_nonce)
        session.pop("captcha_nonce", None)
        session.pop("captcha_text", None)

        auth_service = _get_auth_service()
        try:
            result = auth_service.authenticate(username_or_email, password)
        except ValueError as e:
            # Email not verified error
            return jsonify({"error": str(e)}), 403

        if not result:
            client_ip = get_client_ip()
            register_failed_attempt(client_ip)
            return jsonify({"error": "Invalid credentials"}), 401

        user, token = result

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

    Returns:
        JSON with user info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    return (
        jsonify(
            {
                "user": user.to_dict(),
            }
        ),
        200,
    )


@auth_api_bp.route("/logout", methods=["POST"])
@jwt_required
def logout():
    """Logout user (client should discard token).

    Request headers:
        Authorization: Bearer <token>

    Returns:
        JSON with success message
    """
    # Get token from Authorization header and blacklist it
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
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
            current_app.logger.warning(f"Failed to blacklist token: {type(e).__name__}")

    return jsonify({"message": "Logged out successfully"}), 200


@auth_api_bp.route("/setup/status", methods=["GET"])
def setup_status():
    """Check if setup is complete.

    Returns:
        JSON with is_setup_complete boolean
    """
    try:
        setup_complete = is_setup_complete(current_app)
        return jsonify({"is_setup_complete": setup_complete}), 200
    except Exception as e:
        current_app.logger.error(f"Error checking setup status: {e}")
        return jsonify({"error": "Failed to check setup status"}), 500


@auth_api_bp.route("/setup", methods=["POST"])
@csrf.exempt  # Public endpoint (first-run setup), CSRF not needed
def setup():
    """Create the initial superadmin account (first-run setup).

    This endpoint is only available when no users exist in the database.
    After the first user is created, this endpoint returns 403.

    Request body:
        {
            "email": "admin@example.com",
            "password": "securepassword",
            "confirm_password": "securepassword",
            "display_name": "Admin" (optional)
        }

    Returns:
        JSON with user info and JWT token
    """
    # Check if setup is already complete
    try:
        if is_setup_complete(current_app):
            return jsonify({"error": "Setup already complete"}), 403
    except Exception as e:
        current_app.logger.error(f"Error checking setup status: {e}")
        return jsonify({"error": "Failed to check setup status"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    confirm_password = data.get("confirm_password", "").strip()

    if not email or not password or not confirm_password:
        return (
            jsonify({"error": "Email, password, and confirm_password are required"}),
            400,
        )

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    # Validate password match
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    # Validate password strength using centralized validator
    from vault.utils.password_validator import validate_password_strength

    is_valid, error_message = validate_password_strength(password)
    if not is_valid:
        return jsonify({"error": error_message or "Invalid password"}), 400

    auth_service = _get_auth_service()

    try:
        # Create superadmin user
        user = auth_service.create_user(email, password, GlobalRole.SUPERADMIN)
        token = auth_service._generate_token(user)

        current_app.logger.info(
            f"Setup completed: superadmin user created with email {email}"
        )

        return (
            jsonify(
                {
                    "user": user.to_dict(),
                    "token": token,
                    "message": "Superadmin account created successfully",
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Setup error: {e}")
        return jsonify({"error": "Failed to create superadmin account"}), 500


@auth_api_bp.route("/account/email", methods=["PUT"])
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

    # Verify current password
    result = auth_service.authenticate(user.email, password)
    if not result:
        return jsonify({"error": "Invalid password"}), 401

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


@auth_api_bp.route("/account/password", methods=["POST"])
@jwt_required
def change_password():
    """Change user password.

    Request headers:
        Authorization: Bearer <token>

    Request body:
        {
            "current_password": "old_password",
            "new_password": "new_secure_password"
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

    if not current_password or not new_password:
        return jsonify({"error": "Current password and new password are required"}), 400

    auth_service = _get_auth_service()

    # Verify current password
    result = auth_service.authenticate(user.email, current_password)
    if not result:
        return jsonify({"error": "Invalid current password"}), 401

    try:
        # Update password
        updated_user = auth_service.update_user(user.id, password=new_password)
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
        return jsonify({"error": "Invalid password"}), 401

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

    Args:
        token: Verification token

    Returns:
        JSON with verification status
    """
    from vault.services.email_verification_service import EmailVerificationService
    from vault.database.schema import EmailVerificationToken, db

    email_verification_service = EmailVerificationService()

    if request.method == "POST":
        # Verify using token
        success, user, error_message = email_verification_service.verify_token(token)
        if success:
            # Generate token for immediate login
            auth_service = _get_auth_service()
            login_token = auth_service._generate_token(user)
            return (
                jsonify(
                    {
                        "message": "Email verified successfully",
                        "user": user.to_dict(),
                        "token": login_token,
                    }
                ),
                200,
            )
        else:
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

        from vault.database.schema import User

        user = db.session.query(User).filter_by(id=verification_token.user_id).first()
        return (
            jsonify({"message": "Valid token", "email": user.email if user else None}),
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

    # Find user by user_id or email
    user = None
    if user_id:
        user = db.session.query(User).filter_by(id=user_id).first()
    elif email:
        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400
        user = db.session.query(User).filter_by(email=email, is_active=True).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.email_verified:
        return jsonify({"error": "Email already verified"}), 400

    email_verification_service = EmailVerificationService()
    # VAULT_URL from settings will be used automatically
    success = email_verification_service.send_verification_email(
        user_id=user.id,  # Use user.id (found from user_id or email)
        base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
    )

    if success:
        return (
            jsonify(
                {
                    "message": "Verification email resent successfully",
                    "user_id": user.id,  # Return user_id in case it was requested by email
                }
            ),
            200,
        )
    else:
        return (
            jsonify(
                {
                    "error": "Failed to send verification email. Please check SMTP configuration.",
                }
            ),
            500,
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
            # Note: User email is not verified yet, but we allow login for invited users
            # They will need to verify email after first login
            # For now, we mark email as verified since admin invited them
            # Actually, no - email verification is always required
            # So we don't return token, user must verify email first
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
    """
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


@auth_api_bp.route("/captcha-refresh", methods=["POST"])
@csrf.exempt  # Public endpoint
def captcha_refresh():
    """Refresh CAPTCHA and get new nonce and image URL.

    Request headers (optional):
        X-Login-CSRF: Login CSRF token

    Returns:
        JSON with nonce and image_url
    """
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
            from flask import abort

            abort(400, description="Invalid or expired login session.")
    nonce = _refresh_captcha()
    image_url = url_for("auth_api.captcha_image", nonce=nonce)
    response = jsonify({"nonce": nonce, "image_url": image_url})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
