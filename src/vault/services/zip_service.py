"""Service for ZIP folder operations."""

from __future__ import annotations

import logging
from typing import Any

from vault.database.schema import File, FileKey, db
from vault.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)


class ZipService:
    """Service for managing ZIP folder operations."""

    def __init__(self):
        """Initialize ZIP service."""
        self.encryption_service = EncryptionService()

    def get_folder_tree(
        self, folder_id: str, vaultspace_id: str, user_id: str, base_path: str = ""
    ) -> dict[str, Any]:
        """Recursively get all files and folders in a folder with their metadata and encrypted keys.

        Args:
            folder_id: Folder ID to get tree for
            vaultspace_id: VaultSpace ID
            user_id: User ID requesting the tree
            base_path: Base path for relative paths in ZIP (used for recursion)

        Returns:
            Dictionary with:
                - files: List of file dicts with id, name, path, encrypted_key, size, etc.
                - folders: List of folder dicts with id, name, path, etc.
                - folder_name: Name of the root folder

        Raises:
            ValueError: If folder not found or user doesn't have permission
        """
        folder_obj = db.session.query(File).filter_by(id=folder_id).first()
        if not folder_obj:
            raise ValueError(f"Folder {folder_id} not found")

        if folder_obj.mime_type != "application/x-directory":
            raise ValueError(f"File {folder_id} is not a folder")

        if folder_obj.vaultspace_id != vaultspace_id:
            raise ValueError(
                f"Folder {folder_id} does not belong to VaultSpace {vaultspace_id}"
            )

        # Check permissions: only owner can zip
        if folder_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to zip folder {folder_id}"
            )

        files_list = []
        folders_list = []

        # Get all direct children
        children = (
            db.session.query(File)
            .filter_by(
                vaultspace_id=vaultspace_id, parent_id=folder_id, deleted_at=None
            )
            .all()
        )

        for child in children:
            # Build relative path for ZIP structure
            relative_path = (
                f"{base_path}/{child.original_name}"
                if base_path
                else child.original_name
            )

            if child.mime_type == "application/x-directory":
                # Recursively get subfolder contents
                subfolder_data = self.get_folder_tree(
                    child.id, vaultspace_id, user_id, relative_path
                )
                # Add subfolder itself
                folders_list.append(
                    {
                        "id": child.id,
                        "name": child.original_name,
                        "path": relative_path,
                        "created_at": child.created_at.isoformat(),
                    }
                )
                # Add subfolder's files and folders
                files_list.extend(subfolder_data["files"])
                folders_list.extend(subfolder_data["folders"])
            else:
                # Get encrypted file key
                file_key = self.encryption_service.get_file_key(child.id, vaultspace_id)
                if not file_key:
                    logger.warning(f"FileKey not found for file {child.id}, skipping")
                    continue

                files_list.append(
                    {
                        "id": child.id,
                        "name": child.original_name,
                        "path": relative_path,
                        "encrypted_key": file_key.encrypted_key,
                        "size": child.size,
                        "encrypted_size": child.encrypted_size,
                        "mime_type": child.mime_type,
                        "created_at": child.created_at.isoformat(),
                    }
                )

        return {
            "files": files_list,
            "folders": folders_list,
            "folder_name": folder_obj.original_name,
        }
