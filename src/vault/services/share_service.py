"""Share link service for Leyzen Vault."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..models import ShareLink


class ShareService:
    """Service for managing share links with expiration and download limits."""

    def __init__(self, db_path: Path, timezone: ZoneInfo | None = None):
        """Initialize the share service.

        Args:
            db_path: Path to the share links database file
            timezone: Timezone to use for timestamps. Defaults to UTC if not provided.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone = timezone or ZoneInfo("UTC")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the share links database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS share_links (
                    link_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    max_downloads INTEGER,
                    download_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_share_file_id ON share_links(file_id)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_share_expires_at ON share_links(expires_at)
            """
            )
            conn.commit()
        finally:
            conn.close()

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

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO share_links (link_id, file_id, created_at, expires_at, max_downloads, download_count, is_active)
                VALUES (?, ?, ?, ?, ?, 0, 1)
            """,
                (
                    link_id,
                    file_id,
                    created_at.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                    max_downloads,
                ),
            )
            conn.commit()
        finally:
            conn.close()

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
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT link_id, file_id, created_at, expires_at, max_downloads, download_count, is_active
                FROM share_links WHERE link_id = ?
            """,
                (link_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ShareLink(
                link_id=row[0],
                file_id=row[1],
                created_at=datetime.fromisoformat(row[2]),
                expires_at=datetime.fromisoformat(row[3]) if row[3] else None,
                max_downloads=row[4],
                download_count=row[5],
                is_active=bool(row[6]),
            )
        finally:
            conn.close()

    def validate_share_link(self, link_id: str) -> tuple[bool, str | None]:
        """Validate a share link and return (is_valid, error_message)."""
        share_link = self.get_share_link(link_id)
        if not share_link:
            return False, "Share link not found"

        if share_link.is_expired():
            return False, "Share link has expired"

        if share_link.has_reached_limit():
            return False, "Download limit reached"

        return True, None

    def increment_download_count(self, link_id: str) -> None:
        """Increment the download count for a share link."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE share_links
                SET download_count = download_count + 1
                WHERE link_id = ?
            """,
                (link_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def deactivate_link(self, link_id: str) -> None:
        """Deactivate a share link."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE share_links
                SET is_active = 0
                WHERE link_id = ?
            """,
                (link_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def list_links_for_file(self, file_id: str) -> list[ShareLink]:
        """List all share links for a file."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT link_id, file_id, created_at, expires_at, max_downloads, download_count, is_active
                FROM share_links WHERE file_id = ? ORDER BY created_at DESC
            """,
                (file_id,),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    ShareLink(
                        link_id=row[0],
                        file_id=row[1],
                        created_at=datetime.fromisoformat(row[2]),
                        expires_at=datetime.fromisoformat(row[3]) if row[3] else None,
                        max_downloads=row[4],
                        download_count=row[5],
                        is_active=bool(row[6]),
                    )
                )
            return results
        finally:
            conn.close()

    def cleanup_expired_links(self) -> int:
        """Deactivate expired links and return count of cleaned links."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                UPDATE share_links
                SET is_active = 0
                WHERE is_active = 1
                AND expires_at IS NOT NULL
                AND expires_at < ?
            """,
                (datetime.now(self.timezone).isoformat(),),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


__all__ = ["ShareService"]
