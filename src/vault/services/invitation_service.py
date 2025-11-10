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

    def _get_base_url(self, base_url: str | None = None) -> str | None:
        """Get base URL from VAULT_URL setting or provided base_url.

        Args:
            base_url: Optional base URL to use (takes precedence)

        Returns:
            Base URL string or None
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

        # Fallback to request.host_url
        try:
            from flask import request

            if request:
                return request.host_url.rstrip("/")
        except Exception:
            pass

        return None

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
        # If user exists but is inactive (soft deleted), allow invitation to reactivate
        existing_user = (
            db.session.query(User).filter_by(email=email, is_active=True).first()
        )
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
        base_url_final = self._get_base_url(base_url)

        # Build invitation URL (use frontend route)
        if base_url_final:
            invitation_url = f"{base_url_final}/accept-invitation?token={token}"
        else:
            invitation_url = f"/accept-invitation?token={token}"

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
            # If user exists and is active, cannot accept invitation
            if existing_user.is_active:
                # Mark invitation as accepted anyway
                invitation.accepted_at = datetime.now(timezone.utc)
                db.session.commit()
                return None, "An account already exists for this email"
            else:
                # User exists but is inactive (soft deleted) - reactivate the account
                # Update password and reactivate
                if not self.auth_service:
                    from flask import current_app

                    secret_key = current_app.config.get("SECRET_KEY", "")
                    self.auth_service = AuthService(secret_key)

                # Update password
                existing_user.password_hash = self.auth_service.password_hasher.hash(
                    password
                )
                # Reactivate user
                existing_user.is_active = True
                # Update invited_by if not set
                if not existing_user.invited_by:
                    existing_user.invited_by = invitation.invited_by
                # Reset email verification status (need to verify again)
                existing_user.email_verified = False
                db.session.commit()

                # Mark invitation as accepted
                invitation.accepted_at = datetime.now(timezone.utc)
                db.session.commit()

                # Send verification email (always required after reactivation)
                self.email_verification_service.send_verification_email(
                    user_id=existing_user.id,
                    base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
                )

                return existing_user, "Account reactivated successfully"

        # Create user account
        if not self.auth_service:
            from flask import current_app

            secret_key = current_app.config.get("SECRET_KEY", "")
            self.auth_service = AuthService(secret_key)

        try:
            user = self.auth_service.create_user(
                email=invitation.email,
                password=password,
                global_role=GlobalRole.USER,
            )
            # Set invited_by
            user.invited_by = invitation.invited_by
            # Email verification will be sent automatically after account creation
            db.session.commit()

            # Mark invitation as accepted
            invitation.accepted_at = datetime.now(timezone.utc)
            db.session.commit()

            # Send verification email (always required)
            # VAULT_URL from settings will be used automatically
            self.email_verification_service.send_verification_email(
                user_id=user.id,
                base_url=None,  # Will use VAULT_URL from settings or request.host_url as fallback
            )

            return user, "Account created successfully"
        except ValueError as e:
            return None, str(e)

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
        base_url_final = self._get_base_url(base_url)

        # Build invitation URL (use frontend route)
        if base_url_final:
            invitation_url = (
                f"{base_url_final}/accept-invitation?token={invitation.token}"
            )
        else:
            invitation_url = f"/accept-invitation?token={invitation.token}"

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
