"""Preview service for generating thumbnails from encrypted files."""

from __future__ import annotations

import hashlib
from pathlib import Path


class PreviewService:
    """Service for generating preview thumbnails from files."""

    def __init__(self, storage_dir: Path):
        """Initialize preview service with storage directory."""
        self.storage_dir = storage_dir
        self.thumbnail_dir = storage_dir / "thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    def generate_thumbnail_hash(self, file_id: str) -> str:
        """Generate hash for thumbnail filename."""
        return hashlib.sha256(file_id.encode()).hexdigest()

    def get_thumbnail_path(self, file_id: str) -> Path:
        """Get path to thumbnail file."""
        thumbnail_hash = self.generate_thumbnail_hash(file_id)
        return self.thumbnail_dir / thumbnail_hash

    def save_thumbnail(self, file_id: str, thumbnail_data: bytes) -> Path:
        """Save thumbnail data."""
        thumbnail_path = self.get_thumbnail_path(file_id)
        thumbnail_path.write_bytes(thumbnail_data)
        return thumbnail_path

    def get_thumbnail(self, file_id: str) -> bytes | None:
        """Get thumbnail data if exists."""
        thumbnail_path = self.get_thumbnail_path(file_id)
        if thumbnail_path.exists():
            return thumbnail_path.read_bytes()
        return None

    def delete_thumbnail(self, file_id: str) -> bool:
        """Delete thumbnail file."""
        thumbnail_path = self.get_thumbnail_path(file_id)
        if thumbnail_path.exists():
            thumbnail_path.unlink()
            return True
        return False

    def thumbnail_exists(self, file_id: str) -> bool:
        """Check if thumbnail exists."""
        return self.get_thumbnail_path(file_id).exists()


__all__ = ["PreviewService"]
