"""Data models for Leyzen Vault."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class User:
    """User model for multi-user support."""

    user_id: str  # UUID
    username: str
    password_hash: str  # PBKDF2 hash
    created_at: datetime
    last_login: datetime | None = None
    email: str | None = None
    is_admin: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


@dataclass
class FileMetadata:
    """Metadata for an encrypted file."""

    file_id: str
    original_name: str
    size: int
    encrypted_size: int
    created_at: datetime
    encrypted_hash: str
    user_id: str | None = None  # User who owns/uploaded the file
    folder_id: str | None = None  # Reference to parent folder
    encrypted_tags: str | None = None  # Encrypted JSON tags
    encrypted_description: str | None = None  # Encrypted description
    mime_type: str | None = None  # MIME type for preview
    thumbnail_hash: str | None = None  # Hash of encrypted thumbnail

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "size": self.size,
            "encrypted_size": self.encrypted_size,
            "created_at": self.created_at.isoformat(),
            "encrypted_hash": self.encrypted_hash,
            "folder_id": self.folder_id,
            "encrypted_tags": self.encrypted_tags,
            "encrypted_description": self.encrypted_description,
            "mime_type": self.mime_type,
            "thumbnail_hash": self.thumbnail_hash,
            "user_id": self.user_id,
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
class Folder:
    """Metadata for an encrypted folder."""

    folder_id: str
    encrypted_name: str  # Encrypted folder name
    name_hash: str  # SHA-256 hash of folder name for search
    parent_id: str | None  # None for root folder
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_id": self.folder_id,
            "encrypted_name": self.encrypted_name,
            "name_hash": self.name_hash,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
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
    is_active: bool  # Always True for existing links (kept for backward compatibility)

    def to_dict(self, share_url: str | None = None) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Args:
            share_url: Optional share URL to include in the response
        """
        result = {
            "link_id": self.link_id,
            "file_id": self.file_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
            "is_active": True,  # Always True since we only return existing links
            "is_expired": self.is_expired(),
        }
        if share_url:
            result["share_url"] = share_url
        return result

    def is_expired(self, tolerance_seconds: int = 60) -> bool:
        """Check if the link has expired.

        Uses UTC for comparison to ensure consistency regardless of server timezone.
        Adds a tolerance window to account for clock drift and network delays.

        Args:
            tolerance_seconds: Tolerance in seconds (default: 60) to account for clock drift

        Returns:
            True if expired, False otherwise
        """
        from datetime import timezone, timedelta

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

            # Apply tolerance to account for clock drift and network delays
            # This prevents false positives due to minor clock differences
            expires_with_tolerance = expires_utc + timedelta(seconds=tolerance_seconds)
            return now_utc > expires_with_tolerance
        return False

    def has_reached_limit(self) -> bool:
        """Check if the download limit has been reached."""
        if self.max_downloads is None:
            return False
        return self.download_count >= self.max_downloads


__all__ = [
    "FileMetadata",
    "AuditLog",
    "ShareLink",
    "Folder",
    "User",
]
