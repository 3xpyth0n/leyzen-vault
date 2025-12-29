"""Share link service for Leyzen Vault."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import logging

from flask import current_app

from ..database.schema import ShareLink as ShareLinkModel, db
from ..models import ShareLink

logger = logging.getLogger(__name__)


class ShareService:
    """Service for managing share links with expiration and download limits."""

    def __init__(self, timezone: ZoneInfo | None = None):
        """Initialize the share service.

        Args:
            timezone: Timezone to use for timestamps. Defaults to UTC if not provided.
        """
        self.timezone = timezone or ZoneInfo("UTC")

    def _get_base_url(self) -> str | None:
        """Get base URL from VAULT_URL setting.

        Returns:
            Base URL string or None if not configured

        Note:
            This method does not raise an error if VAULT_URL is not set
            because share links can work with relative URLs as fallback.
            However, VAULT_URL should be configured for proper functionality.
        """

        try:
            settings = current_app.config.get("VAULT_SETTINGS")
            if settings and hasattr(settings, "vault_url") and settings.vault_url:
                return settings.vault_url.rstrip("/")
        except Exception as e:
            # Log warning but continue
            logger.warning(f"Failed to get vault_url from VAULT_SETTINGS: {e}")

        # SECURITY: No fallback to request.host_url to prevent Host header injection
        # Share links will use relative URLs if VAULT_URL is not configured
        logger.warning(
            "VAULT_URL not configured. Share links will use relative URLs. "
            "Set VAULT_URL environment variable for proper functionality."
        )
        return None

    def get_share_url(self, link_id: str, file_id: str) -> str:
        """Get the full share URL for a share link.

        Args:
            link_id: Share link ID
            file_id: File ID

        Returns:
            Full share URL
        """
        base_url = self._get_base_url()
        if base_url:
            return f"{base_url}/share/{link_id}"
        else:
            # Fallback to relative URL
            return f"/share/{link_id}"

    def create_share_link(
        self,
        file_id: str,
        expires_in_hours: int | None = None,
        max_downloads: int | None = None,
    ) -> ShareLink:
        """Create a new share link."""
        link_id = secrets.token_urlsafe(32)
        created_at = datetime.now(self.timezone)
        expires_at = None
        if expires_in_hours:
            expires_at = created_at + timedelta(hours=expires_in_hours)

        # Create share link in PostgreSQL
        share_link_model = ShareLinkModel(
            link_id=link_id,
            file_id=file_id,
            created_at=created_at,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
        )
        db.session.add(share_link_model)
        db.session.commit()

        # Convert to dataclass for compatibility
        return ShareLink(
            link_id=link_id,
            file_id=file_id,
            created_at=created_at,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
            is_active=True,
        )

    def get_share_link(self, link_id: str) -> ShareLink | None:
        """Get a share link by ID."""
        try:
            share_link_model = (
                db.session.query(ShareLinkModel).filter_by(link_id=link_id).first()
            )
            if not share_link_model:
                logger.debug(
                    f"Share link not found in database: link_id={link_id[:20]}..."
                )
                return None

            # Convert to dataclass for compatibility
            return ShareLink(
                link_id=share_link_model.link_id,
                file_id=share_link_model.file_id,
                created_at=share_link_model.created_at,
                expires_at=share_link_model.expires_at,
                max_downloads=share_link_model.max_downloads,
                download_count=share_link_model.download_count,
                is_active=True,  # Always True since we only return existing links
            )
        except Exception as e:
            logger.error(
                f"Error retrieving share link {link_id[:20]}...: {e}", exc_info=True
            )
            return None

    def validate_share_link(self, link_id: str) -> tuple[bool, str | None]:
        """Validate a share link and return (is_valid, error_message).

        Uses UTC time for validation to ensure consistency across timezones.
        Adds tolerance for clock drift to prevent false positives.
        """
        share_link = self.get_share_link(link_id)
        if not share_link:
            return False, "Share link not found"

        # Validate expiration with tolerance (60 seconds) for clock drift
        if share_link.is_expired(tolerance_seconds=60):
            return False, "Share link has expired"

        if share_link.has_reached_limit():
            return False, "Download limit reached"

        return True, None

    def increment_download_count(self, link_id: str) -> None:
        """Increment the download count for a share link."""
        share_link_model = (
            db.session.query(ShareLinkModel).filter_by(link_id=link_id).first()
        )
        if share_link_model:
            share_link_model.download_count += 1
            db.session.commit()

    def revoke_link(self, link_id: str) -> None:
        """Revoke (permanently delete) a share link."""
        share_link_model = (
            db.session.query(ShareLinkModel).filter_by(link_id=link_id).first()
        )
        if share_link_model:
            db.session.delete(share_link_model)
            db.session.commit()

    def revoke_all_links_for_file(self, file_id: str) -> int:
        """Revoke (permanently delete) all share links for a file.

        Args:
            file_id: File ID

        Returns:
            Number of links revoked
        """
        # Delete all links for this file
        deleted_count = (
            db.session.query(ShareLinkModel)
            .filter_by(file_id=file_id)
            .delete(synchronize_session=False)
        )

        if deleted_count > 0:
            db.session.commit()

        return int(deleted_count)

    def list_links_for_file(self, file_id: str) -> list[ShareLink]:
        """List all share links for a file."""
        share_link_models = (
            db.session.query(ShareLinkModel)
            .filter_by(file_id=file_id)
            .order_by(ShareLinkModel.created_at.desc())
            .all()
        )

        # Convert to dataclass list for compatibility
        return [
            ShareLink(
                link_id=model.link_id,
                file_id=model.file_id,
                created_at=model.created_at,
                expires_at=model.expires_at,
                max_downloads=model.max_downloads,
                download_count=model.download_count,
                is_active=True,  # Always True since we only return existing links
            )
            for model in share_link_models
        ]

    def cleanup_expired_links(self) -> int:
        """Permanently delete expired links and return count of cleaned links."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        deleted_count = (
            db.session.query(ShareLinkModel)
            .filter(
                ShareLinkModel.expires_at.isnot(None),
                ShareLinkModel.expires_at < now_utc,
            )
            .delete(synchronize_session=False)
        )

        if deleted_count > 0:
            db.session.commit()

        return int(deleted_count)


__all__ = ["ShareService"]
