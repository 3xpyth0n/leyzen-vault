"""Service for synchronizing files between local storage and external S3 storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from vault.services.external_storage_service import ExternalStorageService
from vault.storage import FileStorage

logger = logging.getLogger(__name__)


class ExternalStorageSyncService:
    """Service for synchronizing files between local and S3 storage (hybrid mode only)."""

    def __init__(
        self,
        local_storage: FileStorage,
        external_storage: ExternalStorageService,
    ):
        """Initialize sync service.

        Args:
            local_storage: Local FileStorage instance
            external_storage: ExternalStorageService instance
        """
        self.local_storage = local_storage
        self.external_storage = external_storage

    def sync_file_to_s3(self, file_id: str) -> tuple[bool, str | None]:
        """Sync a file from local storage to S3.

        Args:
            file_id: File identifier

        Returns:
            Tuple of (success, error_message). If successful, error_message is None.
        """
        try:
            # Check if file exists in local storage
            if not self.local_storage.file_exists(file_id):
                return False, f"File {file_id} not found in local storage"

            # Read file from local storage
            try:
                encrypted_data = self.local_storage.read_file(file_id)
            except FileNotFoundError:
                return False, f"File {file_id} not found in local storage"

            # Upload to S3
            try:
                s3_key = self.external_storage.save_file(file_id, encrypted_data)
                logger.info(f"Successfully synced file {file_id} to S3")
                return True, None
            except Exception as e:
                error_msg = f"Failed to upload file {file_id} to S3: {e}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error syncing file {file_id} to S3: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def restore_file_from_s3(
        self, file_id: str, write_to_local: bool = True
    ) -> tuple[bool, str | None]:
        """Restore a file from S3 to local storage.

        Args:
            file_id: File identifier
            write_to_local: If True, write to local storage after download

        Returns:
            Tuple of (success, error_message). If successful, error_message is None.
        """
        try:
            # Check if file exists in S3
            if not self.external_storage.file_exists(file_id):
                return False, f"File {file_id} not found in S3"

            # Download from S3
            try:
                encrypted_data = self.external_storage.read_file(file_id)
            except FileNotFoundError:
                return False, f"File {file_id} not found in S3"
            except Exception as e:
                return False, f"Failed to download file {file_id} from S3: {e}"

            # Write to local storage if requested
            if write_to_local:
                try:
                    # Use source_dir if available, otherwise use storage_dir
                    if self.local_storage.source_dir:
                        target_dir = self.local_storage.source_dir / "files"
                    else:
                        target_dir = self.local_storage.storage_dir / "files"

                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / file_id

                    # Write file atomically
                    temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
                    temp_path.write_bytes(encrypted_data)
                    temp_path.rename(target_path)

                    logger.info(
                        f"Successfully restored file {file_id} from S3 to local storage"
                    )
                except Exception as e:
                    error_msg = f"Failed to write file {file_id} to local storage: {e}"
                    logger.error(error_msg)
                    return False, error_msg

            return True, None

        except Exception as e:
            error_msg = f"Unexpected error restoring file {file_id} from S3: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def get_s3_file_timestamp(self, file_id: str) -> datetime | None:
        """Get the LastModified timestamp of a file in S3.

        Args:
            file_id: File identifier (storage_ref)

        Returns:
            datetime object with LastModified timestamp, or None if file doesn't exist
        """
        try:
            metadata = self.external_storage.get_file_metadata(file_id)
            if not metadata:
                logger.warning(
                    f"get_s3_file_timestamp: No metadata returned for {file_id} (file may not exist in S3)"
                )
                return None

            # Check for LastModified (native S3 metadata) first
            last_modified = metadata.get("LastModified")

            # If LastModified is not found, check if we have custom metadata with last_modified (lowercase)
            # Some S3-compatible services store last_modified in custom metadata instead of native LastModified
            if last_modified is None:
                # Try to get from custom metadata (fallback for S3-compatible services)
                custom_last_modified = metadata.get("last_modified")
                if custom_last_modified:
                    logger.debug(
                        f"get_s3_file_timestamp: Using custom 'last_modified' for {file_id} instead of native LastModified"
                    )
                    # Try to parse if it's a string
                    if isinstance(custom_last_modified, str):
                        try:
                            from dateutil import parser

                            last_modified = parser.parse(custom_last_modified)
                            # Ensure timezone-aware
                            if last_modified.tzinfo is None:
                                last_modified = last_modified.replace(
                                    tzinfo=timezone.utc
                                )
                        except Exception as e:
                            logger.warning(
                                f"get_s3_file_timestamp: Could not parse custom last_modified string for {file_id}: {custom_last_modified}, error: {e}"
                            )
                    elif isinstance(custom_last_modified, datetime):
                        last_modified = custom_last_modified
                        # Ensure timezone-aware
                        if last_modified.tzinfo is None:
                            last_modified = last_modified.replace(tzinfo=timezone.utc)

            if last_modified is None:
                logger.warning(
                    f"get_s3_file_timestamp: LastModified is None in metadata for {file_id}, metadata keys: {list(metadata.keys()) if metadata else 'metadata is None'}, full metadata: {metadata}"
                )
                return None

            # LastModified from S3 is already timezone-aware
            if isinstance(last_modified, datetime):
                return last_modified
            # If it's a string, parse it (shouldn't happen with boto3, but just in case)
            logger.warning(
                f"get_s3_file_timestamp: LastModified is not a datetime object for {file_id}, type: {type(last_modified)}, value: {last_modified}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Error getting S3 timestamp for file {file_id}: {e}", exc_info=True
            )
            return None

    def get_local_file_timestamp(self, file_id: str) -> datetime | None:
        """Get the modification timestamp of a file in local storage.

        Args:
            file_id: File identifier (storage_ref)

        Returns:
            datetime object with modification timestamp, or None if file doesn't exist
        """
        try:
            # Try to get file path
            storage_path = self.local_storage.get_file_path(file_id)
            if storage_path.exists():
                mtime = storage_path.stat().st_mtime
                return datetime.fromtimestamp(mtime, tz=timezone.utc)
            # Try source path if storage path doesn't exist
            if self.local_storage.source_dir:
                source_path = self.local_storage.get_source_file_path(file_id)
                if source_path.exists():
                    mtime = source_path.stat().st_mtime
                    return datetime.fromtimestamp(mtime, tz=timezone.utc)
            logger.warning(
                f"get_local_file_timestamp: File {file_id} not found in local storage (checked: storage={storage_path}, source={self.local_storage.get_source_file_path(file_id) if self.local_storage.source_dir else 'N/A'})"
            )
            return None
        except FileNotFoundError:
            logger.warning(f"get_local_file_timestamp: FileNotFoundError for {file_id}")
            return None
        except Exception as e:
            logger.warning(
                f"Error getting local timestamp for file {file_id}: {e}", exc_info=True
            )
            return None

    def sync_file_from_s3(self, storage_ref: str) -> tuple[bool, str | None]:
        """Sync a file from S3 to local storage.

        Args:
            storage_ref: File storage reference (actual filename on disk)

        Returns:
            Tuple of (success, error_message). If successful, error_message is None.
        """
        try:
            # Check if file exists in S3
            if not self.external_storage.file_exists(storage_ref):
                return False, f"File {storage_ref} not found in S3"

            # Download from S3
            try:
                encrypted_data = self.external_storage.read_file(storage_ref)
            except FileNotFoundError:
                return False, f"File {storage_ref} not found in S3"
            except Exception as e:
                return False, f"Failed to download file {storage_ref} from S3: {e}"

            # Write to local storage - prioritize source_dir (persistent storage)
            try:
                if self.local_storage.source_dir:
                    target_dir = self.local_storage.source_dir / "files"
                else:
                    target_dir = self.local_storage.storage_dir / "files"

                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / storage_ref

                # Write file atomically
                temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
                temp_path.write_bytes(encrypted_data)
                temp_path.rename(target_path)

                logger.info(
                    f"Successfully synced file {storage_ref} from S3 to local storage"
                )
                return True, None
            except Exception as e:
                error_msg = f"Failed to write file {storage_ref} to local storage: {e}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error syncing file {storage_ref} from S3: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def sync_recent_files(self, days: int = 7, max_files: int = 100) -> dict[str, Any]:
        """Auto-restore recent files from S3 if missing locally.

        Args:
            days: Number of days to consider "recent" (default: 7)
            max_files: Maximum number of files to restore (default: 100)

        Returns:
            Dictionary with sync statistics
        """
        # This would require database access to find recent files
        # For now, return empty stats
        # TODO: Implement database query to find recent files missing locally
        return {
            "restored": [],
            "failed": [],
            "restored_count": 0,
            "failed_count": 0,
        }

    def sync_all_files_bidirectional(self) -> dict[str, Any]:
        """Sync all files bidirectionally between local and S3.

        This method must be called within a Flask application context.

        For each file in database:
        - If exists locally but not in S3: upload to S3
        - If exists in S3 but not locally: download from S3
        - If exists in both: compare timestamps, sync newer version
        - If exists in neither: file is orphaned (handled by cleanup)

        Returns:
            Dictionary with sync statistics
        """
        synced_to_s3: list[str] = []
        synced_from_s3: list[str] = []
        skipped: list[str] = []
        failed: list[tuple[str, str]] = []

        try:
            from vault.database.schema import File, db

            # Get all non-deleted files from database
            all_files = (
                db.session.query(File)
                .filter(File.deleted_at.is_(None))
                .filter(File.mime_type != "application/x-directory")
                .all()
            )
            logger.info(f"[SYNC] Found {len(all_files)} files in database to sync")

            if len(all_files) == 0:
                logger.warning("[SYNC] No files found in database to sync")
                return {
                    "synced_to_s3": [],
                    "synced_from_s3": [],
                    "skipped": [],
                    "failed": [],
                    "synced_to_s3_count": 0,
                    "synced_from_s3_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                }

            # Process each file
            for file_obj in all_files:
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                if not storage_ref:
                    logger.warning(
                        f"[SYNC] File {file_id} has no storage_ref, skipping"
                    )
                    skipped.append(file_id)
                    continue

                try:
                    # Check existence in local storage
                    exists_local = False
                    try:
                        self.local_storage.read_file(storage_ref)
                        exists_local = True
                    except FileNotFoundError:
                        exists_local = False

                    # Check existence in S3
                    exists_s3 = self.external_storage.file_exists(storage_ref)

                    # Determine sync action based on existence
                    if exists_local and not exists_s3:
                        # Local only: upload to S3
                        logger.info(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists locally only, uploading to S3..."
                        )
                        success, error_msg = self.sync_file_to_s3(storage_ref)
                        if success:
                            synced_to_s3.append(file_id)
                            logger.info(
                                f"[SYNC] Successfully uploaded file {file_id} (storage_ref: {storage_ref}) to S3"
                            )
                        else:
                            failed.append((file_id, error_msg or "Unknown error"))
                            logger.warning(
                                f"[SYNC] Failed to upload file {file_id} (storage_ref: {storage_ref}): {error_msg}"
                            )

                    elif exists_s3 and not exists_local:
                        # S3 only: download from S3
                        logger.info(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists in S3 only, downloading to local..."
                        )
                        success, error_msg = self.sync_file_from_s3(storage_ref)
                        if success:
                            synced_from_s3.append(file_id)
                            logger.info(
                                f"[SYNC] Successfully downloaded file {file_id} (storage_ref: {storage_ref}) from S3"
                            )
                        else:
                            failed.append((file_id, error_msg or "Unknown error"))
                            logger.warning(
                                f"[SYNC] Failed to download file {file_id} (storage_ref: {storage_ref}): {error_msg}"
                            )

                    elif exists_local and exists_s3:
                        # Both exist: compare timestamps
                        s3_timestamp = self.get_s3_file_timestamp(storage_ref)
                        local_timestamp = self.get_local_file_timestamp(storage_ref)

                        # Warning logging if timestamps are missing
                        if not s3_timestamp:
                            logger.warning(
                                f"[SYNC] Could not get S3 timestamp for file {file_id} (storage_ref: {storage_ref})"
                            )
                        if not local_timestamp:
                            logger.warning(
                                f"[SYNC] Could not get local timestamp for file {file_id} (storage_ref: {storage_ref})"
                            )

                        if s3_timestamp and local_timestamp:
                            # Calculate time difference
                            time_diff = abs(
                                (s3_timestamp - local_timestamp).total_seconds()
                            )

                            # If difference is less than 5 seconds, consider them identical
                            if time_diff < 5:
                                logger.debug(
                                    f"[SYNC] File {file_id} (storage_ref: {storage_ref}) is up to date (diff: {time_diff:.1f}s), skipping"
                                )
                                skipped.append(file_id)
                            elif s3_timestamp > local_timestamp:
                                # S3 is newer: download from S3
                                logger.info(
                                    f"[SYNC] File {file_id} (storage_ref: {storage_ref}) is newer in S3 (diff: {time_diff:.1f}s), downloading..."
                                )
                                success, error_msg = self.sync_file_from_s3(storage_ref)
                                if success:
                                    synced_from_s3.append(file_id)
                                    logger.info(
                                        f"[SYNC] Successfully updated file {file_id} (storage_ref: {storage_ref}) from S3"
                                    )
                                else:
                                    failed.append(
                                        (file_id, error_msg or "Unknown error")
                                    )
                                    logger.warning(
                                        f"[SYNC] Failed to update file {file_id} (storage_ref: {storage_ref}) from S3: {error_msg}"
                                    )
                            else:
                                # Local is newer: upload to S3
                                logger.info(
                                    f"[SYNC] File {file_id} (storage_ref: {storage_ref}) is newer locally (diff: {time_diff:.1f}s), uploading..."
                                )
                                success, error_msg = self.sync_file_to_s3(storage_ref)
                                if success:
                                    synced_to_s3.append(file_id)
                                    logger.info(
                                        f"[SYNC] Successfully updated file {file_id} (storage_ref: {storage_ref}) to S3"
                                    )
                                else:
                                    failed.append(
                                        (file_id, error_msg or "Unknown error")
                                    )
                                    logger.warning(
                                        f"[SYNC] Failed to update file {file_id} (storage_ref: {storage_ref}) to S3: {error_msg}"
                                    )
                        else:
                            # Could not get timestamps, skip
                            logger.warning(
                                f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists in both but could not compare timestamps, skipping"
                            )
                            skipped.append(file_id)

                    else:
                        # Neither exists: file is orphaned
                        logger.warning(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists in neither local nor S3, will be cleaned up"
                        )
                        skipped.append(file_id)

                except Exception as e:
                    error_msg = f"Error processing file {file_id}: {e}"
                    failed.append((file_id, error_msg))
                    logger.error(f"[SYNC] {error_msg}", exc_info=True)

            logger.info(
                f"[SYNC] Sync completed: {len(synced_to_s3)} uploaded to S3, {len(synced_from_s3)} downloaded from S3, "
                f"{len(skipped)} skipped, {len(failed)} failed"
            )

            # Clean up orphaned database entries (files in DB that don't exist on disk or S3)
            orphaned_files = [
                file_id
                for file_id in skipped
                if file_id not in synced_to_s3 and file_id not in synced_from_s3
            ]
            if orphaned_files:
                logger.info(
                    f"[SYNC] Cleaning up {len(orphaned_files)} orphaned database entries..."
                )
                cleanup_results = self.cleanup_orphaned_database_entries()
                logger.info(
                    f"[SYNC] Cleanup completed: {cleanup_results['cleaned_count']} files deleted, "
                    f"{cleanup_results['failed_count']} failed"
                )
        except Exception as e:
            logger.error(f"Error in sync_all_files_bidirectional: {e}", exc_info=True)
            return {
                "synced_to_s3": [],
                "synced_from_s3": [],
                "skipped": [],
                "failed": [("all", str(e))],
                "synced_to_s3_count": 0,
                "synced_from_s3_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
            }

        return {
            "synced_to_s3": synced_to_s3,
            "synced_from_s3": synced_from_s3,
            "skipped": skipped,
            "failed": failed,
            "synced_to_s3_count": len(synced_to_s3),
            "synced_from_s3_count": len(synced_from_s3),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        }

    def sync_all_files_to_s3(self) -> dict[str, Any]:
        """Sync all files from local storage to S3, overwriting S3 content.

        This method must be called within a Flask application context.

        For each file in database:
        - If exists locally: upload to S3 (overwriting if exists in S3)
        - If doesn't exist locally: skip

        Returns:
            Dictionary with sync statistics
        """
        synced_to_s3: list[str] = []
        skipped: list[str] = []
        failed: list[tuple[str, str]] = []

        try:
            from vault.database.schema import File, db

            # Get all non-deleted files from database
            all_files = (
                db.session.query(File)
                .filter(File.deleted_at.is_(None))
                .filter(File.mime_type != "application/x-directory")
                .all()
            )
            logger.info(
                f"[SYNC] Found {len(all_files)} files in database to sync to S3"
            )

            if len(all_files) == 0:
                logger.warning("[SYNC] No files found in database to sync to S3")
                return {
                    "synced_to_s3": [],
                    "skipped": [],
                    "failed": [],
                    "synced_to_s3_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                }

            # Process each file
            for file_obj in all_files:
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                if not storage_ref:
                    logger.warning(
                        f"[SYNC] File {file_id} has no storage_ref, skipping"
                    )
                    skipped.append(file_id)
                    continue

                try:
                    # Check existence in local storage
                    exists_local = False
                    try:
                        self.local_storage.read_file(storage_ref)
                        exists_local = True
                    except FileNotFoundError:
                        exists_local = False

                    if exists_local:
                        # File exists locally: upload to S3 (overwrite if exists)
                        logger.info(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists locally, uploading to S3 (overwrite)..."
                        )
                        success, error_msg = self.sync_file_to_s3(storage_ref)
                        if success:
                            synced_to_s3.append(file_id)
                            logger.info(
                                f"[SYNC] Successfully uploaded file {file_id} (storage_ref: {storage_ref}) to S3"
                            )
                        else:
                            failed.append((file_id, error_msg or "Unknown error"))
                            logger.warning(
                                f"[SYNC] Failed to upload file {file_id} (storage_ref: {storage_ref}): {error_msg}"
                            )
                    else:
                        # File doesn't exist locally: skip
                        logger.debug(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) doesn't exist locally, skipping"
                        )
                        skipped.append(file_id)

                except Exception as e:
                    error_msg = f"Error processing file {file_id}: {e}"
                    failed.append((file_id, error_msg))
                    logger.error(f"[SYNC] {error_msg}", exc_info=True)

            logger.info(
                f"[SYNC] Sync to S3 completed: {len(synced_to_s3)} uploaded to S3, "
                f"{len(skipped)} skipped, {len(failed)} failed"
            )
        except Exception as e:
            logger.error(f"Error in sync_all_files_to_s3: {e}", exc_info=True)
            return {
                "synced_to_s3": [],
                "skipped": [],
                "failed": [("all", str(e))],
                "synced_to_s3_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
            }

        return {
            "synced_to_s3": synced_to_s3,
            "skipped": skipped,
            "failed": failed,
            "synced_to_s3_count": len(synced_to_s3),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        }

    def sync_all_files_from_s3(self) -> dict[str, Any]:
        """Sync all files from S3 to local storage, overwriting local content.

        This method must be called within a Flask application context.

        For each file in database:
        - If exists in S3: download to local (overwriting if exists locally)
        - If doesn't exist in S3: skip

        Returns:
            Dictionary with sync statistics
        """
        synced_from_s3: list[str] = []
        skipped: list[str] = []
        failed: list[tuple[str, str]] = []

        try:
            from vault.database.schema import File, db

            # Get all non-deleted files from database
            all_files = (
                db.session.query(File)
                .filter(File.deleted_at.is_(None))
                .filter(File.mime_type != "application/x-directory")
                .all()
            )
            logger.info(
                f"[SYNC] Found {len(all_files)} files in database to sync from S3"
            )

            if len(all_files) == 0:
                logger.warning("[SYNC] No files found in database to sync from S3")
                return {
                    "synced_from_s3": [],
                    "skipped": [],
                    "failed": [],
                    "synced_from_s3_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                }

            # Process each file
            for file_obj in all_files:
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                if not storage_ref:
                    logger.warning(
                        f"[SYNC] File {file_id} has no storage_ref, skipping"
                    )
                    skipped.append(file_id)
                    continue

                try:
                    # Check existence in S3
                    exists_s3 = self.external_storage.file_exists(storage_ref)

                    if exists_s3:
                        # File exists in S3: download to local (overwrite if exists)
                        logger.info(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) exists in S3, downloading to local (overwrite)..."
                        )
                        success, error_msg = self.sync_file_from_s3(storage_ref)
                        if success:
                            synced_from_s3.append(file_id)
                            logger.info(
                                f"[SYNC] Successfully downloaded file {file_id} (storage_ref: {storage_ref}) from S3"
                            )
                        else:
                            failed.append((file_id, error_msg or "Unknown error"))
                            logger.warning(
                                f"[SYNC] Failed to download file {file_id} (storage_ref: {storage_ref}): {error_msg}"
                            )
                    else:
                        # File doesn't exist in S3: skip
                        logger.debug(
                            f"[SYNC] File {file_id} (storage_ref: {storage_ref}) doesn't exist in S3, skipping"
                        )
                        skipped.append(file_id)

                except Exception as e:
                    error_msg = f"Error processing file {file_id}: {e}"
                    failed.append((file_id, error_msg))
                    logger.error(f"[SYNC] {error_msg}", exc_info=True)

            logger.info(
                f"[SYNC] Sync from S3 completed: {len(synced_from_s3)} downloaded from S3, "
                f"{len(skipped)} skipped, {len(failed)} failed"
            )
        except Exception as e:
            logger.error(f"Error in sync_all_files_from_s3: {e}", exc_info=True)
            return {
                "synced_from_s3": [],
                "skipped": [],
                "failed": [("all", str(e))],
                "synced_from_s3_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
            }

        return {
            "synced_from_s3": synced_from_s3,
            "skipped": skipped,
            "failed": failed,
            "synced_from_s3_count": len(synced_from_s3),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        }

    def sync_all_pending_files(self) -> dict[str, Any]:
        """Sync all pending files from local to S3.

        This method is kept for backward compatibility.
        It now calls sync_all_files_bidirectional().

        This method must be called within a Flask application context.

        Returns:
            Dictionary with sync statistics
        """
        # Call bidirectional sync for backward compatibility
        results = self.sync_all_files_bidirectional()
        # Map results to old format
        return {
            "synced": results["synced_to_s3"] + results["synced_from_s3"],
            "failed": results["failed"],
            "synced_count": results["synced_to_s3_count"]
            + results["synced_from_s3_count"],
            "failed_count": results["failed_count"],
        }

    def sync_deletions(self) -> dict[str, Any]:
        """Sync file deletions from local to S3.

        Returns:
            Dictionary with sync statistics
        """
        deleted: list[str] = []
        failed: list[tuple[str, str]] = []

        # This would require database access to find deleted files
        # For now, return empty stats
        # TODO: Implement database query to find deleted files that still exist in S3

        return {
            "deleted": deleted,
            "failed": failed,
            "deleted_count": len(deleted),
            "failed_count": len(failed),
        }

    def cleanup_orphaned_database_entries(self) -> dict[str, Any]:
        """Clean up database entries for files that no longer exist on disk.

        This method must be called within a Flask application context.

        Returns:
            Dictionary with cleanup statistics:
            {
                "cleaned": list[str],  # List of file IDs that were cleaned up
                "failed": list[tuple[str, str]],  # List of (file_id, error) tuples
                "cleaned_count": int,
                "failed_count": int
            }
        """
        cleaned: list[str] = []
        failed: list[tuple[str, str]] = []

        try:
            from vault.database.schema import File, db

            # Get all files from database (including those in trash, as they still have physical files)
            # We only check files that have a storage_ref and are not directories
            all_files = (
                db.session.query(File)
                .filter(File.mime_type != "application/x-directory")
                .filter(File.storage_ref.isnot(None))
                .all()
            )
            logger.info(
                f"[CLEANUP] Found {len(all_files)} non-deleted files in database to check"
            )

            if len(all_files) == 0:
                logger.info("[CLEANUP] No files to check")
                return {
                    "cleaned": [],
                    "failed": [],
                    "cleaned_count": 0,
                    "failed_count": 0,
                }

            # List all files on disk
            from pathlib import Path

            disk_files = set()
            storage_files_dir = self.local_storage.storage_dir / "files"
            if storage_files_dir.exists():
                for file_path in storage_files_dir.iterdir():
                    if file_path.is_file():
                        disk_files.add(file_path.name)

            if self.local_storage.source_dir:
                source_files_dir = self.local_storage.source_dir / "files"
                if source_files_dir.exists():
                    for file_path in source_files_dir.iterdir():
                        if file_path.is_file():
                            disk_files.add(file_path.name)

            logger.info(
                f"[CLEANUP] Found {len(disk_files)} files on disk, {len(all_files)} files in database"
            )

            # Find files in database that don't exist on disk
            # Use multiple verification methods to ensure file really doesn't exist
            orphaned_count = 0
            for file_obj in all_files:
                file_id = file_obj.id
                storage_ref = file_obj.storage_ref

                if not storage_ref:
                    logger.warning(
                        f"[CLEANUP] File {file_id} has no storage_ref, skipping"
                    )
                    continue

                # First check: verify storage_ref is not in the disk_files set
                if storage_ref not in disk_files:
                    # Second check: try to read the file using local_storage.read_file()
                    # This will check both storage_dir and source_dir
                    file_really_missing = False
                    try:
                        self.local_storage.read_file(storage_ref)
                        # File exists! Don't delete, log warning
                        logger.warning(
                            f"[CLEANUP] File {file_id} (storage_ref: {storage_ref}) found via read_file() "
                            f"but not in disk_files set - skipping deletion (possible mapping issue)"
                        )
                        continue
                    except FileNotFoundError:
                        # File really doesn't exist, proceed with deletion
                        file_really_missing = True
                    except Exception as e:
                        # Unexpected error reading file - don't delete, log error
                        logger.error(
                            f"[CLEANUP] Error verifying file {file_id} (storage_ref: {storage_ref}): {e} - skipping deletion"
                        )
                        failed.append((file_id, f"Error verifying file: {e}"))
                        continue

                    if file_really_missing:
                        # Third check: verify paths directly
                        from pathlib import Path

                        storage_path = self.local_storage.get_file_path(storage_ref)
                        source_path = (
                            self.local_storage.get_source_file_path(storage_ref)
                            if self.local_storage.source_dir
                            else None
                        )

                        # Verify both paths don't exist
                        if storage_path.exists() or (
                            source_path and source_path.exists()
                        ):
                            logger.warning(
                                f"[CLEANUP] File {file_id} (storage_ref: {storage_ref}) found at path "
                                f"but not in disk_files set - skipping deletion (possible mapping issue)"
                            )
                            continue

                        # All checks passed - file really doesn't exist, safe to delete
                        try:
                            # Delete the file completely (hard delete, not soft delete)
                            db.session.delete(file_obj)
                            db.session.commit()
                            cleaned.append(file_id)
                            orphaned_count += 1
                            logger.info(
                                f"[CLEANUP] Permanently deleted file {file_id} (storage_ref: {storage_ref}) "
                                f"from database (verified not found on disk)"
                            )
                        except Exception as e:
                            db.session.rollback()
                            error_msg = (
                                f"Error deleting file {file_id} from database: {e}"
                            )
                            failed.append((file_id, error_msg))
                            logger.error(f"[CLEANUP] {error_msg}", exc_info=True)

            logger.info(
                f"[CLEANUP] Cleanup completed: {orphaned_count} files marked as deleted, {len(failed)} failed"
            )

        except Exception as e:
            logger.error(
                f"Error in cleanup_orphaned_database_entries: {e}", exc_info=True
            )
            return {
                "cleaned": [],
                "failed": [("all", str(e))],
                "cleaned_count": 0,
                "failed_count": 1,
            }

        return {
            "cleaned": cleaned,
            "failed": failed,
            "cleaned_count": len(cleaned),
            "failed_count": len(failed),
        }


__all__ = ["ExternalStorageSyncService"]
