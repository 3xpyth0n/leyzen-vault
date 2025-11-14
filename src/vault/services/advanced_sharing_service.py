"""Advanced sharing service for public links and granular permissions."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.database.schema import (
    File,
    PublicShareLink,
    User,
    db,
)
from vault.services.encryption_service import EncryptionService
from werkzeug.security import check_password_hash, generate_password_hash


class AdvancedSharingService:
    """Service for managing advanced sharing features."""

    def __init__(self):
        self.encryption_service = EncryptionService()

    def create_public_link(
        self,
        resource_id: str,
        resource_type: str,
        created_by: str,
        password: str | None = None,
        expires_in_days: int | None = None,
        max_downloads: int | None = None,
        max_access_count: int | None = None,
        allow_download: bool = True,
        allow_preview: bool = True,
        permission_type: str = "read",
    ) -> PublicShareLink:
        """Create a public share link.

        Args:
            resource_id: Resource ID (file or vaultspace)
            resource_type: Resource type ('file' or 'vaultspace')
            created_by: User ID creating the link
            password: Optional password for the link
            expires_in_days: Optional expiration in days
            max_downloads: Optional maximum download count
            max_access_count: Optional maximum access count
            allow_download: Whether download is allowed
            allow_preview: Whether preview is allowed
            permission_type: Permission type (read, write, admin)

        Returns:
            PublicShareLink object

        Raises:
            ValueError: If resource not found or invalid parameters
        """
        # Verify resource exists
        if resource_type == "file":
            resource = db.session.query(File).filter_by(id=resource_id).first()
            if not resource:
                raise ValueError(f"File {resource_id} not found")
        elif resource_type == "vaultspace":
            from vault.database.schema import VaultSpace

            resource = db.session.query(VaultSpace).filter_by(id=resource_id).first()
            if not resource:
                raise ValueError(f"VaultSpace {resource_id} not found")
        else:
            raise ValueError(f"Invalid resource_type: {resource_type}")

        # Verify user exists
        user = db.session.query(User).filter_by(id=created_by, is_active=True).first()
        if not user:
            raise ValueError(f"User {created_by} not found")

        # Generate unique token
        token = secrets.token_urlsafe(48)

        # Hash password if provided
        password_hash = None
        if password:
            password_hash = generate_password_hash(password)

        # Calculate expiration date
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create share link
        share_link = PublicShareLink(
            resource_id=resource_id,
            resource_type=resource_type,
            created_by=created_by,
            token=token,
            password_hash=password_hash,
            expires_at=expires_at,
            max_downloads=max_downloads,
            max_access_count=max_access_count,
            allow_download=allow_download,
            allow_preview=allow_preview,
            permission_type=permission_type,
        )

        db.session.add(share_link)
        db.session.commit()

        return share_link

    def get_public_link(self, token: str) -> PublicShareLink | None:
        """Get public share link by token.

        Args:
            token: Share link token

        Returns:
            PublicShareLink object or None if not found
        """
        return db.session.query(PublicShareLink).filter_by(token=token).first()

    def verify_public_link_password(
        self, token: str, password: str
    ) -> tuple[bool, PublicShareLink | None]:
        """Verify password for a public share link.

        Args:
            token: Share link token
            password: Password to verify

        Returns:
            Tuple of (is_valid, share_link)
        """
        share_link = self.get_public_link(token)
        if not share_link:
            return False, None

        if not share_link.password_hash:
            return True, share_link

        if check_password_hash(share_link.password_hash, password):
            return True, share_link

        return False, share_link

    def access_public_link(
        self, token: str, password: str | None = None
    ) -> PublicShareLink | None:
        """Access a public share link (increments access count).

        Args:
            token: Share link token
            password: Optional password

        Returns:
            PublicShareLink object if access granted, None otherwise
        """
        if password:
            is_valid, share_link = self.verify_public_link_password(token, password)
            if not is_valid:
                return None
        else:
            share_link = self.get_public_link(token)
            if not share_link:
                return None

        if not share_link.can_access():
            return None

        # Increment access count
        share_link.access_count += 1
        share_link.last_accessed_at = datetime.now(timezone.utc)
        db.session.commit()

        return share_link

    def download_public_link(
        self, token: str, password: str | None = None
    ) -> PublicShareLink | None:
        """Download via public share link (increments download count).

        Args:
            token: Share link token
            password: Optional password

        Returns:
            PublicShareLink object if download allowed, None otherwise
        """
        share_link = self.access_public_link(token, password)
        if not share_link:
            return None

        if not share_link.allow_download:
            return None

        # Increment download count
        share_link.download_count += 1
        db.session.commit()

        return share_link

    def list_user_public_links(
        self, user_id: str, resource_id: str | None = None
    ) -> list[PublicShareLink]:
        """List public share links created by a user.

        Args:
            user_id: User ID
            resource_id: Optional resource ID filter

        Returns:
            List of PublicShareLink objects
        """
        query = db.session.query(PublicShareLink).filter_by(created_by=user_id)
        if resource_id:
            query = query.filter_by(resource_id=resource_id)
        return query.order_by(PublicShareLink.created_at.desc()).all()

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    def _get_share_link_by_identifier(self, identifier: str) -> PublicShareLink | None:
        if self._is_uuid(identifier):
            link = db.session.query(PublicShareLink).filter_by(id=identifier).first()
            if link:
                return link
        return db.session.query(PublicShareLink).filter_by(token=identifier).first()

    def revoke_public_link(self, link_id: str, user_id: str) -> bool:
        """Revoke a public share link.

        Args:
            link_id: Share link ID or token
            user_id: User ID (must be creator)

        Returns:
            True if revoked, False otherwise
        """
        # Try to find by ID first, then by token
        share_link = self._get_share_link_by_identifier(link_id)

        if not share_link:
            return False

        if share_link.created_by != user_id:
            return False

        share_link.is_active = False
        db.session.commit()
        return True

    def revoke_all_links_for_file(
        self, resource_id: str, resource_type: str = "file"
    ) -> int:
        """Revoke all active share links for a file or resource.

        Args:
            resource_id: Resource ID (file or vaultspace)
            resource_type: Resource type ('file' or 'vaultspace'), defaults to 'file'

        Returns:
            Number of links revoked
        """
        # Find all active links for this resource
        active_links = (
            db.session.query(PublicShareLink)
            .filter_by(resource_id=resource_id, resource_type=resource_type)
            .filter_by(is_active=True)
            .all()
        )

        # Revoke all active links
        count = len(active_links)
        for link in active_links:
            link.is_active = False

        if count > 0:
            db.session.commit()

        return count

    def update_public_link(
        self,
        link_id: str,
        user_id: str,
        expires_in_days: int | None = None,
        max_downloads: int | None = None,
        max_access_count: int | None = None,
        allow_download: bool | None = None,
        allow_preview: bool | None = None,
        is_active: bool | None = None,
    ) -> PublicShareLink | None:
        """Update a public share link.

        Args:
            link_id: Share link ID or token
            user_id: User ID (must be creator)
            expires_in_days: Optional new expiration in days
            max_downloads: Optional new max downloads
            max_access_count: Optional new max access count
            allow_download: Optional new allow_download setting
            allow_preview: Optional new allow_preview setting
            is_active: Optional new is_active setting

        Returns:
            Updated PublicShareLink object or None if not found/unauthorized
        """
        # Try to find by ID first, then by token
        share_link = self._get_share_link_by_identifier(link_id)

        if not share_link:
            return None

        if share_link.created_by != user_id:
            return None

        if expires_in_days is not None:
            if expires_in_days == 0:
                share_link.expires_at = None
            else:
                share_link.expires_at = datetime.now(timezone.utc) + timedelta(
                    days=expires_in_days
                )

        if max_downloads is not None:
            share_link.max_downloads = max_downloads

        if max_access_count is not None:
            share_link.max_access_count = max_access_count

        if allow_download is not None:
            share_link.allow_download = allow_download

        if allow_preview is not None:
            share_link.allow_preview = allow_preview

        if is_active is not None:
            share_link.is_active = is_active

        db.session.commit()
        return share_link
