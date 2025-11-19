"""Authentication service for Leyzen Vault."""

from __future__ import annotations

import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from vault.database.schema import GlobalRole, JWTBlacklist, User, db
from vault.blueprints.validators import validate_email
from vault.utils.password_validator import validate_password_strength_raise
from vault.utils.constant_time import constant_time_compare


# Cache for jti column existence check (per process)
_jti_column_exists_cache = None


def _check_jti_column_exists() -> bool:
    """Check if jti column exists in jwt_blacklist table.

    Uses a cached result to avoid repeated database queries.
    Returns False if check fails (safe default - assumes column doesn't exist).
    This function NEVER raises exceptions - all errors are caught and return False.

    Returns:
        True if column exists, False otherwise
    """
    global _jti_column_exists_cache

    # Return cached result if available
    if _jti_column_exists_cache is not None:
        return _jti_column_exists_cache

    # Check if column exists - wrap everything in try/except to ensure no exceptions escape
    try:
        from sqlalchemy.exc import ProgrammingError, InternalError
        from sqlalchemy.sql import text as sql_text
        from flask import has_app_context

        # Only check if we're in Flask application context
        try:
            if not has_app_context():
                # Not in context - assume column doesn't exist (safe default)
                _jti_column_exists_cache = False
                return False
        except Exception:
            # If has_app_context() itself fails, assume no context
            _jti_column_exists_cache = False
            return False

        # Try a simple query that will fail if column doesn't exist
        # Use a very lightweight query that won't affect performance
        try:
            # Use a query that will fail gracefully if column doesn't exist
            result = db.session.execute(
                sql_text("SELECT jti FROM jwt_blacklist LIMIT 0")
            )
            # If query succeeds, column exists
            _jti_column_exists_cache = True
            return True
        except (ProgrammingError, InternalError) as e:
            # Check if error is about missing column
            error_str = str(e).lower()
            if (
                "column" in error_str and "jti" in error_str
            ) or "does not exist" in error_str:
                # Column doesn't exist
                _jti_column_exists_cache = False
                return False
            else:
                # Other database error - assume column doesn't exist (safe default)
                _jti_column_exists_cache = False
                return False
        except Exception:
            # Any other error - assume column doesn't exist (safe default)
            _jti_column_exists_cache = False
            return False
    except Exception:
        # Any error during check - assume column doesn't exist (safe default)
        # This outer catch ensures NO exceptions can escape this function
        _jti_column_exists_cache = False
        return False


