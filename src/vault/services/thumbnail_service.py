"""Thumbnail generation service for Leyzen Vault."""

from __future__ import annotations

import hashlib
import io

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from vault.storage import FileStorage


class ThumbnailService:
    """Service for generating and managing thumbnails."""

    def __init__(self, storage: FileStorage | None = None):
        """Initialize thumbnail service.

        Args:
            storage: FileStorage instance (optional, will be created if not provided)
        """
        self.storage = storage
        self.thumbnail_sizes = [
            (64, 64),  # Small thumbnail
            (128, 128),  # Medium thumbnail
            (256, 256),  # Large thumbnail
        ]

    def generate_thumbnail(
        self, file_data: bytes, mime_type: str, size: tuple[int, int] = (256, 256)
    ) -> bytes | None:
        """Generate thumbnail from file data.

        Args:
            file_data: File data (encrypted)
            mime_type: MIME type of the file
            size: Thumbnail size (width, height)

        Returns:
            Thumbnail image bytes or None if generation failed
        """
        # Only generate thumbnails for images
        if not mime_type.startswith("image/"):
            return None

        if not PIL_AVAILABLE:
            return None

        try:
            # Note: This assumes file_data is decrypted
            # In production, we'd decrypt client-side or use a secure thumbnail service
            image = Image.open(io.BytesIO(file_data))

            # Convert to RGB if necessary (for PNG with transparency, etc.)
            if image.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image, mask=image.split()[-1] if image.mode == "RGBA" else None
                )
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Resize maintaining aspect ratio
            image.thumbnail(size, Image.Resampling.LANCZOS)

            # Save to bytes
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue()

        except Exception:
            # If thumbnail generation fails, return None
            return None

    def generate_thumbnail_hash(self, file_id: str, size: tuple[int, int]) -> str:
        """Generate a hash for thumbnail storage key.

        Args:
            file_id: File ID
            size: Thumbnail size

        Returns:
            Hash string for thumbnail key
        """
        key = f"{file_id}_{size[0]}x{size[1]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get_thumbnail_storage_key(self, file_id: str, size: tuple[int, int]) -> str:
        """Get storage key for thumbnail.

        Args:
            file_id: File ID
            size: Thumbnail size

        Returns:
            Storage key for thumbnail
        """
        hash_key = self.generate_thumbnail_hash(file_id, size)
        return f"thumbnails/{hash_key[:2]}/{hash_key[2:4]}/{hash_key}_{size[0]}x{size[1]}.jpg"

    def save_thumbnail(
        self, file_id: str, thumbnail_data: bytes, size: tuple[int, int]
    ) -> str:
        """Save thumbnail to storage.

        Args:
            file_id: File ID
            thumbnail_data: Thumbnail image bytes
            size: Thumbnail size

        Returns:
            Storage reference for thumbnail
        """
        if not self.storage:
            from flask import current_app

            self.storage = current_app.config.get("VAULT_STORAGE")

        storage_key = self.get_thumbnail_storage_key(file_id, size)
        # save_file returns a Path, but we need to return the storage_key as string
        self.storage.save_file(storage_key, thumbnail_data)
        return storage_key

    def get_thumbnail(
        self, file_id: str, size: tuple[int, int] = (256, 256)
    ) -> bytes | None:
        """Get thumbnail from storage.

        Args:
            file_id: File ID
            size: Thumbnail size

        Returns:
            Thumbnail image bytes or None if not found
        """
        if not self.storage:
            from flask import current_app

            self.storage = current_app.config.get("VAULT_STORAGE")

        storage_key = self.get_thumbnail_storage_key(file_id, size)
        try:
            return self.storage.read_file(storage_key)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def generate_and_save_thumbnails(
        self, file_id: str, file_data: bytes, mime_type: str
    ) -> dict[str, str]:
        """Generate and save thumbnails for all sizes.

        Args:
            file_id: File ID
            file_data: Decrypted file data
            mime_type: MIME type

        Returns:
            Dictionary mapping size to storage reference
        """
        thumbnails = {}
        for size in self.thumbnail_sizes:
            thumbnail_data = self.generate_thumbnail(file_data, mime_type, size)
            if thumbnail_data:
                storage_ref = self.save_thumbnail(file_id, thumbnail_data, size)
                thumbnails[f"{size[0]}x{size[1]}"] = storage_ref

        return thumbnails

    def delete_thumbnails(self, file_id: str) -> bool:
        """Delete all thumbnails for a file.

        Args:
            file_id: File ID

        Returns:
            True if successful
        """
        if not self.storage:
            from flask import current_app

            self.storage = current_app.config.get("VAULT_STORAGE")

        success = True
        for size in self.thumbnail_sizes:
            storage_key = self.get_thumbnail_storage_key(file_id, size)
            try:
                self.storage.delete_file(storage_key)
            except Exception:
                success = False

        return success
