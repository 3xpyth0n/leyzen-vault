"""Version service for file versioning with automatic version creation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vault.database.schema import File, FileVersion, db
from vault.services.file_service import AdvancedFileService


class VersionService:
    """Service for managing file versions."""

    def __init__(self):
        """Initialize version service."""
        self.file_service = AdvancedFileService()

    def create_version_on_upload(
        self,
        file_id: str,
        encrypted_hash: str,
        storage_ref: str,
        created_by: str,
        change_description: str | None = None,
    ) -> FileVersion:
        """Create a version when a file is uploaded or updated.

        Args:
            file_id: File ID
            encrypted_hash: Hash of encrypted file data
            storage_ref: Storage reference
            created_by: User ID creating version
            change_description: Optional description of changes

        Returns:
            Created FileVersion object
        """
        return self.file_service.create_version(
            file_id=file_id,
            encrypted_hash=encrypted_hash,
            storage_ref=storage_ref,
            created_by=created_by,
            branch_name="main",
            change_description=change_description,
        )

    def get_version_history(
        self,
        file_id: str,
        branch_name: str = "main",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get version history for a file.

        Args:
            file_id: File ID
            branch_name: Branch name (default: "main")
            limit: Maximum number of versions to return
            offset: Offset for pagination

        Returns:
            Dictionary with versions and metadata
        """
        # Get total count
        total_count = (
            db.session.query(FileVersion)
            .filter_by(file_id=file_id, branch_name=branch_name)
            .count()
        )

        # Get versions
        versions = (
            db.session.query(FileVersion)
            .filter_by(file_id=file_id, branch_name=branch_name)
            .order_by(FileVersion.version_number.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return {
            "versions": [v.to_dict() for v in versions],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
        }

    def get_version(self, version_id: str) -> FileVersion | None:
        """Get a specific version by ID.

        Args:
            version_id: Version ID

        Returns:
            FileVersion object if found, None otherwise
        """
        return db.session.query(FileVersion).filter_by(id=version_id).first()

    def restore_version(
        self,
        file_id: str,
        version_id: str,
        restored_by: str,
    ) -> File:
        """Restore a file to a previous version.

        This creates a new version with the same content as the restored version.

        Args:
            file_id: File ID
            version_id: Version ID to restore
            restored_by: User ID restoring the version

        Returns:
            Updated File object

        Raises:
            ValueError: If version not found or doesn't belong to file
        """
        version = self.get_version(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        if version.file_id != file_id:
            raise ValueError(f"Version {version_id} does not belong to file {file_id}")

        # Get file
        file_obj = db.session.query(File).filter_by(id=file_id).first()
        if not file_obj:
            raise ValueError(f"File {file_id} not found")

        # Update file to point to restored version's storage
        file_obj.storage_ref = version.storage_ref
        file_obj.encrypted_hash = version.encrypted_hash
        file_obj.updated_at = datetime.now(timezone.utc)

        # Create new version with restored content
        self.file_service.create_version(
            file_id=file_id,
            encrypted_hash=version.encrypted_hash,
            storage_ref=version.storage_ref,
            created_by=restored_by,
            branch_name=version.branch_name,
            change_description=f"Restored from version {version.version_number}",
            parent_version_id=version_id,
        )

        db.session.commit()
        return file_obj

    def delete_version(self, version_id: str, deleted_by: str) -> bool:
        """Delete a version (soft delete by marking as deleted).

        Note: We don't actually delete versions to maintain history.
        This method can be extended to mark versions as deleted.

        Args:
            version_id: Version ID
            deleted_by: User ID deleting the version

        Returns:
            True if version exists
        """
        version = self.get_version(version_id)
        if not version:
            return False

        # For now, we don't delete versions to maintain history
        # In the future, we could add a deleted_at field
        return True

    def cleanup_old_versions(
        self,
        file_id: str,
        keep_count: int = 10,
        branch_name: str = "main",
    ) -> int:
        """Clean up old versions, keeping only the most recent ones.

        Args:
            file_id: File ID
            keep_count: Number of versions to keep
            branch_name: Branch name

        Returns:
            Number of versions deleted
        """
        # Get versions ordered by version number (descending)
        versions = (
            db.session.query(FileVersion)
            .filter_by(file_id=file_id, branch_name=branch_name)
            .order_by(FileVersion.version_number.desc())
            .all()
        )

        if len(versions) <= keep_count:
            return 0

        # Delete old versions (keep the most recent keep_count)
        versions_to_delete = versions[keep_count:]
        deleted_count = 0

        for version in versions_to_delete:
            # Delete from storage if needed
            # (storage cleanup can be handled separately)
            db.session.delete(version)
            deleted_count += 1

        db.session.commit()
        return deleted_count

    def compare_versions(
        self,
        version1_id: str,
        version2_id: str,
    ) -> dict[str, Any]:
        """Compare two versions.

        Args:
            version1_id: First version ID
            version2_id: Second version ID

        Returns:
            Dictionary with comparison results
        """
        version1 = self.get_version(version1_id)
        version2 = self.get_version(version2_id)

        if not version1 or not version2:
            raise ValueError("One or both versions not found")

        if version1.file_id != version2.file_id:
            raise ValueError("Versions belong to different files")

        return {
            "version1": version1.to_dict(),
            "version2": version2.to_dict(),
            "same_hash": version1.encrypted_hash == version2.encrypted_hash,
            "version_diff": version2.version_number - version1.version_number,
        }
