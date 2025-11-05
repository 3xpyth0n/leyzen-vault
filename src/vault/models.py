"""Data models for Leyzen Vault."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FileMetadata:
    """Metadata for an encrypted file."""

    file_id: str
    original_name: str
    size: int
    encrypted_size: int
    created_at: datetime
    encrypted_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "size": self.size,
            "encrypted_size": self.encrypted_size,
            "created_at": self.created_at.isoformat(),
            "encrypted_hash": self.encrypted_hash,
        }


@dataclass
class AuditLog:
    """Audit log entry for tracking actions."""

    action: str  # upload, download, delete, share, access_denied
    file_id: str | None
    user_ip: str
    timestamp: datetime
    details: dict[str, Any]
    success: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "file_id": self.file_id,
            "user_ip": self.user_ip,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "success": self.success,
        }


@dataclass
class ShareLink:
    """Share link for a file with expiration and download limits."""

    link_id: str  # UUID token
    file_id: str
    created_at: datetime
    expires_at: datetime | None
    max_downloads: int | None
    download_count: int
    is_active: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "link_id": self.link_id,
            "file_id": self.file_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
            "is_active": self.is_active,
        }

    def is_expired(self) -> bool:
        """Check if the link has expired.

        Uses UTC for comparison to ensure consistency regardless of server timezone.
        """
        from datetime import timezone

        if not self.is_active:
            return True
        if self.expires_at:
            # Compare using UTC to ensure consistency
            # expires_at is timezone-aware, so we compare with UTC now
            now_utc = datetime.now(timezone.utc)
            # If expires_at is timezone-aware, convert to UTC for comparison
            if self.expires_at.tzinfo is not None:
                expires_utc = self.expires_at.astimezone(timezone.utc)
            else:
                # If expires_at is naive, assume it's UTC
                expires_utc = self.expires_at.replace(tzinfo=timezone.utc)
            return now_utc > expires_utc
        return False

    def has_reached_limit(self) -> bool:
        """Check if the download limit has been reached."""
        if self.max_downloads is None:
            return False
        return self.download_count >= self.max_downloads


class FileDatabase:
    """SQLite database for file metadata."""

    def __init__(self, db_path: Path):
        """Initialize the database."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    encrypted_size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    encrypted_hash TEXT NOT NULL
                )
            """
            )
            conn.commit()
        finally:
            conn.close()

    def add_file(self, metadata: FileMetadata) -> None:
        """Add a file metadata entry."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO files (file_id, original_name, size, encrypted_size, created_at, encrypted_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.file_id,
                    metadata.original_name,
                    metadata.size,
                    metadata.encrypted_size,
                    metadata.created_at.isoformat(),
                    metadata.encrypted_hash,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_file(self, file_id: str) -> FileMetadata | None:
        """Get file metadata by ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT file_id, original_name, size, encrypted_size, created_at, encrypted_hash
                FROM files WHERE file_id = ?
            """,
                (file_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return FileMetadata(
                file_id=row[0],
                original_name=row[1],
                size=row[2],
                encrypted_size=row[3],
                created_at=datetime.fromisoformat(row[4]),
                encrypted_hash=row[5],
            )
        finally:
            conn.close()

    def list_files(self) -> list[FileMetadata]:
        """List all files."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT file_id, original_name, size, encrypted_size, created_at, encrypted_hash
                FROM files ORDER BY created_at DESC
            """
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    FileMetadata(
                        file_id=row[0],
                        original_name=row[1],
                        size=row[2],
                        encrypted_size=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        encrypted_hash=row[5],
                    )
                )
            return results
        finally:
            conn.close()

    def delete_file(self, file_id: str) -> bool:
        """Delete a file metadata entry."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


__all__ = ["FileMetadata", "FileDatabase", "AuditLog", "ShareLink"]