class AuthService:
    """Service for user authentication and management."""

    def __init__(self, secret_key: str, jwt_expiration_hours: int = 1):
        """Initialize authentication service.

        Args:
            secret_key: Secret key for JWT signing
            jwt_expiration_hours: JWT token expiration time in hours (default: 1)
        """
        self.secret_key = secret_key
        self.jwt_expiration_hours = jwt_expiration_hours
        self.password_hasher = PasswordHasher()

    def create_user(
        self,
        email: str,
        password: str,
        global_role: GlobalRole = GlobalRole.USER,
    ) -> User:
        """Create a new user.

        Args:
            email: User email (must be unique)
            password: User password (will be hashed with Argon2)
            global_role: User global role

        Returns:
            Created User object

        Raises:
            ValueError: If email already exists or validation fails
        """
        # Validate email format
        if not validate_email(email):
            raise ValueError("Invalid email format")

        # Validate password strength using centralized validator
        validate_password_strength_raise(password)

        # Check if user already exists
        existing_user = db.session.query(User).filter_by(email=email).first()
        if existing_user:
            raise ValueError(f"User with email {email} already exists")

        # Hash password with Argon2
        password_hash = self.password_hasher.hash(password)

        # Generate master key salt (16 bytes, base64-encoded)
        # This salt will be used to derive the user's master key from their password
        # It must be persistent per user to ensure the same master key is derived each session
        salt_bytes = secrets.token_bytes(16)
        master_key_salt = base64.b64encode(salt_bytes).decode("utf-8")

        # Create user with email_verified=False (verification always required)
        user = User(
            email=email,
            password_hash=password_hash,
            global_role=global_role,
            master_key_salt=master_key_salt,
            email_verified=False,  # Email verification always required
        )
        db.session.add(user)
        db.session.commit()

        return user

    def authenticate(
        self, username_or_email: str, password: str
    ) -> tuple[User, str] | None:
        """Authenticate a user and return JWT token.

        Args:
            username_or_email: User email
            password: User password

        Returns:
            Tuple of (User, JWT token) if authentication succeeds, None otherwise

        Raises:
            ValueError: If email is not verified (with error message)
        """
        # Try to find user by email
        user = db.session.query(User).filter_by(email=username_or_email).first()

        # If user found in database, verify password
        if user:
            try:
                self.password_hasher.verify(user.password_hash, password)
            except VerifyMismatchError:
                return None

            # SECURITY: Check if email is verified (always required)
            # Exception: superadmin created during setup may not have verified email initially
            # but we allow them to login to complete setup
            if not user.email_verified and user.global_role != GlobalRole.SUPERADMIN:
                raise ValueError(
                    "Email not verified. Please verify your email before logging in."
                )

            # Update last login
            user.last_login = datetime.now(timezone.utc)

            # If user doesn't have a master_key_salt, generate one now
            # This handles initialization for users created before master_key_salt was required
            if not user.master_key_salt:
                salt_bytes = secrets.token_bytes(16)
                user.master_key_salt = base64.b64encode(salt_bytes).decode("utf-8")

            db.session.commit()

            # Generate JWT token
            token = self._generate_token(user)
            return user, token

        return None

    def verify_token(self, token: str) -> User | None:
        """Verify JWT token and return user.

        Args:
            token: JWT token string

        Returns:
            User object if token is valid, None otherwise
        """
        try:
            # Validate token format first (basic sanity check)
            if not token or not isinstance(token, str) or len(token) < 10:
                # Use constant-time comparison to prevent timing attacks
                # Compare against a dummy token to maintain constant time
                constant_time_compare(token or "", "dummy_token_for_timing_protection")
                return None

            # SECURITY: Check for token replay using jti (JWT ID) claim
            # First decode without verification to get jti, then verify
            jti = None
            try:
                unverified_payload = jwt.decode(
                    token, options={"verify_signature": False}
                )
                jti = unverified_payload.get("jti")
            except Exception:
                jti = None

            # Check if jti is blacklisted (replay protection)
            # Handle case where jti column might not exist yet (database migration pending)
            if jti:
                # Check if jti column exists before using it
                # _check_jti_column_exists() never raises exceptions, so this is safe
                try:
                    jti_column_exists = _check_jti_column_exists()
                    if jti_column_exists:
                        try:
                            blacklisted_jti = (
                                db.session.query(JWTBlacklist)
                                .filter_by(jti=jti)
                                .first()
                            )
                            if blacklisted_jti:
                                # Use constant-time comparison to prevent timing attacks
                                constant_time_compare(
                                    token, "dummy_token_for_timing_protection"
                                )
                                return None
                        except Exception:
                            # Database error during jti check - continue without jti validation
                            # This is expected if column doesn't exist or database is unavailable
                            pass
                except Exception:
                    # If _check_jti_column_exists() somehow raises (shouldn't happen), continue
                    pass

            # Check if token is blacklisted (full token match)
            # Protect database query to avoid ProgrammingError being logged as JWT error
            try:
                blacklisted = (
                    db.session.query(JWTBlacklist).filter_by(token=token).first()
                )
                if blacklisted:
                    # Use constant-time comparison to prevent timing attacks
                    constant_time_compare(token, "dummy_token_for_timing_protection")
                    return None
            except Exception:
                # Database error during blacklist check - continue with token verification
                # This is expected if table doesn't exist or database is unavailable
                pass

            # Decode and verify token with strict algorithm validation
            # CRITICAL: Always explicitly specify algorithms to prevent algorithm confusion attacks
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],  # Explicitly require HS256 only
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["exp", "iat", "user_id"],  # Require essential claims
                },
            )

            # Validate required claims
            user_id = payload.get("user_id")
            if not user_id or not isinstance(user_id, str):
                # Use constant-time comparison to prevent timing attacks
                constant_time_compare(str(user_id or ""), "dummy_user_id")
                return None

            # Validate token type (prevent misuse of other tokens)
            # Ensure token was issued by our service (has expected claims)
            if "email" not in payload or "global_role" not in payload:
                # Use constant-time comparison to prevent timing attacks
                constant_time_compare(str(user_id), "dummy_user_id")
                return None

            # Validate issuer claim if present (additional security check)
            # Tokens issued by our service should have iss="leyzen-vault"
            if "iss" in payload and not constant_time_compare(
                str(payload.get("iss", "")), "leyzen-vault"
            ):
                return None

            # Regular user lookup from database
            # Protect database query to avoid ProgrammingError being logged as JWT error
            try:
                user = db.session.query(User).filter_by(id=user_id).first()
                # Use constant-time comparison to prevent user enumeration via timing
                if not user:
                    constant_time_compare(str(user_id), "dummy_user_id")
                return user
            except Exception:
                # Database error during user lookup - token is valid but can't verify user
                # Return None to indicate authentication failure
                return None
        except jwt.InvalidTokenError:
            # Use constant-time comparison to prevent timing attacks
            constant_time_compare(token or "", "dummy_token_for_timing_protection")
            return None
        except Exception as e:
            # Log unexpected errors but don't expose details
            # Don't log database errors (ProgrammingError, InternalError) as JWT errors
            # These are already handled in the try blocks above
            from sqlalchemy.exc import ProgrammingError, InternalError

            if not isinstance(e, (ProgrammingError, InternalError)):
                # Only log non-database errors as JWT verification errors
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"JWT verification error: {type(e).__name__}")

            # Use constant-time comparison to prevent timing attacks
            constant_time_compare(token or "", "dummy_token_for_timing_protection")
            return None

    def refresh_token(self, token: str) -> tuple[User, str] | None:
        """Refresh JWT token.

        Args:
            token: Current JWT token

        Returns:
            Tuple of (User, new JWT token) if token is valid, None otherwise
        """
        user = self.verify_token(token)
        if not user:
            return None

        new_token = self._generate_token(user)
        return user, new_token

    def get_user(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object if found, None otherwise
        """
        return db.session.query(User).filter_by(id=user_id).first()

    def update_user(
        self,
        user_id: str,
        email: str | None = None,
        password: str | None = None,
        global_role: GlobalRole | None = None,
    ) -> User | None:
        """Update user information.

        Args:
            user_id: User ID
            email: New email (optional)
            password: New password (optional, will be hashed)
            global_role: New global role (optional)

        Returns:
            Updated User object if found, None otherwise
        """
        user = self.get_user(user_id)
        if not user:
            return None

        if email is not None:
            # Check if email is already taken by another user
            existing = db.session.query(User).filter_by(email=email).first()
            if existing and existing.id != user_id:
                raise ValueError(f"Email {email} is already taken")
            user.email = email

        if password is not None:
            # Validate password strength using centralized validator
            validate_password_strength_raise(password)

            user.password_hash = self.password_hasher.hash(password)

        if global_role is not None:
            user.global_role = global_role

        db.session.commit()
        return user

    def delete_user(self, user_id: str) -> bool:
        """Permanently delete a user and all associated data.

        Args:
            user_id: User ID

        Returns:
            True if user was deleted, False if not found
        """
        # Get user
        user = db.session.query(User).filter_by(id=user_id).first()

        if not user:
            return False

        # Permanently delete user and all associated data
        # First, delete all physical files owned by the user
        from vault.database.schema import File
        from flask import current_app
        from vault.services.thumbnail_service import ThumbnailService

        storage = current_app.config.get("VAULT_STORAGE")
        thumbnail_service = ThumbnailService(storage)

        # Get all files owned by this user (including deleted ones)
        user_files = db.session.query(File).filter_by(owner_user_id=user_id).all()

        for file_obj in user_files:
            # Delete physical file from storage
            if storage and file_obj.storage_ref:
                try:
                    # Delete main file
                    if file_obj.mime_type != "application/x-directory":
                        storage.delete_file(file_obj.storage_ref)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to delete file {file_obj.storage_ref} from storage: {e}"
                    )

            # Delete thumbnails
            try:
                thumbnail_service.delete_thumbnails(file_obj.id)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to delete thumbnails for file {file_obj.id}: {e}"
                )

        # Delete user from database
        # Cascades will automatically delete:
        # - VaultSpaces (owner_user_id)
        # - VaultSpaceKeys (user_id)
        # - Files (owner_user_id) - but we already handled physical deletion
        # - FileKeys (via Files)
        # - Permissions (user_id and granted_by)
        # - EmailVerificationTokens (user_id)
        # - UserInvitations (invited_by)
        # - Webhooks (user_id)
        # - Devices (user_id)
        # - Quotas (user_id)
        # - Workflows (user_id)
        # - BehaviorAnalytics (user_id)
        # - VaultSpaceTemplates (created_by)
        # - PublicShareLinks (created_by)
        # - ShareLinks (via Files)
        # - AuditLogEntry (via file_id, but file_id is SET NULL, so logs remain)

        db.session.delete(user)
        db.session.commit()

        return True

    def _generate_token(self, user: User) -> str:
        """Generate JWT token for user.

        Args:
            user: User object

        Returns:
            JWT token string
        """
        expiration = datetime.now(timezone.utc) + timedelta(
            hours=self.jwt_expiration_hours
        )
        issued_at = datetime.now(timezone.utc)

        # Generate unique JWT ID (jti) for replay protection
        jti = secrets.token_urlsafe(32)

        # Regular User payload with all required claims
        # CRITICAL: Always use HS256 algorithm explicitly
        payload = {
            "user_id": user.id,
            "email": user.email,
            "global_role": user.global_role.value,
            "exp": expiration,
            "iat": issued_at,
            "typ": "JWT",  # Token type claim
            "iss": "leyzen-vault",  # Issuer claim for additional validation
            "jti": jti,  # JWT ID for replay protection
        }

        # Encode with explicit algorithm specification
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def blacklist_token(self, token: str, expiration_time: datetime) -> None:
        """Add a JWT token to the blacklist.

        Args:
            token: JWT token string to blacklist
            expiration_time: Token expiration time (from JWT payload)
        """
        # Extract jti from token if present
        jti = None
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            jti = unverified_payload.get("jti")
        except Exception:
            pass

        # Check if token is already blacklisted
        existing = db.session.query(JWTBlacklist).filter_by(token=token).first()
        if existing:
            return

        # Check if jti is already blacklisted (handle case where column might not exist)
        if jti and _check_jti_column_exists():
            try:
                existing_jti = db.session.query(JWTBlacklist).filter_by(jti=jti).first()
                if existing_jti:
                    return
            except Exception as e:
                # Log error but continue
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(f"JTI check error (non-fatal): {type(e).__name__}")

        # Create blacklist entry
        # Handle case where jti column might not exist yet (database migration pending)
        # Use raw SQL to avoid SQLAlchemy model issues with missing columns
        from sqlalchemy.sql import text as sql_text

        jti_column_exists = _check_jti_column_exists()

        try:
            if jti_column_exists and jti:
                # Column exists, insert with jti
                db.session.execute(
                    sql_text(
                        "INSERT INTO jwt_blacklist (token, jti, expires_at, created_at) "
                        "VALUES (:token, :jti, :expires_at, NOW())"
                    ),
                    {"token": token, "jti": jti, "expires_at": expiration_time},
                )
            else:
                # Column doesn't exist or jti is None, insert without jti
                db.session.execute(
                    sql_text(
                        "INSERT INTO jwt_blacklist (token, expires_at, created_at) "
                        "VALUES (:token, :expires_at, NOW())"
                    ),
                    {"token": token, "expires_at": expiration_time},
                )
            db.session.commit()
        except Exception as e:
            # Fallback: try without jti if first attempt failed
            db.session.rollback()
            try:
                db.session.execute(
                    sql_text(
                        "INSERT INTO jwt_blacklist (token, expires_at, created_at) "
                        "VALUES (:token, :expires_at, NOW())"
                    ),
                    {"token": token, "expires_at": expiration_time},
                )
                db.session.commit()
            except Exception as e2:
                # If that also fails, log and re-raise
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create blacklist entry: {e2}")
                raise

        # Clean up expired tokens (older than 24 hours past expiration)
        cleanup_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        db.session.query(JWTBlacklist).filter(
            JWTBlacklist.expires_at < cleanup_threshold
        ).delete(synchronize_session=False)
        db.session.commit()

    def count_superadmins(self) -> int:
        """Count the number of superadmin users.

        Returns:
            Number of superadmin users
        """
        return (
            db.session.query(User).filter_by(global_role=GlobalRole.SUPERADMIN).count()
        )

    def get_superadmins(self) -> list[User]:
        """Get all superadmin users.

        Returns:
            List of superadmin users
        """
        return db.session.query(User).filter_by(global_role=GlobalRole.SUPERADMIN).all()
