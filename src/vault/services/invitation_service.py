"""Invitation service for managing user invitations by admins."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from vault.database.schema import GlobalRole, User, UserInvitation, db
from vault.services.auth_service import AuthService
from vault.services.email_service import EmailService
from vault.services.email_verification_service import EmailVerificationService


class InvitationService:
    """Service for managing user invitations."""

    def __init__(
        self,
        email_service: EmailService | None = None,
        auth_service: AuthService | None = None,
        email_verification_service: EmailVerificationService | None = None,
    ):
        """Initialize invitation service.

        Args:
            email_service: Email service instance
            auth_service: Auth service instance
            email_verification_service: Email verification service instance
        """
        self.email_service = email_service or EmailService()
        self.auth_service = auth_service
        self.email_verification_service = (
            email_verification_service or EmailVerificationService()
        )

    def generate_invitation_token(self) -> str:
        """Generate a secure invitation token.

        Returns:
            Invitation token string
        """
        return secrets.token_urlsafe(32)

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

        # In development, log warning and raise error
        current_app.logger.warning(
            "VAULT_URL not configured. Invitation links may not work correctly. "
            "Set VAULT_URL environment variable."
        )
        raise ValueError(
            "VAULT_URL must be configured. "
            "Set VAULT_URL environment variable to generate invitation links."
        )

    def create_invitation(
        self,
        email: str,
        invited_by: str,
        expires_in_days: int = 7,
        base_url: str | None = None,
    ) -> UserInvitation:
        """Create a new user invitation.

        Args:
            email: Email address to invite
            invited_by: User ID of admin creating the invitation
            expires_in_days: Expiration time in days (default: 7)
            base_url: Base URL for invitation link (optional, overrides VAULT_URL)

        Returns:
            UserInvitation object

        Raises:
            ValueError: If email already has an account or invitation exists
        """
        # Check if an active user already exists
        # Check if user already exists
        existing_user = db.session.query(User).filter_by(email=email).first()
        if existing_user:
            raise ValueError(f"An account already exists for email {email}")

        # Check if pending invitation exists
        existing_invitation = (
            db.session.query(UserInvitation)
            .filter_by(email=email, accepted_at=None)
            .filter(UserInvitation.expires_at > datetime.now(timezone.utc))
            .first()
        )
        if existing_invitation:
            raise ValueError(f"A pending invitation already exists for email {email}")

        # Verify inviter is admin
        inviter = db.session.query(User).filter_by(id=invited_by).first()
        if not inviter:
            raise ValueError(f"User {invited_by} not found")
        if inviter.global_role not in (GlobalRole.ADMIN, GlobalRole.SUPERADMIN):
            raise ValueError("Only administrators can create invitations")

        # Generate token
        token = self.generate_invitation_token()

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create invitation
        invitation = UserInvitation(
            email=email,
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
        )
        db.session.add(invitation)
        db.session.commit()

        # Get base URL (from VAULT_URL setting or provided base_url)
        # This will raise ValueError if VAULT_URL is not configured
        try:
            base_url_final = self._get_base_url(base_url)
            # Build invitation URL (use frontend route)
            invitation_url = f"{base_url_final}/accept-invitation?token={token}"
        except ValueError as e:
            current_app.logger.error(
                f"Failed to get base URL for invitation email: {e}"
            )
            raise ValueError(f"Cannot send invitation email: {e}") from e

        self.email_service.send_invitation_email(
            to_email=email,
            invitation_url=invitation_url,
            invited_by=inviter.email,
        )

        return invitation

    def get_invitation(self, token: str) -> UserInvitation | None:
        """Get invitation by token.

        Args:
            token: Invitation token

        Returns:
            UserInvitation object or None if not found
        """
        return db.session.query(UserInvitation).filter_by(token=token).first()

    def accept_invitation(
        self,
        token: str,
        password: str,
    ) -> tuple[User | None, str]:
        """Accept an invitation and create user account.

        Args:
            token: Invitation token
            password: User password

        Returns:
            Tuple of (User, error_message)
        """
        invitation = self.get_invitation(token)
        if not invitation:
            return None, "Invitation not found"

        if invitation.is_accepted():
            return None, "Invitation already accepted"

        if invitation.is_expired():
            return None, "Invitation expired"

        # Check if user already exists
        existing_user = db.session.query(User).filter_by(email=invitation.email).first()
        if existing_user:
            # If user exists, cannot accept invitation (user already exists)
            # Mark invitation as accepted anyway
            invitation.accepted_at = datetime.now(timezone.utc)
            db.session.commit()
            return None, "An account already exists for this email"

        # Create new user account
        if not self.auth_service:
            from flask import current_app

            secret_key = current_app.config.get("SECRET_KEY", "")
            self.auth_service = AuthService(secret_key)

        # Create user
        new_user = self.auth_service.create_user(
            email=invitation.email,
            password=password,
            global_role=invitation.role,
        )

        # Set invited_by
        new_user.invited_by = invitation.invited_by
        db.session.commit()

        # Mark invitation as accepted
        invitation.accepted_at = datetime.now(timezone.utc)
        db.session.commit()

        # Send verification email (always required)
        self.email_verification_service.send_verification_email(
            user_id=new_user.id,
            base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
        )

        return new_user, "Account created successfully"

    def list_invitations(
        self,
        invited_by: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """List invitations with filters.

        Args:
            invited_by: Filter by inviter user ID
            status: Filter by status ("pending", "accepted", "expired")
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Dictionary with invitations and pagination info
        """
        query = db.session.query(UserInvitation)

        if invited_by:
            query = query.filter_by(invited_by=invited_by)

        if status == "pending":
            query = query.filter_by(accepted_at=None).filter(
                UserInvitation.expires_at > datetime.now(timezone.utc)
            )
        elif status == "accepted":
            query = query.filter(UserInvitation.accepted_at.isnot(None))
        elif status == "expired":
            query = query.filter_by(accepted_at=None).filter(
                UserInvitation.expires_at <= datetime.now(timezone.utc)
            )

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        invitations = (
            query.order_by(UserInvitation.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        return {
            "invitations": [inv.to_dict() for inv in invitations],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page if per_page > 0 else 1,
            },
        }

    def resend_invitation(
        self,
        invitation_id: str,
        base_url: str | None = None,
    ) -> bool:
        """Resend invitation email.

        Args:
            invitation_id: Invitation ID
            base_url: Base URL for invitation link (optional, overrides VAULT_URL)

        Returns:
            True if email sent successfully, False otherwise
        """
        invitation = (
            db.session.query(UserInvitation).filter_by(id=invitation_id).first()
        )
        if not invitation:
            return False

        if invitation.is_accepted():
            return False

        if invitation.is_expired():
            return False

        # Get inviter
        inviter = db.session.query(User).filter_by(id=invitation.invited_by).first()
        invited_by_email = inviter.email if inviter else None

        # Get base URL (from VAULT_URL setting or provided base_url)
        # This will raise ValueError if VAULT_URL is not configured
        try:
            base_url_final = self._get_base_url(base_url)
            # Build invitation URL (use frontend route)
            invitation_url = (
                f"{base_url_final}/accept-invitation?token={invitation.token}"
            )
        except ValueError as e:
            current_app.logger.error(
                f"Failed to get base URL for invitation email: {e}"
            )
            return False

        return self.email_service.send_invitation_email(
            to_email=invitation.email,
            invitation_url=invitation_url,
            invited_by=invited_by_email,
        )

    def cancel_invitation(self, invitation_id: str) -> bool:
        """Cancel an invitation.

        Args:
            invitation_id: Invitation ID

        Returns:
            True if cancelled, False if not found
        """
        invitation = (
            db.session.query(UserInvitation).filter_by(id=invitation_id).first()
        )
        if not invitation:
            return False

        if invitation.is_accepted():
            return False  # Cannot cancel accepted invitation

        # Delete invitation
        db.session.delete(invitation)
        db.session.commit()

        return True

    def cleanup_expired_invitations(self) -> int:
        """Clean up expired invitations.

        Returns:
            Number of invitations deleted
        """
        from datetime import timedelta

        # Delete invitations expired more than 30 days ago
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        deleted_count = (
            db.session.query(UserInvitation)
            .filter(
                UserInvitation.expires_at < cutoff,
                UserInvitation.accepted_at.is_(None),
            )
            .delete()
        )
        db.session.commit()

        return deleted_count
