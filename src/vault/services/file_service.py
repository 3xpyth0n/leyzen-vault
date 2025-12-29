"""Advanced file service with sharing and encryption key management."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from vault.database.schema import (
    File,
    FileKey,
    db,
)
from vault.database.transaction import db_transaction
from vault.services.encryption_service import EncryptionService

from vault.services.vaultspace_service import VaultSpaceService
from vault.services.search_service import SearchService
from vault.services.cache_service import get_cache_service, cache_key
from vault.services.file_event_service import (
    FileEventService,
    FileEventType,
    get_file_event_service,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AdvancedFileService:
    """Advanced file service with sharing and encryption key management."""

    def __init__(self):
        """Initialize advanced file service."""
        self.vaultspace_service = VaultSpaceService()
        self.encryption_service = EncryptionService()
        self.search_service = SearchService()
        self._event_service: FileEventService | None = None

    def _get_event_service(self) -> FileEventService:
        """Get the file event service instance (lazy initialization)."""
        if self._event_service is None:
            self._event_service = get_file_event_service()
        return self._event_service

    def _emit_file_event(
        self,
        event_type: FileEventType,
        file_id: str,
        vaultspace_id: str,
        user_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit a file event (non-blocking).

        Args:
            event_type: Type of event
            file_id: File ID
            vaultspace_id: VaultSpace ID
            user_id: User ID who triggered the event
            data: Additional event data
        """
        try:
            self._get_event_service().emit(
                event_type=event_type,
                file_id=file_id,
                vaultspace_id=vaultspace_id,
                user_id=user_id,
                data=data or {},
            )
        except Exception as e:
            # Don't fail the operation if event emission fails
            logger.debug(f"Failed to emit file event: {e}", exc_info=True)

    def _retry_with_backoff(
        self,
        operation: Callable[[], T],
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> T:
        """Retry an operation with exponential backoff.

        Args:
            operation: Function to retry
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            retryable_exceptions: Tuple of exception types that should trigger retry

        Returns:
            Result of the operation

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                return operation()
            except retryable_exceptions as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.debug(
                        f"Operation failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying after {delay}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Operation failed after {max_retries} attempts: {e}")
                    raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Operation failed without exception")

    def _get_active_file_query(self):
        """Get a base query for active (non-deleted) files.

        Returns:
            SQLAlchemy query filtered to exclude deleted files
        """
        return db.session.query(File).filter(File.deleted_at.is_(None))

    def _check_duplicate_name_in_folder(
        self,
        vaultspace_id: str,
        parent_id: str | None,
        name: str,
        exclude_file_id: str | None = None,
    ) -> bool:
        """Check if a file with the same name already exists in the same folder.

        Args:
            vaultspace_id: VaultSpace ID
            parent_id: Parent folder ID (None for root folder)
            name: File name to check
            exclude_file_id: Optional file ID to exclude from check (for renaming)

        Returns:
            True if a duplicate exists, False otherwise
        """
        query = (
            db.session.query(File)
            .filter_by(
                vaultspace_id=vaultspace_id,
                parent_id=parent_id,
                original_name=name,
            )
            .filter(File.deleted_at.is_(None))
        )
        if exclude_file_id:
            query = query.filter(File.id != exclude_file_id)
        existing = query.first()
        return existing is not None

    def upload_file(
        self,
        vaultspace_id: str,
        user_id: str,
        original_name: str,
        encrypted_data: bytes,
        encrypted_hash: str,
        storage_ref: str,
        encrypted_file_key: str,
        mime_type: str | None = None,
        parent_id: str | None = None,
        encrypted_metadata: str | None = None,
        overwrite: bool = False,
    ) -> tuple[File, FileKey]:
        """Upload a file with encryption key management.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID uploading the file
            original_name: Original filename
            encrypted_data: Encrypted file data
            encrypted_hash: Hash of encrypted data
            storage_ref: Storage reference path
            encrypted_file_key: File key encrypted with VaultSpace key
            mime_type: MIME type
            parent_id: Parent folder ID
            encrypted_metadata: Encrypted metadata JSON
            overwrite: If True, overwrite existing file with same name

        Returns:
            Tuple of (File, FileKey) objects

        Raises:
            ValueError: If user doesn't have write permission to VaultSpace
        """
        # Verify user has access to VaultSpace
        vaultspace = self.vaultspace_service.get_vaultspace(vaultspace_id)
        if not vaultspace:
            raise ValueError(f"VaultSpace {vaultspace_id} not found")

        # Check permissions: only owner can upload
        if vaultspace.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have write permission to VaultSpace {vaultspace_id}"
            )

        # Validate filename format using common validation utility
        from vault.utils.file_validation import validate_filename

        is_valid, validation_error = validate_filename(original_name)
        if not is_valid:
            raise ValueError(validation_error or "Invalid filename")

        # Validate parent if provided
        if parent_id:
            parent_file = (
                self._get_active_file_query()
                .filter_by(id=parent_id, vaultspace_id=vaultspace_id)
                .first()
            )
            if not parent_file:
                raise ValueError(
                    f"Parent file {parent_id} not found in VaultSpace {vaultspace_id} or has been deleted"
                )

        # Check for duplicate names in the same folder
        existing_file = None
        if self._check_duplicate_name_in_folder(
            vaultspace_id, parent_id, original_name
        ):
            if overwrite:
                # Find and delete existing file
                existing_file = (
                    self._get_active_file_query()
                    .filter_by(
                        vaultspace_id=vaultspace_id,
                        parent_id=parent_id,
                        original_name=original_name,
                    )
                    .first()
                )
                if existing_file:
                    # Check if user has permission to overwrite (must be owner)
                    if existing_file.owner_user_id != user_id:
                        raise ValueError(
                            f"User {user_id} does not have permission to overwrite file {existing_file.id}"
                        )
                    # Soft delete the existing file
                    from datetime import datetime, timezone

                    existing_file.deleted_at = datetime.now(timezone.utc)
                    db.session.commit()
            else:
                raise ValueError(
                    f"A file with the name '{original_name}' already exists in this folder"
                )

        # Create file record
        file_obj = File(
            id=str(uuid.uuid4()),
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            owner_user_id=user_id,
            original_name=original_name,
            size=len(encrypted_data),
            encrypted_size=len(encrypted_data),
            encrypted_hash=encrypted_hash,
            encrypted_metadata=encrypted_metadata,
            storage_ref=storage_ref,
            mime_type=mime_type,
        )
        db.session.add(file_obj)

        # Validate encrypted key format
        if not self.encryption_service.validate_encrypted_key_format(
            encrypted_file_key
        ):
            raise ValueError("Invalid encrypted file key format")

        # Create file key entry (encrypted with VaultSpace key)

        file_key = self.encryption_service.create_file_key_entry(
            file_id=file_obj.id,
            vaultspace_id=vaultspace_id,
            encrypted_key=encrypted_file_key,
        )

        # Index file for search (outside transaction to avoid blocking)
        self.search_service.index_file(file_obj)

        # Emit file creation event
        self._emit_file_event(
            event_type=FileEventType.CREATE,
            file_id=file_obj.id,
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            data={
                "original_name": original_name,
                "parent_id": parent_id,
                "mime_type": mime_type,
            },
        )

        return file_obj, file_key

    def delete_file(
        self,
        file_id: str,
        user_id: str,
    ) -> bool:
        """Delete a file with permission check.

        Args:
            file_id: File ID
            user_id: User ID requesting deletion

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If user doesn't have permission to delete
        """
        # Get file - must not be deleted (can't delete an already deleted file)
        file_obj = self._get_active_file_query().filter_by(id=file_id).first()
        if not file_obj:
            return False

        # Check permissions: only owner can delete
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to delete file {file_id}"
            )

        # Store parent_id and vaultspace_id before deletion for cache invalidation
        parent_id = file_obj.parent_id
        vaultspace_id = file_obj.vaultspace_id
        owner_user_id = file_obj.owner_user_id

        # Perform deletion in atomic transaction with retry
        def _delete_operation():
            # Refresh file object to ensure we have latest state
            db.session.refresh(file_obj)
            if file_obj.deleted_at is not None:
                # Already deleted
                return True

            now = datetime.now(timezone.utc)

            # Soft delete the file/folder itself
            file_obj.deleted_at = now

            if file_obj.mime_type == "application/x-directory":

                def _soft_delete_recursive(parent_id):
                    children = (
                        db.session.query(File)
                        .filter_by(parent_id=parent_id, deleted_at=None)
                        .all()
                    )
                    for child in children:
                        child.deleted_at = now
                        if child.mime_type == "application/x-directory":
                            _soft_delete_recursive(child.id)

                _soft_delete_recursive(file_id)

            db.session.flush()  # Flush to ensure state is saved
            return True

        # Retry with exponential backoff for database operations
        try:
            with db_transaction():
                self._retry_with_backoff(
                    _delete_operation,
                    max_retries=3,
                    base_delay=0.1,
                    retryable_exceptions=(Exception,),
                )
        except Exception as e:
            logger.error(f"Failed to delete file {file_id} after retries: {e}")
            raise

        # Update folder size for parent folder after deletion
        if parent_id:
            try:
                self.update_folder_size_recursive(parent_id)
            except Exception as e:
                logger.warning(
                    f"Failed to update folder size for parent {parent_id}: {e}"
                )

        # Invalidate cache for the parent folder to ensure fresh data
        # The cache key format is: "files:vaultspace_id:user_id:parent_id:page:per_page"
        cache = get_cache_service()
        # Invalidate all cache entries for this vaultspace and user to ensure consistency
        # This covers all parent folders and all pages
        vaultspace_pattern = f"files:{vaultspace_id}:{owner_user_id}:"
        invalidated_count = cache.invalidate_pattern(vaultspace_pattern)
        logger.debug(
            f"Invalidated {invalidated_count} cache entries for vaultspace {vaultspace_id} after file deletion"
        )

        # Revoke all share links for this file
        try:
            from vault.services.advanced_sharing_service import AdvancedSharingService
            from vault.services.share_link_service import ShareService

            sharing_service = AdvancedSharingService()
            share_service = ShareService()

            # Revoke PublicShareLink (new sharing system)
            public_links_revoked = sharing_service.revoke_all_links_for_file(
                resource_id=file_id, resource_type="file"
            )
            if public_links_revoked > 0:
                logger.info(
                    f"Revoked {public_links_revoked} public share link(s) for file {file_id}"
                )

            # Revoke ShareLink (legacy sharing system)
            legacy_links_revoked = share_service.revoke_all_links_for_file(file_id)
            if legacy_links_revoked > 0:
                logger.info(
                    f"Revoked {legacy_links_revoked} legacy share link(s) for file {file_id}"
                )
        except Exception as e:
            # Log warning but don't fail the operation if share link revocation fails
            logger.debug(f"Failed to revoke share links for file {file_id}: {e}")

        # Remove from search index in background
        # This prevents blocking the worker uvicorn on slow I/O operations
        from flask import current_app

        # Capture Flask app instance and search index service before creating thread
        flask_app = current_app._get_current_object()
        search_index_service = self.search_service.index_service

        def _background_remove_from_index():
            """Background removal from search index."""
            # Use captured Flask app instance to create app context
            with flask_app.app_context():
                if search_index_service:
                    try:
                        search_index_service.remove_file(file_id)
                    except Exception as e:
                        # Log warning but don't fail the operation if search index removal fails
                        logger.debug(
                            f"Failed to remove file {file_id} from search index: {e}"
                        )

        # Execute index removal in background thread to avoid blocking the worker
        if search_index_service:
            cleanup_thread = threading.Thread(
                target=_background_remove_from_index, daemon=True
            )
            cleanup_thread.start()

        # Emit file deletion event
        self._emit_file_event(
            event_type=FileEventType.DELETE,
            file_id=file_id,
            vaultspace_id=vaultspace_id,
            user_id=owner_user_id,
            data={
                "parent_id": parent_id,
                "mime_type": file_obj.mime_type,
            },
        )

        return True

    def restore_file(
        self,
        file_id: str,
        user_id: str,
    ) -> File | None:
        """Restore a soft-deleted file from trash.

        Args:
            file_id: File ID
            user_id: User ID requesting restoration

        Returns:
            Restored File object, or None if not found

        Raises:
            ValueError: If user doesn't have permission to restore
        """
        file_obj = db.session.query(File).filter_by(id=file_id).first()
        if not file_obj:
            return None

        # Check if file is actually deleted
        if not file_obj.deleted_at:
            raise ValueError(f"File {file_id} is not deleted")

        # Check permissions: only owner can restore
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to restore file {file_id}"
            )

        # Store the deletion timestamp to restore only related children
        deletion_time = file_obj.deleted_at

        # Restore file by clearing deleted_at
        file_obj.deleted_at = None

        if file_obj.mime_type == "application/x-directory":

            def _restore_recursive(parent_id):
                # Only restore children that were deleted at approximately the same time
                # We use a small buffer of 1 second just in case of slight DB execution differences
                # although in our new delete_file implementation they share the exact same 'now'
                children = (
                    db.session.query(File)
                    .filter(
                        File.parent_id == parent_id, File.deleted_at == deletion_time
                    )
                    .all()
                )
                for child in children:
                    child.deleted_at = None
                    if child.mime_type == "application/x-directory":
                        _restore_recursive(child.id)

            _restore_recursive(file_id)

        db.session.commit()

        # Re-index file after restore in background
        # This prevents blocking the worker uvicorn on slow I/O operations
        from flask import current_app

        # Capture Flask app instance and search index service before creating thread
        flask_app = current_app._get_current_object()
        search_index_service = self.search_service.index_service
        file_obj_copy = file_obj  # Capture file object for background thread

        def _background_index_file():
            """Background file indexing."""
            # Use captured Flask app instance to create app context
            with flask_app.app_context():
                if search_index_service:
                    try:
                        search_index_service.index_file(file_obj_copy)
                    except Exception as e:
                        # Log warning but don't fail the operation if indexing fails
                        logger.debug(
                            f"Failed to index file {file_id} after restore: {e}"
                        )

        # Execute indexing in background thread to avoid blocking the worker
        if search_index_service:
            index_thread = threading.Thread(target=_background_index_file, daemon=True)
            index_thread.start()

        # Emit file restore event
        self._emit_file_event(
            event_type=FileEventType.RESTORE,
            file_id=file_id,
            vaultspace_id=file_obj.vaultspace_id,
            user_id=user_id,
            data={
                "parent_id": file_obj.parent_id,
                "mime_type": file_obj.mime_type,
            },
        )

        return file_obj

    def permanently_delete_file(
        self,
        file_id: str,
        user_id: str,
    ) -> bool:
        """Permanently delete a file (hard delete, cannot be undone).

        Args:
            file_id: File ID
            user_id: User ID requesting permanent deletion

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If user doesn't have permission to delete
        """
        file_obj = db.session.query(File).filter_by(id=file_id).first()
        if not file_obj:
            return False

        # Check permissions: only owner can permanently delete
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to permanently delete file {file_id}"
            )

        # Collect all files to delete (recursively if folder)
        files_to_delete = [file_obj]
        if file_obj.mime_type == "application/x-directory":

            def _collect_recursive(parent_id):
                children = db.session.query(File).filter_by(parent_id=parent_id).all()
                for child in children:
                    files_to_delete.append(child)
                    if child.mime_type == "application/x-directory":
                        _collect_recursive(child.id)

            _collect_recursive(file_id)

        # Store storage info for cleanup
        cleanup_info = [
            (f.id, f.storage_ref, f.mime_type)
            for f in files_to_delete
            if f.storage_ref or f.mime_type == "application/x-directory"
        ]

        # Perform permanent deletion in atomic transaction with retry
        def _permanent_delete_operation():
            # Refresh all objects to ensure we have latest state
            for f in files_to_delete:
                db.session.refresh(f)

            for f in files_to_delete:
                # Delete all FileKeys (cascade will handle but we do it explicitly to be safe)
                file_keys = self.encryption_service.get_all_file_keys(f.id)
                for fk in file_keys:
                    db.session.delete(fk)

                # Hard delete file from database
                db.session.delete(f)

            db.session.flush()  # Flush to ensure state is saved
            return True

        # Retry with exponential backoff for database operations
        try:
            with db_transaction():
                self._retry_with_backoff(
                    _permanent_delete_operation,
                    max_retries=3,
                    base_delay=0.1,
                    retryable_exceptions=(Exception,),
                )
        except Exception as e:
            logger.error(
                f"Failed to permanently delete file {file_id} after retries: {e}"
            )
            raise

        # Delete physical files from storage and remove from search index in background
        # This prevents blocking the worker uvicorn on slow I/O operations
        # The database deletion is already committed, so we can safely do cleanup async
        from flask import current_app

        # Capture Flask app instance and required objects before creating thread
        flask_app = current_app._get_current_object()
        storage = flask_app.config.get("VAULT_STORAGE")
        search_index_service = self.search_service.index_service

        def _background_cleanup():
            """Background cleanup of physical files and search index."""
            # Use captured Flask app instance to create app context
            with flask_app.app_context():
                for f_id, s_ref, m_type in cleanup_info:
                    if storage and s_ref and m_type != "application/x-directory":
                        try:
                            # Delete from both primary and source storage
                            deleted = storage.delete_file(s_ref)

                            # Only log if a file was actually deleted
                            if deleted:
                                logger.info(
                                    f"Deleted physical file {s_ref} during permanent delete"
                                )
                        except Exception as e:
                            # Log warning - physical deletion failed for a reason other than "not found"
                            logger.warning(
                                f"Failed to delete physical file {s_ref} during permanent delete: {e}"
                            )

                    # Remove from search index
                    if search_index_service:
                        try:
                            search_index_service.remove_file(f_id)
                        except Exception as e:
                            logger.debug(
                                f"Failed to remove file {f_id} from search index: {e}"
                            )

        # Execute cleanup in background thread to avoid blocking the worker
        cleanup_thread = threading.Thread(target=_background_cleanup, daemon=True)
        cleanup_thread.start()

        return True

    def list_recent_files(
        self,
        user_id: str,
        vaultspace_id: str | None = None,
        limit: int = 50,
        days: int = 30,
    ) -> list[File]:
        """List recent files across all accessible VaultSpaces.

        Args:
            user_id: User ID
            vaultspace_id: Optional VaultSpace ID filter
            limit: Maximum number of files to return
            days: Number of days to look back

        Returns:
            List of recent File objects
        """
        from datetime import timedelta
        from sqlalchemy import and_, or_

        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get VaultSpaces user has access to (owned or shared)
        from vault.services.vaultspace_service import VaultSpaceService

        vaultspace_service = VaultSpaceService()
        accessible_vaultspaces = vaultspace_service.list_vaultspaces(user_id)
        accessible_vaultspace_ids = [vs.id for vs in accessible_vaultspaces]

        if not accessible_vaultspace_ids:
            return []

        if vaultspace_id:
            if vaultspace_id not in accessible_vaultspace_ids:
                return []
            target_vaultspace_ids = [vaultspace_id]
        else:
            target_vaultspace_ids = accessible_vaultspace_ids

        # Query recent files
        # 1. Must be in an accessible VaultSpace
        # 2. Must not be deleted
        # 3. Must be recently updated or created
        query = db.session.query(File).filter(
            and_(
                File.vaultspace_id.in_(target_vaultspace_ids),
                File.deleted_at.is_(None),
                or_(
                    File.updated_at >= cutoff_date,
                    File.created_at >= cutoff_date,
                ),
            )
        )

        # Order by most recently updated first
        query = query.order_by(File.updated_at.desc())

        # Limit results
        recent_files = query.limit(limit).all()

        return recent_files

    def list_trash_files(
        self,
        vaultspace_id: str | None = None,
        user_id: str | None = None,
    ) -> list[File]:
        """List all deleted files (trash).

        Args:
            vaultspace_id: Optional VaultSpace ID filter
            user_id: Optional user ID filter (files owned by user)

        Returns:
            List of deleted File objects
        """
        query = db.session.query(File).filter(File.deleted_at.isnot(None))

        if vaultspace_id:
            query = query.filter_by(vaultspace_id=vaultspace_id)

        if user_id:
            query = query.filter_by(owner_user_id=user_id)

        return query.order_by(File.deleted_at.desc()).all()

    def toggle_star_file(
        self,
        file_id: str,
        user_id: str,
    ) -> File | None:
        """Toggle star status of a file.

        Args:
            file_id: File ID
            user_id: User ID requesting toggle

        Returns:
            Updated File object if found, None otherwise

        Raises:
            ValueError: If user doesn't have permission
        """
        # Get file - must not be deleted
        file_obj = self._get_active_file_query().filter_by(id=file_id).first()
        if not file_obj:
            return None

        # Check permissions: only owner can star
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to star file {file_id}"
            )

        # Toggle star status
        file_obj.is_starred = not file_obj.is_starred
        db.session.commit()

        return file_obj

    def list_starred_files(
        self,
        vaultspace_id: str | None = None,
        user_id: str | None = None,
    ) -> list[File]:
        """List all starred files.

        Args:
            vaultspace_id: Optional VaultSpace ID filter
            user_id: Optional user ID filter (files accessible by user)

        Returns:
            List of starred File objects
        """
        query = db.session.query(File).filter_by(is_starred=True)

        # Exclude deleted files
        query = query.filter(File.deleted_at.is_(None))

        if vaultspace_id:
            query = query.filter_by(vaultspace_id=vaultspace_id)

        # Filter by user access if provided
        if user_id:
            # Only files owned by user
            query = query.filter(File.owner_user_id == user_id)

        return query.order_by(File.updated_at.desc()).all()

    def get_file_with_permissions(
        self,
        file_id: str,
        user_id: str,
    ) -> tuple[File | None, list]:
        """Get file (legacy method, permissions always empty).

        Args:
            file_id: File ID
            user_id: User ID

        Returns:
            Tuple of (File, empty list)
        """
        file_obj = db.session.query(File).filter_by(id=file_id).first()
        if not file_obj:
            return None, []

        return file_obj, []

    def create_folder(
        self,
        vaultspace_id: str,
        user_id: str,
        name: str,
        parent_id: str | None = None,
        overwrite: bool = False,
    ) -> File:
        """Create a folder (directory).

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID creating the folder
            name: Folder name
            parent_id: Optional parent folder ID
            overwrite: If True, overwrite existing folder with same name

        Returns:
            Created File object representing the folder

        Raises:
            ValueError: If user doesn't have write permission to VaultSpace
        """
        # Verify user has access to VaultSpace
        vaultspace = self.vaultspace_service.get_vaultspace(vaultspace_id)
        if not vaultspace:
            raise ValueError(f"VaultSpace {vaultspace_id} not found")

        # Check permissions: only owner can upload
        if vaultspace.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have write permission to VaultSpace {vaultspace_id}"
            )

        # Validate parent if provided
        if parent_id:
            parent_file = (
                self._get_active_file_query()
                .filter_by(id=parent_id, vaultspace_id=vaultspace_id)
                .first()
            )
            if not parent_file:
                raise ValueError(
                    f"Parent folder {parent_id} not found in VaultSpace {vaultspace_id} or has been deleted"
                )
            # Check that parent is actually a folder
            if parent_file.mime_type != "application/x-directory":
                raise ValueError(f"Parent {parent_id} is not a folder")

        # Normalize folder name (trim and collapse spaces, same as validation does)
        import re

        name = name.strip()
        name = re.sub(r"\s+", " ", name)

        # Validate folder name format using common validation utility
        from vault.utils.file_validation import validate_filename

        is_valid, validation_error = validate_filename(name)
        if not is_valid:
            raise ValueError(validation_error or "Invalid folder name")

        # Check for duplicate folder names in the same parent
        # Use the normalized name for comparison
        existing_folder = None
        if self._check_duplicate_name_in_folder(vaultspace_id, parent_id, name):
            if overwrite:
                # Find and delete existing folder
                existing_folder = (
                    self._get_active_file_query()
                    .filter_by(
                        vaultspace_id=vaultspace_id,
                        parent_id=parent_id,
                        original_name=name,
                        mime_type="application/x-directory",
                    )
                    .first()
                )
                if existing_folder:
                    # Check if user has permission to overwrite (must be owner)
                    if existing_folder.owner_user_id != user_id:
                        raise ValueError(
                            f"User {user_id} does not have permission to overwrite folder {existing_folder.id}"
                        )
                    # Soft delete the existing folder
                    from datetime import datetime, timezone

                    existing_folder.deleted_at = datetime.now(timezone.utc)
                    db.session.commit()
            else:
                raise ValueError(
                    f"A folder with the name '{name}' already exists in this location"
                )

        # Create folder record (folders have mime_type="application/x-directory" and empty storage_ref)
        folder = File(
            id=str(uuid.uuid4()),
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            owner_user_id=user_id,
            original_name=name,
            size=0,
            encrypted_size=0,
            encrypted_hash="",  # Folders don't have content hash
            encrypted_metadata=None,
            storage_ref="",  # Folders don't have storage reference
            mime_type="application/x-directory",
        )
        db.session.add(folder)
        db.session.commit()

        # Invalidate cache for this vaultspace to ensure fresh data
        cache = get_cache_service()
        # Invalidate all cache entries for this vaultspace and user to ensure consistency
        # This covers all parent folders and all pages after folder creation
        vaultspace_pattern = f"files:{vaultspace_id}:{user_id}:"
        invalidated_count = cache.invalidate_pattern(vaultspace_pattern)
        logger.debug(
            f"Invalidated {invalidated_count} cache entries for vaultspace {vaultspace_id} after folder creation"
        )

        # Emit folder creation event
        self._emit_file_event(
            event_type=FileEventType.CREATE,
            file_id=folder.id,
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            data={
                "original_name": name,
                "parent_id": parent_id,
                "mime_type": "application/x-directory",
            },
        )

        return folder

    @staticmethod
    def _get_extension(filename: str) -> str | None:
        """Extract file extension from filename.

        Args:
            filename: File name with or without extension

        Returns:
            Extension string (e.g., ".txt", ".pdf") or None if no extension
        """
        if not filename:
            return None

        last_dot = filename.rfind(".")
        if last_dot == -1 or last_dot == 0:
            return None

        return filename[last_dot:]

    @staticmethod
    def _get_name_without_extension(filename: str) -> str:
        """Get filename without extension.

        Args:
            filename: File name with or without extension

        Returns:
            Filename without extension
        """
        if not filename:
            return filename

        last_dot = filename.rfind(".")
        if last_dot == -1 or last_dot == 0:
            return filename

        return filename[:last_dot]

    def rename_file(
        self,
        file_id: str,
        user_id: str,
        new_name: str,
    ) -> File | None:
        """Rename a file or folder.

        Args:
            file_id: File ID
            user_id: User ID requesting rename
            new_name: New name

        Returns:
            Updated File object if found, None otherwise

        Raises:
            ValueError: If user doesn't have permission to rename
        """
        # Get file - must not be deleted
        file_obj = self._get_active_file_query().filter_by(id=file_id).first()
        if not file_obj:
            return None

        # Check permissions: only owner can rename
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to rename file {file_id}"
            )

        # Preserve file extension for security
        original_name = file_obj.original_name
        is_folder = file_obj.mime_type == "application/x-directory"

        if is_folder:
            # For folders: remove any extension from new name
            new_name = self._get_name_without_extension(new_name)
        else:
            # For files: preserve original extension or add one from mime-type
            original_ext = self._get_extension(original_name)

            if original_ext:
                # File had an extension: preserve it
                new_name_base = self._get_name_without_extension(new_name)
                new_name = new_name_base + original_ext
            else:
                # File had no extension: try to add one from mime-type
                from vault.utils.mime_type_detection import get_extension_from_mime_type

                if file_obj.mime_type:
                    mime_ext = get_extension_from_mime_type(file_obj.mime_type)
                    if mime_ext:
                        # Add extension from mime-type
                        new_name = new_name + mime_ext
                    else:
                        # No extension can be determined, keep name without extension
                        new_name = self._get_name_without_extension(new_name)
                else:
                    # No mime-type, keep name without extension
                    new_name = self._get_name_without_extension(new_name)

        # Validate filename format using common validation utility
        from vault.utils.file_validation import validate_filename

        is_valid, validation_error = validate_filename(new_name)
        if not is_valid:
            raise ValueError(validation_error or "Invalid filename")

        # Check for duplicate names in the same folder
        if self._check_duplicate_name_in_folder(
            file_obj.vaultspace_id,
            file_obj.parent_id,
            new_name,
            exclude_file_id=file_id,
        ):
            raise ValueError(
                f"A file with the name '{new_name}' already exists in this folder"
            )

        # Perform rename in atomic transaction with retry
        def _rename_operation():
            # Refresh file object to ensure we have latest state
            db.session.refresh(file_obj)
            # Re-check for duplicates (optimistic locking)
            if self._check_duplicate_name_in_folder(
                file_obj.vaultspace_id,
                file_obj.parent_id,
                new_name,
                exclude_file_id=file_id,
            ):
                raise ValueError(
                    f"A file with the name '{new_name}' already exists in this folder"
                )
            file_obj.original_name = new_name
            db.session.flush()  # Flush to ensure state is saved
            return file_obj

        # Retry with exponential backoff for database operations
        try:
            with db_transaction():
                file_obj = self._retry_with_backoff(
                    _rename_operation,
                    max_retries=3,
                    base_delay=0.1,
                    retryable_exceptions=(Exception,),
                )
        except Exception as e:
            logger.error(f"Failed to rename file {file_id} after retries: {e}")
            raise

        # Invalidate cache for this vaultspace/parent to ensure fresh data
        cache = get_cache_service()
        vaultspace_id = file_obj.vaultspace_id
        user_id = file_obj.owner_user_id
        # Invalidate all cache entries for this vaultspace and user to ensure consistency
        # This covers all parent folders and all pages after rename operation
        vaultspace_pattern = f"files:{vaultspace_id}:{user_id}:"
        invalidated_count = cache.invalidate_pattern(vaultspace_pattern)
        logger.debug(
            f"Invalidated {invalidated_count} cache entries for vaultspace {vaultspace_id} after file rename"
        )

        # Re-index file after rename
        self.search_service.index_file(file_obj)

        # Emit file rename event
        self._emit_file_event(
            event_type=FileEventType.RENAME,
            file_id=file_id,
            vaultspace_id=file_obj.vaultspace_id,
            user_id=user_id,
            data={
                "old_name": file_obj.original_name,
                "new_name": new_name,
                "parent_id": file_obj.parent_id,
            },
        )

        return file_obj

    def move_file(
        self,
        file_id: str,
        user_id: str,
        new_parent_id: str | None = None,
    ) -> File | None:
        """Move a file or folder to a different parent.

        Args:
            file_id: File ID
            user_id: User ID requesting move
            new_parent_id: New parent folder ID (None for root)

        Returns:
            Updated File object if found, None otherwise

        Raises:
            ValueError: If user doesn't have permission or move would create cycle
        """
        # Get file source - must not be deleted
        file_obj = self._get_active_file_query().filter_by(id=file_id).first()
        if not file_obj:
            return None

        # Check permissions: only owner can move
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to move file {file_id}"
            )

        # Validate new parent if provided
        if new_parent_id:
            parent_file = (
                self._get_active_file_query()
                .filter_by(id=new_parent_id, vaultspace_id=file_obj.vaultspace_id)
                .first()
            )
            if not parent_file:
                raise ValueError(
                    f"Parent folder {new_parent_id} not found or has been deleted"
                )
            # Check that parent is actually a folder
            if parent_file.mime_type != "application/x-directory":
                raise ValueError(f"Parent {new_parent_id} is not a folder")

            # Check for cycles (can't move folder into itself or its descendants)
            if file_obj.mime_type == "application/x-directory":
                if self._would_create_cycle(file_id, new_parent_id):
                    raise ValueError("Moving folder would create a cycle")

        # Store old parent_id before moving for cache invalidation
        old_parent_id = file_obj.parent_id
        vaultspace_id = file_obj.vaultspace_id
        user_id = file_obj.owner_user_id

        # Perform move in atomic transaction with retry
        def _move_operation():
            # Refresh file object to ensure we have latest state
            db.session.refresh(file_obj)
            # Re-validate parent if provided (optimistic locking)
            if new_parent_id:
                parent_file = (
                    self._get_active_file_query()
                    .filter_by(id=new_parent_id, vaultspace_id=file_obj.vaultspace_id)
                    .first()
                )
                if not parent_file:
                    raise ValueError(
                        f"Parent folder {new_parent_id} not found or has been deleted"
                    )
                if parent_file.mime_type != "application/x-directory":
                    raise ValueError(f"Parent {new_parent_id} is not a folder")
                # Re-check for cycles
                if file_obj.mime_type == "application/x-directory":
                    if self._would_create_cycle(file_id, new_parent_id):
                        raise ValueError("Moving folder would create a cycle")
            file_obj.parent_id = new_parent_id
            db.session.flush()  # Flush to ensure state is saved
            return file_obj

        # Retry with exponential backoff for database operations
        try:
            with db_transaction():
                file_obj = self._retry_with_backoff(
                    _move_operation,
                    max_retries=3,
                    base_delay=0.1,
                    retryable_exceptions=(Exception,),
                )
        except Exception as e:
            logger.error(f"Failed to move file {file_id} after retries: {e}")
            raise

        # Invalidate cache for this vaultspace to ensure fresh data
        cache = get_cache_service()
        # Invalidate all cache entries for this vaultspace and user to ensure consistency
        # This covers all parent folders and all pages after move operation
        vaultspace_pattern = f"files:{vaultspace_id}:{user_id}:"
        invalidated_count = cache.invalidate_pattern(vaultspace_pattern)
        logger.debug(
            f"Invalidated {invalidated_count} cache entries for vaultspace {vaultspace_id} after file move"
        )

        # Re-index file after move
        self.search_service.index_file(file_obj)

        # Emit file move event
        self._emit_file_event(
            event_type=FileEventType.MOVE,
            file_id=file_id,
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            data={
                "old_parent_id": old_parent_id,
                "new_parent_id": new_parent_id,
                "mime_type": file_obj.mime_type,
            },
        )

        return file_obj

    def _would_create_cycle(self, folder_id: str, new_parent_id: str) -> bool:
        """Check if moving a folder would create a cycle.

        Args:
            folder_id: Folder ID to move
            new_parent_id: New parent folder ID

        Returns:
            True if cycle would be created, False otherwise
        """
        # Traverse up from new_parent_id to see if we reach folder_id
        current_id = new_parent_id
        visited = set()

        while current_id:
            if current_id == folder_id:
                return True  # Cycle detected
            if current_id in visited:
                break  # Already checked this path
            visited.add(current_id)

            parent = (
                self._get_active_file_query()
                .filter_by(id=current_id, mime_type="application/x-directory")
                .first()
            )
            if not parent:
                break
            current_id = parent.parent_id

        return False

    def batch_delete_files(
        self,
        file_ids: list[str],
        user_id: str,
    ) -> dict[str, Any]:
        """Delete multiple files in batch.

        Args:
            file_ids: List of file IDs to delete
            user_id: User ID requesting deletion

        Returns:
            Dictionary with success_count, failed_count, and errors
        """
        success_count = 0
        failed_count = 0
        errors = []

        for file_id in file_ids:
            try:
                if self.delete_file(file_id, user_id):
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append({"file_id": file_id, "error": "File not found"})
            except ValueError as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})
            except Exception as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(file_ids),
            "errors": errors,
        }

    def batch_move_files(
        self,
        file_ids: list[str],
        user_id: str,
        new_parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Move multiple files to a new parent in batch.

        Args:
            file_ids: List of file IDs to move
            user_id: User ID requesting move
            new_parent_id: New parent folder ID (None for root)

        Returns:
            Dictionary with success_count, failed_count, and errors
        """
        success_count = 0
        failed_count = 0
        errors = []
        moved_files = []

        for file_id in file_ids:
            try:
                file_obj = self.move_file(file_id, user_id, new_parent_id)
                if file_obj:
                    success_count += 1
                    moved_files.append(file_obj.to_dict())
                else:
                    failed_count += 1
                    errors.append({"file_id": file_id, "error": "File not found"})
            except ValueError as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})
            except Exception as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(file_ids),
            "moved_files": moved_files,
            "errors": errors,
        }

    def batch_rename_files(
        self,
        file_renames: list[dict[str, str]],
        user_id: str,
    ) -> dict[str, Any]:
        """Rename multiple files in batch.

        Args:
            file_renames: List of dicts with "file_id" and "new_name"
            user_id: User ID requesting rename

        Returns:
            Dictionary with success_count, failed_count, and errors
        """
        success_count = 0
        failed_count = 0
        errors = []
        renamed_files = []

        for rename_op in file_renames:
            file_id = rename_op.get("file_id")
            new_name = rename_op.get("new_name")

            if not file_id or not new_name:
                failed_count += 1
                errors.append(
                    {
                        "file_id": file_id or "unknown",
                        "error": "Missing file_id or new_name",
                    }
                )
                continue

            try:
                file_obj = self.rename_file(file_id, user_id, new_name)
                if file_obj:
                    success_count += 1
                    renamed_files.append(file_obj.to_dict())
                else:
                    failed_count += 1
                    errors.append({"file_id": file_id, "error": "File not found"})
            except ValueError as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})
            except Exception as e:
                failed_count += 1
                errors.append({"file_id": file_id, "error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "total": len(file_renames),
            "renamed_files": renamed_files,
            "errors": errors,
        }

    def copy_file(
        self,
        file_id: str,
        user_id: str,
        new_parent_id: str | None = None,
        new_vaultspace_id: str | None = None,
        new_name: str | None = None,
    ) -> File:
        """Copy a file to a new location.

        Args:
            file_id: File ID to copy
            user_id: User ID requesting copy
            new_parent_id: New parent folder ID (None for root)
            new_vaultspace_id: New VaultSpace ID (None to keep same)
            new_name: New name for copied file (None to keep same)

        Returns:
            New File object (copy)

        Raises:
            ValueError: If user doesn't have permission or file not found
        """
        # Get file source - must not be deleted
        file_obj = self._get_active_file_query().filter_by(id=file_id).first()
        if not file_obj:
            raise ValueError(f"File {file_id} not found or has been deleted")

        # Check permissions: only owner can copy
        if file_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to copy file {file_id}"
            )

        # Determine target VaultSpace
        target_vaultspace_id = new_vaultspace_id or file_obj.vaultspace_id

        # Verify user has write permission to target VaultSpace
        vaultspace = self.vaultspace_service.get_vaultspace(target_vaultspace_id)
        if not vaultspace:
            raise ValueError(f"Target VaultSpace {target_vaultspace_id} not found")

        if vaultspace.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have write permission to target VaultSpace {target_vaultspace_id}"
            )

        # Determine new name (handle conflicts)
        new_file_name = new_name or file_obj.original_name
        if new_parent_id:
            parent_file = (
                self._get_active_file_query()
                .filter_by(id=new_parent_id, vaultspace_id=target_vaultspace_id)
                .first()
            )
            if not parent_file:
                raise ValueError(
                    f"Parent folder {new_parent_id} not found or has been deleted"
                )
            if parent_file.mime_type != "application/x-directory":
                raise ValueError(f"Parent {new_parent_id} is not a folder")

        # Check for name conflicts and generate unique name if needed
        # Only check active (non-deleted) files
        existing = (
            self._get_active_file_query()
            .filter_by(
                vaultspace_id=target_vaultspace_id,
                parent_id=new_parent_id,
                original_name=new_file_name,
            )
            .first()
        )

        if existing:
            # Generate unique name
            import os

            name_parts = os.path.splitext(new_file_name)
            counter = 1
            while existing:
                new_file_name = f"{name_parts[0]} ({counter}){name_parts[1]}"
                existing = (
                    self._get_active_file_query()
                    .filter_by(
                        vaultspace_id=target_vaultspace_id,
                        parent_id=new_parent_id,
                        original_name=new_file_name,
                    )
                    .first()
                )
                counter += 1

        # Create new file record (copy)
        new_file = File(
            id=str(uuid.uuid4()),
            vaultspace_id=target_vaultspace_id,
            parent_id=new_parent_id,
            owner_user_id=user_id,
            original_name=new_file_name,
            size=file_obj.size,
            encrypted_size=file_obj.encrypted_size,
            encrypted_hash=file_obj.encrypted_hash,
            encrypted_metadata=file_obj.encrypted_metadata,
            storage_ref=file_obj.storage_ref,  # Share storage reference
            mime_type=file_obj.mime_type,
        )
        db.session.add(new_file)

        # Copy FileKey if needed (re-encrypt for new VaultSpace)
        if new_vaultspace_id and new_vaultspace_id != file_obj.vaultspace_id:
            # Get original FileKey
            original_file_key = (
                db.session.query(FileKey)
                .filter_by(file_id=file_id, vaultspace_id=file_obj.vaultspace_id)
                .first()
            )
            if original_file_key:

                # with the new VaultSpace key. For now, we'll create a placeholder.
                # The client will need to handle re-encryption.
                pass

        db.session.commit()

        # Update folder size for parent folder after copy
        if new_parent_id:
            try:
                self.update_folder_size_recursive(new_parent_id)
            except Exception as e:
                logger.warning(
                    f"Failed to update folder size for parent {new_parent_id}: {e}"
                )

        # Invalidate cache for the target vaultspace to ensure fresh data
        cache = get_cache_service()
        vaultspace_pattern = f"files:{target_vaultspace_id}:{user_id}:"
        invalidated_count = cache.invalidate_pattern(vaultspace_pattern)
        logger.debug(
            f"Invalidated {invalidated_count} cache entries for vaultspace {target_vaultspace_id} after file copy"
        )

        # Re-index copied file
        self.search_service.index_file(new_file)

        # Emit file creation event for copied file
        self._emit_file_event(
            event_type=FileEventType.CREATE,
            file_id=new_file.id,
            vaultspace_id=target_vaultspace_id,
            user_id=user_id,
            data={
                "original_name": new_file_name,
                "parent_id": new_parent_id,
                "mime_type": new_file.mime_type,
                "copied_from": file_id,
            },
        )

        return new_file

    def copy_folder(
        self,
        folder_id: str,
        user_id: str,
        new_parent_id: str | None = None,
        new_vaultspace_id: str | None = None,
        new_name: str | None = None,
    ) -> File:
        """Copy a folder recursively to a new location.

        Args:
            folder_id: Folder ID to copy
            user_id: User ID requesting copy
            new_parent_id: New parent folder ID (None for root)
            new_vaultspace_id: New VaultSpace ID (None to keep same)
            new_name: New name for copied folder (None to keep same)

        Returns:
            New File object (copy of folder)

        Raises:
            ValueError: If user doesn't have permission or folder not found
        """
        # Get folder source - must not be deleted
        folder_obj = self._get_active_file_query().filter_by(id=folder_id).first()
        if not folder_obj:
            raise ValueError(f"Folder {folder_id} not found or has been deleted")

        if folder_obj.mime_type != "application/x-directory":
            raise ValueError(f"File {folder_id} is not a folder")

        # Check permissions: only owner can copy
        if folder_obj.owner_user_id != user_id:
            raise ValueError(
                f"User {user_id} does not have permission to copy folder {folder_id}"
            )

        # Copy the folder itself
        new_folder = self.copy_file(
            file_id=folder_id,
            user_id=user_id,
            new_parent_id=new_parent_id,
            new_vaultspace_id=new_vaultspace_id,
            new_name=new_name,
        )

        # Recursively copy children - only active (non-deleted) files
        children = (
            self._get_active_file_query()
            .filter_by(vaultspace_id=folder_obj.vaultspace_id, parent_id=folder_id)
            .all()
        )

        for child in children:
            if child.mime_type == "application/x-directory":
                self.copy_folder(
                    folder_id=child.id,
                    user_id=user_id,
                    new_parent_id=new_folder.id,
                    new_vaultspace_id=new_vaultspace_id,
                )
            else:
                self.copy_file(
                    file_id=child.id,
                    user_id=user_id,
                    new_parent_id=new_folder.id,
                    new_vaultspace_id=new_vaultspace_id,
                )

        return new_folder

    def calculate_folder_size(self, folder_id: str) -> int:
        """Calculate total size of a folder recursively.

        Args:
            folder_id: Folder ID

        Returns:
            Total size in bytes (sum of all files in folder and subfolders)
        """
        total_size = 0

        # Get all direct children (files and folders)
        children = (
            db.session.query(File).filter_by(parent_id=folder_id, deleted_at=None).all()
        )

        for child in children:
            if child.mime_type == "application/x-directory":
                # Recursively calculate size of subfolder
                total_size += self.calculate_folder_size(child.id)
            else:
                # Add file size
                total_size += child.size

        return total_size

    def update_folder_size_recursive(self, folder_id: str) -> None:
        """Update folder size and all parent folder sizes recursively.

        Args:
            folder_id: Folder ID to update
        """
        if not folder_id:
            return

        # Calculate current folder size
        total_size = self.calculate_folder_size(folder_id)

        # Update folder in database
        folder = db.session.query(File).filter_by(id=folder_id).first()
        if folder and folder.mime_type == "application/x-directory":
            folder.size = total_size
            db.session.flush()  # Ensure changes are staged
            db.session.commit()

            # Invalidate cache for this vaultspace to ensure fresh data
            cache = get_cache_service()
            vaultspace_pattern = f"files:{folder.vaultspace_id}:"
            cache.invalidate_pattern(vaultspace_pattern)

            # Recursively update parent folders
            if folder.parent_id:
                self.update_folder_size_recursive(folder.parent_id)

    def list_files_in_vaultspace(
        self,
        vaultspace_id: str,
        user_id: str,
        parent_id: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """List files in a VaultSpace with permissions and pagination.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID
            parent_id: Optional parent folder ID
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Dictionary with files list, pagination info, and total count
        """
        cache = get_cache_service()
        cache_key_str = cache_key(
            "files", vaultspace_id, user_id, parent_id, page, per_page
        )

        # Recalculate parent folder size if parent_id is provided
        # This ensures the parent folder size is accurate when viewing its contents
        if parent_id:
            try:
                parent_folder = (
                    db.session.query(File)
                    .filter_by(id=parent_id, vaultspace_id=vaultspace_id)
                    .first()
                )
                if (
                    parent_folder
                    and parent_folder.mime_type == "application/x-directory"
                ):
                    parent_size = self.calculate_folder_size(parent_id)
                    if parent_folder.size != parent_size:
                        parent_folder.size = parent_size
                        db.session.commit()
                        # Invalidate cache when parent size changes
                        cache.invalidate_pattern(f"files:{vaultspace_id}:")
            except Exception as e:
                logger.warning(
                    f"Failed to recalculate parent folder size for {parent_id}: {e}"
                )
                db.session.rollback()

        cache.get(cache_key_str)

        query = db.session.query(File).filter_by(vaultspace_id=vaultspace_id)
        if parent_id:
            query = query.filter_by(parent_id=parent_id)
        else:
            query = query.filter_by(parent_id=None)

        # Exclude deleted files (soft delete)
        query = query.filter(File.deleted_at.is_(None))

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        files = (
            query.order_by(File.created_at.desc()).offset(offset).limit(per_page).all()
        )

        # Build result with permissions
        result_files = []
        folder_ids_to_update = []

        for file_obj in files:
            # Check permissions: only show files owned by user
            if file_obj.owner_user_id == user_id:
                file_dict = file_obj.to_dict()
                file_dict["permission_level"] = "owner"

                # Calculate folder size if it's a directory
                if file_obj.mime_type == "application/x-directory":
                    # Recalculate folder size to ensure accuracy
                    # This is done for visible folders to keep sizes up to date
                    try:
                        folder_size = self.calculate_folder_size(file_obj.id)
                        # Update in database if size changed
                        if file_obj.size != folder_size:
                            file_obj.size = folder_size
                            db.session.flush()
                            folder_ids_to_update.append(file_obj.id)
                        file_dict["total_size"] = folder_size
                        file_dict["size"] = folder_size
                    except Exception as e:
                        # Fallback to stored size if calculation fails
                        logger.warning(
                            f"Failed to calculate size for folder {file_obj.id}: {e}"
                        )
                        folder_size = file_obj.size if file_obj.size else 0
                        file_dict["total_size"] = folder_size
                        file_dict["size"] = folder_size

                result_files.append(file_dict)

        # Commit folder size updates if any
        if folder_ids_to_update:
            try:
                db.session.commit()
                # Invalidate cache for this vaultspace to ensure fresh data
                cache.invalidate_pattern(f"files:{vaultspace_id}:")
            except Exception as e:
                logger.warning(f"Failed to commit folder size updates: {e}")
                db.session.rollback()

        result = {
            "files": result_files,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": (
                    (total_count + per_page - 1) // per_page if per_page > 0 else 1
                ),
            },
        }

        # Cache result for 10 seconds (reduced from 30 to prevent stale data)
        cache.set(cache_key_str, result, ttl=10)

        return result
