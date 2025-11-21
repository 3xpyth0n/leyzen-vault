"""Service for reconciling database file records with physical storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Set

from vault.database.schema import File, db

logger = logging.getLogger(__name__)


class StorageReconciliationService:
    """Reconciles database file records with physical storage.

    This service helps identify and clean up orphaned files - files that exist
    on disk but have no corresponding database records. This can happen when:
    - File deletion fails partially (DB updated but disk cleanup failed)
    - Unexpected errors during file operations
    - Manual file manipulation
    """

    def __init__(self, storage):
        """Initialize with storage instance.

        Args:
            storage: FileStorage instance
        """
        self.storage = storage

    def get_database_file_ids(self) -> Set[str]:
        """Get all file storage_ref values from database (non-deleted files only).

        Only includes files that:
        - Have not been soft-deleted (deleted_at is NULL)
        - Have a valid storage_ref (not NULL or empty)
        - Are not folders (folders don't have physical files)

        Returns:
            Set of storage_ref values
        """
        files = (
            db.session.query(File.storage_ref)
            .filter(
                File.deleted_at.is_(None),
                File.storage_ref.isnot(None),
                File.storage_ref != "",  # Exclude folders
                File.mime_type != "application/x-directory",  # Exclude folders
            )
            .all()
        )
        return {f.storage_ref for f in files if f.storage_ref}

    def get_physical_file_ids(self, directory: Path) -> Set[str]:
        """Get all file IDs from physical storage directory.

        Args:
            directory: Storage directory (e.g., /data or /data-source)

        Returns:
            Set of file IDs (filenames in the files/ subdirectory)
        """
        files_dir = directory / "files"
        if not files_dir.exists():
            return set()

        # List all files (exclude directories and hidden files)
        return {
            f.name
            for f in files_dir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        }

    def find_orphaned_files(self) -> dict:
        """Find orphaned files in both storage locations.

        Orphaned files are files that exist on disk but have no corresponding
        active database record.

        Returns:
            Dictionary with orphan sets and statistics:
            {
                "primary": set of orphaned file IDs in primary storage,
                "source": set of orphaned file IDs in source storage,
                "db_records": count of active files in database,
                "primary_files": count of physical files in primary storage,
                "source_files": count of physical files in source storage
            }
        """
        db_file_ids = self.get_database_file_ids()

        # Check primary storage
        primary_file_ids = self.get_physical_file_ids(self.storage.storage_dir)
        primary_orphans = primary_file_ids - db_file_ids

        # Check source storage
        source_orphans = set()
        source_file_count = 0
        if self.storage.source_dir:
            source_file_ids = self.get_physical_file_ids(self.storage.source_dir)
            source_orphans = source_file_ids - db_file_ids
            source_file_count = len(source_file_ids)

        return {
            "primary": primary_orphans,
            "source": source_orphans,
            "db_records": len(db_file_ids),
            "primary_files": len(primary_file_ids),
            "source_files": source_file_count,
        }

    def cleanup_orphaned_files(self, dry_run: bool = True) -> dict:
        """Remove orphaned files from storage.

        Args:
            dry_run: If True, only report what would be deleted without deleting

        Returns:
            Dictionary with cleanup results:
            {
                "dry_run": bool,
                "deleted_primary": list of deleted file IDs from primary storage,
                "deleted_source": list of deleted file IDs from source storage,
                "failed": list of failed deletions with error details,
                "stats": orphan statistics from find_orphaned_files()
            }
        """
        orphans = self.find_orphaned_files()

        deleted_primary = []
        deleted_source = []
        failed = []

        # Clean primary storage
        for file_id in orphans["primary"]:
            if dry_run:
                deleted_primary.append(file_id)
            else:
                try:
                    file_path = self.storage.storage_dir / "files" / file_id
                    if file_path.exists():
                        file_path.unlink()
                        deleted_primary.append(file_id)
                        logger.info(
                            f"Deleted orphaned file from primary storage: {file_id}"
                        )
                except Exception as e:
                    failed.append(
                        {"file_id": file_id, "location": "primary", "error": str(e)}
                    )
                    logger.error(
                        f"Failed to delete {file_id} from primary storage: {e}"
                    )

        # Clean source storage
        if self.storage.source_dir:
            for file_id in orphans["source"]:
                if dry_run:
                    deleted_source.append(file_id)
                else:
                    try:
                        file_path = self.storage.source_dir / "files" / file_id
                        if file_path.exists():
                            file_path.unlink()
                            deleted_source.append(file_id)
                            logger.info(
                                f"Deleted orphaned file from source storage: {file_id}"
                            )
                    except Exception as e:
                        failed.append(
                            {"file_id": file_id, "location": "source", "error": str(e)}
                        )
                        logger.error(
                            f"Failed to delete {file_id} from source storage: {e}"
                        )

        return {
            "dry_run": dry_run,
            "deleted_primary": deleted_primary,
            "deleted_source": deleted_source,
            "failed": failed,
            "stats": orphans,
        }
