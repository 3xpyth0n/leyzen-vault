"""VaultSpace service for Leyzen Vault."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from vault.database.schema import (
    File,
    FileKey,
    User,
    VaultSpace,
    VaultSpaceKey,
    VaultSpaceType,
    db,
)
from vault.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)
from vault.storage import FileStorage
from vault.utils.valid_icons import is_valid_icon_name


class VaultSpaceService:
    """Service for VaultSpace management."""

    def __init__(self):
        """Initialize VaultSpace service."""
        self.encryption_service = EncryptionService()

    def _check_duplicate_vaultspace_name(
        self, name: str, exclude_vaultspace_id: str | None = None
    ) -> bool:
        """Check if a vaultspace with the same name already exists.

        Args:
            name: VaultSpace name to check
            exclude_vaultspace_id: Optional VaultSpace ID to exclude from check (for renaming)

        Returns:
            True if a duplicate exists, False otherwise
        """
        query = db.session.query(VaultSpace).filter_by(name=name)
        if exclude_vaultspace_id:
            query = query.filter(VaultSpace.id != exclude_vaultspace_id)
        existing = query.first()
        return existing is not None

    def _validate_vaultspace_name(
        self, name: str, exclude_vaultspace_id: str | None = None
    ) -> None:
        """Validate vaultspace name format and check for duplicates.

        Args:
            name: VaultSpace name to validate
            exclude_vaultspace_id: Optional VaultSpace ID to exclude from duplicate check

        Raises:
            ValueError: If name is invalid or duplicate exists
        """
        # Validate filename format using common validation utility
        from vault.utils.file_validation import validate_filename

        is_valid, validation_error = validate_filename(name)
        if not is_valid:
            raise ValueError(validation_error or "Invalid vaultspace name")

        # Check for duplicate names globally
        if self._check_duplicate_vaultspace_name(name, exclude_vaultspace_id):
            raise ValueError("A vaultspace with this name already exists")

    def create_vaultspace(
        self,
        name: str,
        owner_user_id: str,
        encrypted_metadata: str | None = None,
        icon_name: str | None = None,
    ) -> VaultSpace:
        """Create a new VaultSpace.

        Args:
            name: VaultSpace name
            owner_user_id: Owner user ID
            encrypted_metadata: Encrypted metadata (optional)
            icon_name: Icon name for the VaultSpace (optional, must be a valid SVG icon name)

        Returns:
            Created VaultSpace object

        Raises:
            ValueError: If owner not found, invalid parameters, or invalid icon name
        """
        if not owner_user_id:
            raise ValueError("owner_user_id is required")

        # Legacy admin cannot create VaultSpaces (no DB user)
        if owner_user_id == "legacy_admin":
            raise ValueError(
                "Legacy admin cannot create VaultSpaces. "
                "Please create a regular user account."
            )

        owner = (
            db.session.query(User).filter_by(id=owner_user_id, is_active=True).first()
        )
        if not owner:
            raise ValueError(f"User {owner_user_id} not found")

        # Validate vaultspace name (format and duplicates)
        self._validate_vaultspace_name(name)

        # Validate icon_name if provided
        if icon_name is not None:
            if not is_valid_icon_name(icon_name):
                raise ValueError(
                    f"Invalid icon name: {icon_name}. Must be a valid SVG icon name."
                )

        vaultspace = VaultSpace(
            name=name,
            type=VaultSpaceType.PERSONAL,
            owner_user_id=owner_user_id,
            encrypted_metadata=encrypted_metadata,
            icon_name=icon_name,
        )

        db.session.add(vaultspace)
        db.session.commit()

        return vaultspace

    def get_vaultspace(self, vaultspace_id: str) -> VaultSpace | None:
        """Get VaultSpace by ID.

        Args:
            vaultspace_id: VaultSpace ID

        Returns:
            VaultSpace object if found, None otherwise
        """
        return db.session.query(VaultSpace).filter_by(id=vaultspace_id).first()

    def list_vaultspaces(self, user_id: str) -> list[VaultSpace]:
        """List VaultSpaces owned by a user.

        Args:
            user_id: User ID

        Returns:
            List of VaultSpace objects
        """
        # Legacy admin has no VaultSpaces in database
        if user_id == "legacy_admin":
            return []

        return (
            db.session.query(VaultSpace)
            .filter_by(owner_user_id=user_id, type=VaultSpaceType.PERSONAL)
            .all()
        )

    def store_vaultspace_key_for_user(
        self,
        vaultspace_id: str,
        user_id: str,
        encrypted_key: str,
    ) -> VaultSpaceKey:
        """Store encrypted VaultSpace key for a user.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID (must be the owner)
            encrypted_key: VaultSpace key encrypted for the user

        Returns:
            Created or updated VaultSpaceKey object

        Raises:
            ValueError: If VaultSpace not found, user not found, or user is not the owner
        """
        vaultspace = self.get_vaultspace(vaultspace_id)
        if not vaultspace:
            raise ValueError(f"VaultSpace {vaultspace_id} not found")

        # Legacy admin cannot store VaultSpace keys (no DB user)
        if user_id == "legacy_admin":
            raise ValueError(
                "Legacy admin cannot store VaultSpace keys. "
                "Please create a regular user account."
            )

        # Verify user is the owner
        if vaultspace.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} is not the owner of VaultSpace {vaultspace_id}"
            )

        user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check if key already exists
        existing = (
            db.session.query(VaultSpaceKey)
            .filter_by(vaultspace_id=vaultspace_id, user_id=user_id)
            .first()
        )

        if existing:
            # Update existing key
            existing.encrypted_key = encrypted_key
            db.session.commit()
            return existing

        # Create new key
        vaultspace_key = VaultSpaceKey(
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            encrypted_key=encrypted_key,
        )
        db.session.add(vaultspace_key)
        db.session.commit()

        return vaultspace_key

    def get_vaultspace_key(
        self,
        vaultspace_id: str,
        user_id: str,
    ) -> VaultSpaceKey | None:
        """Get encrypted VaultSpace key for a user.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID

        Returns:
            VaultSpaceKey object if found, None otherwise
        """
        return (
            db.session.query(VaultSpaceKey)
            .filter_by(vaultspace_id=vaultspace_id, user_id=user_id)
            .first()
        )

    def update_vaultspace(
        self,
        vaultspace_id: str,
        name: str | None = None,
        encrypted_metadata: str | None = None,
        icon_name: str | None = None,
    ) -> VaultSpace | None:
        """Update VaultSpace metadata.

        Args:
            vaultspace_id: VaultSpace ID
            name: New name (optional)
            encrypted_metadata: New encrypted metadata (optional)
            icon_name: New icon name (optional, must be a valid SVG icon name, or None to clear)

        Returns:
            Updated VaultSpace object if found, None otherwise

        Raises:
            ValueError: If invalid icon name
        """
        vaultspace = self.get_vaultspace(vaultspace_id)
        if not vaultspace:
            return None

        if name is not None:
            # Validate vaultspace name (format and duplicates, excluding current vaultspace)
            self._validate_vaultspace_name(name, exclude_vaultspace_id=vaultspace_id)
            vaultspace.name = name
        if encrypted_metadata is not None:
            vaultspace.encrypted_metadata = encrypted_metadata
        if icon_name is not None:
            # Validate icon_name if provided (allow None to clear icon)
            if icon_name and not is_valid_icon_name(icon_name):
                raise ValueError(
                    f"Invalid icon name: {icon_name}. Must be a valid SVG icon name."
                )
            vaultspace.icon_name = icon_name

        db.session.commit()
        return vaultspace

    def delete_vaultspace(
        self,
        vaultspace_id: str,
        user_id: str,
    ) -> bool:
        """Delete a VaultSpace with permission check.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID requesting deletion

        Returns:
            True if deleted, False if not found or permission denied

        Raises:
            ValueError: If user doesn't have permission to delete
        """
        vaultspace = self.get_vaultspace(vaultspace_id)
        if not vaultspace:
            return False

        # Check permissions: only owner can delete
        if vaultspace.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to delete VaultSpace {vaultspace_id}"
            )

        # Get storage service to delete physical files
        from vault.storage import FileStorage
        from flask import current_app

        storage = current_app.config.get("VAULT_STORAGE")

        # Delete all associated files (including from storage)
        files = db.session.query(File).filter_by(vaultspace_id=vaultspace_id).all()
        for file in files:
            # Delete from storage if it's not a folder and has storage_ref
            if (
                storage
                and file.mime_type != "application/x-directory"
                and file.storage_ref
            ):
                try:
                    storage.delete_file(file.storage_ref)
                except Exception as e:
                    # Continue even if storage deletion fails, but log the error
                    logger.warning(
                        f"Failed to delete storage file {file.storage_ref}: {e}"
                    )
            # Delete from database (cascade will handle FileKeys)
            db.session.delete(file)

        # Delete all VaultSpaceKeys (cascade will handle)
        vaultspace_keys = self.encryption_service.get_all_vaultspace_keys(vaultspace_id)
        for key in vaultspace_keys:
            db.session.delete(key)

        # Delete VaultSpace
        db.session.delete(vaultspace)
        db.session.commit()

        return True

    def get_vaultspace_keys(self, vaultspace_id: str) -> list[VaultSpaceKey]:
        """Get all encrypted VaultSpace keys for a VaultSpace.

        Args:
            vaultspace_id: VaultSpace ID

        Returns:
            List of VaultSpaceKey objects
        """
        return self.encryption_service.get_all_vaultspace_keys(vaultspace_id)
