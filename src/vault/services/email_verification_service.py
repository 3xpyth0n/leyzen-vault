"""Email verification service for verifying user email addresses."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app, url_for

from vault.database.schema import EmailVerificationToken, User, db
from vault.services.email_service import EmailService


class EmailVerificationService:
    """Service for managing email verification."""

    def __init__(self, email_service: EmailService | None = None):
        """Initialize email verification service.

        Args:
            email_service: Email service instance. If None, will create a new one.
        """
        self.email_service = email_service or EmailService()

    def generate_verification_token(self) -> str:
        """Generate a secure verification token.

        Returns:
            Verification token string
        """
        return secrets.token_urlsafe(32)

    def create_verification_token(
        self,
        user_id: str,
        expires_in_minutes: int | None = None,
    ) -> EmailVerificationToken:
        """Create a new email verification token for a user.

        Args:
            user_id: User ID
            expires_in_minutes: Expiration time in minutes. If None, uses EMAIL_VERIFICATION_EXPIRY_MINUTES from config (default: 10)

        Returns:
            EmailVerificationToken object

        Raises:
            ValueError: If user not found
        """
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get expiry time from config if not provided
        if expires_in_minutes is None:
            try:
                settings = current_app.config.get("VAULT_SETTINGS")
                if settings and hasattr(settings, "email_verification_expiry_minutes"):
                    expires_in_minutes = settings.email_verification_expiry_minutes
                else:
                    expires_in_minutes = 10  # Default fallback
            except Exception:
                expires_in_minutes = 10  # Default fallback

        # Generate token only (no code)
        token = self.generate_verification_token()
        # Generate empty code (legacy field, will be ignored)
        code = "000000"

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

        # Create verification token
        verification_token = EmailVerificationToken(
            user_id=user_id,
            token=token,
            code=code,  # Legacy field, ignored
            expires_at=expires_at,
        )
        db.session.add(verification_token)
        db.session.commit()

        return verification_token

    def _get_base_url(self, base_url: str | None = None) -> str:
        """Get base URL from VAULT_URL setting or provided base_url.

        Args:
            base_url: Optional base URL to use (takes precedence)

        Returns:
            Base URL string

        Raises:
            ValueError: If VAULT_URL is not configured (required for security)
        """
        # If base_url is provided, use it
        if base_url:
            return base_url.rstrip("/")

        # Try to get from VAULT_SETTINGS
        try:
            settings = current_app.config.get("VAULT_SETTINGS")
            if settings and hasattr(settings, "vault_url") and settings.vault_url:
                return settings.vault_url.rstrip("/")
        except Exception:
            pass

        # SECURITY: VAULT_URL is mandatory - no fallback to request.host_url
        # This prevents Host header injection attacks
        is_production = current_app.config.get("IS_PRODUCTION", True)
        if is_production:
            raise ValueError(
                "VAULT_URL must be configured in production. "
                "Set VAULT_URL environment variable to prevent Host header injection attacks."
            )

        # In development, allow None but log warning
        current_app.logger.warning(
            "VAULT_URL not configured. Email verification links may not work correctly. "
            "Set VAULT_URL environment variable."
        )
        raise ValueError(
            "VAULT_URL must be configured. "
            "Set VAULT_URL environment variable to generate email verification links."
        )

    def _get_expiry_minutes(self) -> int:
        """Get email verification expiry time in minutes from config.

        Returns:
            Expiry time in minutes (default: 10)
        """
        try:
            settings = current_app.config.get("VAULT_SETTINGS")
            if settings and hasattr(settings, "email_verification_expiry_minutes"):
                return settings.email_verification_expiry_minutes
        except Exception:
            pass
        return 10  # Default fallback

    def send_verification_email(
        self,
        user_id: str,
        base_url: str | None = None,
    ) -> bool:
        """Send verification email to user.

        Args:
            user_id: User ID
            base_url: Base URL for verification link (optional, overrides VAULT_URL)

        Returns:
            True if email sent successfully, False otherwise
        """
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        # Create or get existing token
        existing_token = (
            db.session.query(EmailVerificationToken)
            .filter_by(user_id=user_id, used_at=None)
            .filter(EmailVerificationToken.expires_at > datetime.now(timezone.utc))
            .first()
        )

        if existing_token:
            verification_token = existing_token
        else:
            verification_token = self.create_verification_token(user_id)

        # Get base URL (from VAULT_URL setting or provided base_url)
        # This will raise ValueError if VAULT_URL is not configured
        try:
            base_url_final = self._get_base_url(base_url)
            # Use frontend route for verification
            verification_url = (
                f"{base_url_final}/verify-email?token={verification_token.token}"
            )
        except ValueError as e:
            current_app.logger.error(
                f"Failed to get base URL for verification email: {e}"
            )
            return False

        # Send email (no code, only link)
        return self.email_service.send_verification_email(
            to_email=user.email,
            verification_url=verification_url,
            expiry_minutes=self._get_expiry_minutes(),
        )

    def verify_token(self, token: str) -> tuple[bool, User | None, str]:
        """Verify a verification token.

        Args:
            token: Verification token

        Returns:
            Tuple of (success, user, error_message)
        """
        verification_token = (
            db.session.query(EmailVerificationToken)
            .filter_by(token=token, used_at=None)
            .first()
        )

        if not verification_token:
            return False, None, "Invalid or already used token"

        if verification_token.is_expired():
            return False, None, "Token expired"

        user = db.session.query(User).filter_by(id=verification_token.user_id).first()
        if not user:
            return False, None, "User not found"

        # Mark token as used
        verification_token.used_at = datetime.now(timezone.utc)
        db.session.commit()

        # Mark user email as verified
        user.email_verified = True
        db.session.commit()

        return True, user, "Email verified successfully"

    def get_user_verification_status(self, user_id: str) -> dict[str, Any]:
        """Get user email verification status.

        Args:
            user_id: User ID

        Returns:
            Dictionary with verification status
        """
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return {"verified": False, "error": "User not found"}

        # Get latest token
        latest_token = (
            db.session.query(EmailVerificationToken)
            .filter_by(user_id=user_id)
            .order_by(EmailVerificationToken.created_at.desc())
            .first()
        )

        return {
            "verified": user.email_verified,
            "has_pending_token": (
                latest_token is not None
                and latest_token.used_at is None
                and not latest_token.is_expired()
            ),
            "latest_token_created_at": (
                latest_token.created_at.isoformat() if latest_token else None
            ),
        }

    def cleanup_expired_tokens(self) -> int:
        """Clean up expired verification tokens.

        Returns:
            Number of tokens deleted
        """
        from datetime import timedelta

        # Delete tokens expired more than 7 days ago
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        deleted_count = (
            db.session.query(EmailVerificationToken)
            .filter(EmailVerificationToken.expires_at < cutoff)
            .delete()
        )
        db.session.commit()

        return deleted_count
