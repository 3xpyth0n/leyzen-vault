"""Search service for files and folders with E2EE support."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Query

from vault.database.schema import (
    File,
    VaultSpace,
    VaultSpaceType,
    db,
)
from vault.services.search_index_service import SearchIndexService


class SearchService:
    """Service for searching files and folders."""

    def __init__(self, index_service: SearchIndexService | None = None):
        """Initialize search service.

        Args:
            index_service: Optional SearchIndexService instance
        """
        self.index_service = index_service
        if self.index_service is None:
            try:
                storage_dir = current_app.config.get("VAULT_STORAGE_DIR")
                if storage_dir:
                    index_dir = Path(storage_dir) / "search_index"
                else:
                    index_dir = Path("/data/search_index")
            except RuntimeError:
                index_dir = Path("/data/search_index")
            self.index_service = SearchIndexService(index_dir=index_dir)

    def search_files(
        self,
        user_id: str,
        query: str | None = None,
        vaultspace_id: str | None = None,
        parent_id: str | None = None,
        mime_type: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        files_only: bool = False,
        folders_only: bool = False,
        sort_by: str = "relevance",  # relevance, name, date, size
        sort_order: str = "desc",  # asc, desc
        limit: int = 100,
        offset: int = 0,
        encrypted_query: str | None = None,
    ) -> dict[str, Any]:
        """Search files and folders.

        Args:
            user_id: User ID performing search
            query: Search query (for filename search)
            vaultspace_id: Optional VaultSpace ID to limit search
            parent_id: Optional parent folder ID to limit search to this folder and its subfolders
            mime_type: Optional MIME type filter
            min_size: Optional minimum file size in bytes
            max_size: Optional maximum file size in bytes
            created_after: Optional creation date filter (after)
            created_before: Optional creation date filter (before)
            updated_after: Optional update date filter (after)
            updated_before: Optional update date filter (before)
            files_only: If True, return only files (exclude folders)
            folders_only: If True, return only folders
            sort_by: Sort field (relevance, name, date, size)
            sort_order: Sort order (asc, desc)
            limit: Maximum number of results
            offset: Offset for pagination
            encrypted_query: Optional encrypted query for searchable encryption

        Returns:
            Dictionary with results and metadata
        """
        # Start with base query for files user has access to
        base_query = self._get_accessible_files_query(user_id, vaultspace_id)

        # Filter by parent_id if specified (recursive search within folder)
        if parent_id is not None:
            # Get all file IDs in the folder and its subfolders recursively
            folder_file_ids = self._get_folder_file_ids_recursive(parent_id)
            if folder_file_ids:
                base_query = base_query.filter(File.id.in_(folder_file_ids))
            else:
                # No files in this folder, return empty results
                return {
                    "results": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "has_more": False,
                }

        # Apply filters
        if files_only:
            base_query = base_query.filter(File.mime_type != "application/x-directory")
        elif folders_only:
            base_query = base_query.filter(File.mime_type == "application/x-directory")

        if mime_type:
            base_query = base_query.filter(File.mime_type == mime_type)

        if min_size is not None:
            base_query = base_query.filter(File.size >= min_size)
        if max_size is not None:
            base_query = base_query.filter(File.size <= max_size)

        if created_after:
            base_query = base_query.filter(File.created_at >= created_after)
        if created_before:
            base_query = base_query.filter(File.created_at <= created_before)

        if updated_after:
            base_query = base_query.filter(File.updated_at >= updated_after)
        if updated_before:
            base_query = base_query.filter(File.updated_at <= updated_before)

        # Text search (filename) - use Whoosh for fuzzy search if available
        file_ids_from_index = None
        if query and self.index_service:
            try:
                # Use Whoosh for fuzzy search
                index_results = self.index_service.search(
                    query_str=query,
                    vaultspace_id=vaultspace_id,
                    mime_type=mime_type,
                    fuzzy=True,
                    limit=limit * 2,  # Get more results for filtering
                )
                file_ids_from_index = [r["file_id"] for r in index_results]

                if file_ids_from_index:
                    # Filter base query to only include indexed files
                    base_query = base_query.filter(File.id.in_(file_ids_from_index))
                else:
                    # If Whoosh returns no results, fallback to ILIKE
                    base_query = base_query.filter(
                        File.original_name.ilike(f"%{query}%")
                    )
            except Exception:
                # Fallback to simple ILIKE if Whoosh fails
                base_query = base_query.filter(File.original_name.ilike(f"%{query}%"))
        elif query:
            # Simple ILIKE search without Whoosh
            base_query = base_query.filter(File.original_name.ilike(f"%{query}%"))

        # Encrypted search (searchable encryption)
        if encrypted_query:
            # Search in encrypted_metadata for searchable index
            # This is a simplified implementation - in production use proper SSE
            base_query = base_query.filter(File.encrypted_metadata.isnot(None))
            # The actual matching would be done client-side after decryption
            # Here we just filter files that have searchable indexes

        # Get total count before pagination
        total_count = base_query.count()

        # Apply sorting
        if sort_by == "name":
            order_by = (
                File.original_name.asc()
                if sort_order == "asc"
                else File.original_name.desc()
            )
        elif sort_by == "date":
            order_by = (
                File.updated_at.asc() if sort_order == "asc" else File.updated_at.desc()
            )
        elif sort_by == "size":
            order_by = File.size.asc() if sort_order == "asc" else File.size.desc()
        else:  # relevance (default)
            # For relevance, prioritize files matching query in name
            if query:
                # Use PostgreSQL's similarity or simple ordering
                # Files with query at start of name get higher priority
                order_by = case(
                    (File.original_name.ilike(f"{query}%"), 1),
                    (File.original_name.ilike(f"%{query}%"), 2),
                    else_=3,
                ).asc()
            else:
                order_by = File.updated_at.desc()

        base_query = base_query.order_by(order_by)

        # Apply pagination
        files = base_query.limit(limit).offset(offset).all()

        # Convert to dictionaries and add match scores from index if available
        results = []
        index_scores = {}
        if file_ids_from_index and self.index_service:
            try:
                index_results = self.index_service.search(
                    query_str=query,
                    vaultspace_id=vaultspace_id,
                    mime_type=mime_type,
                    fuzzy=True,
                    limit=limit * 2,
                )
                index_scores = {r["file_id"]: r["match_score"] for r in index_results}
            except Exception:
                pass

        for file_obj in files:
            file_dict = file_obj.to_dict()
            # Add match score from index or calculate basic score
            if file_obj.id in index_scores:
                file_dict["match_score"] = index_scores[file_obj.id]
            elif query and file_obj.original_name:
                file_dict["match_score"] = self._calculate_match_score(
                    file_obj.original_name, query
                )
            else:
                file_dict["match_score"] = 1.0

            # Add full path for the file/folder
            file_dict["full_path"] = self._get_file_path(file_obj.id)
            results.append(file_dict)

        # Sort by match score if relevance sorting
        if sort_by == "relevance" and query:
            results.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return {
            "results": results,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
        }

    def _get_accessible_files_query(
        self, user_id: str, vaultspace_id: str | None = None
    ) -> Query:
        """Get query for files accessible by user.

        Args:
            user_id: User ID
            vaultspace_id: Optional VaultSpace ID to limit search

        Returns:
            SQLAlchemy query
        """
        # Get VaultSpaces user has access to
        accessible_vaultspace_ids = self._get_accessible_vaultspace_ids(user_id)

        if vaultspace_id:
            # Verify user has access to this VaultSpace
            if vaultspace_id not in accessible_vaultspace_ids:
                # Return empty query
                return db.session.query(File).filter(False)
            accessible_vaultspace_ids = [vaultspace_id]

        # Base query: files in accessible VaultSpaces, excluding deleted files
        query = db.session.query(File).filter(
            and_(
                File.vaultspace_id.in_(accessible_vaultspace_ids),
                File.deleted_at.is_(None),  # Exclude deleted files
            )
        )

        return query

    def _get_folder_file_ids_recursive(self, folder_id: str | None) -> list[str]:
        """Get all file IDs in a folder and its subfolders recursively.

        Args:
            folder_id: Folder ID (None for root folder)

        Returns:
            List of file IDs
        """
        file_ids = []
        visited_folders = set()
        max_depth = 100
        depth = 0

        def collect_files_recursive(current_folder_id: str | None, current_depth: int):
            """Recursively collect file IDs from folder and subfolders."""
            if current_depth > max_depth:
                return

            # Get all files and folders in current folder
            if current_folder_id is None:
                # Root folder - get files with parent_id = None
                children = (
                    db.session.query(File)
                    .filter(
                        and_(
                            File.parent_id.is_(None),
                            File.deleted_at.is_(None),
                        )
                    )
                    .all()
                )
            else:
                # Subfolder - get files with parent_id = current_folder_id
                if current_folder_id in visited_folders:
                    return  # Avoid cycles
                visited_folders.add(current_folder_id)

                children = (
                    db.session.query(File)
                    .filter(
                        and_(
                            File.parent_id == current_folder_id,
                            File.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

            for child in children:
                if child.mime_type == "application/x-directory":
                    # It's a folder, recurse into it
                    collect_files_recursive(child.id, current_depth + 1)
                else:
                    # It's a file, add its ID
                    file_ids.append(child.id)

        collect_files_recursive(folder_id, depth)
        return file_ids

    def _get_accessible_vaultspace_ids(self, user_id: str) -> list[str]:
        """Get list of VaultSpace IDs accessible by user.

        Args:
            user_id: User ID

        Returns:
            List of VaultSpace IDs
        """
        vaultspace_ids = []

        # Personal VaultSpaces owned by user
        personal = (
            db.session.query(VaultSpace)
            .filter(
                and_(
                    VaultSpace.owner_user_id == user_id,
                    VaultSpace.type == VaultSpaceType.PERSONAL,
                )
            )
            .all()
        )
        vaultspace_ids.extend([vs.id for vs in personal])

        return list(set(vaultspace_ids))  # Remove duplicates

    def _get_file_path(self, file_id: str) -> str:
        """Get the full path for a file or folder.

        Args:
            file_id: File ID

        Returns:
            Full path string (e.g., "Documents/Projects/file.pdf")
        """
        try:
            file_obj = (
                db.session.query(File).filter_by(id=file_id, deleted_at=None).first()
            )

            if not file_obj:
                return ""

            # Build path by traversing up the parent chain
            path_parts = []
            current = file_obj
            visited = set()
            max_depth = 50
            depth = 0

            while current is not None and depth < max_depth:
                if current.id in visited:
                    break  # Avoid cycles
                visited.add(current.id)

                # Add current file/folder name to path
                if current.original_name:
                    path_parts.insert(0, current.original_name)

                # Move to parent
                if current.parent_id:
                    current = (
                        db.session.query(File)
                        .filter_by(id=current.parent_id, deleted_at=None)
                        .first()
                    )
                else:
                    current = None

                depth += 1

            return "/".join(path_parts) if path_parts else file_obj.original_name or ""
        except Exception:
            # If path calculation fails, return empty string
            return ""

    def _calculate_match_score(self, filename: str, query: str) -> float:
        """Calculate match score for relevance sorting.

        Args:
            filename: File name
            query: Search query

        Returns:
            Match score (lower is better for sorting)
        """
        filename_lower = filename.lower()
        query_lower = query.lower()

        if filename_lower.startswith(query_lower):
            return 1.0  # Highest priority
        elif query_lower in filename_lower:
            return 2.0  # Medium priority
        else:
            return 3.0  # Lower priority

    def search_recent_files(
        self,
        user_id: str,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recently accessed or modified files.

        Args:
            user_id: User ID
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of file dictionaries
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = self._get_accessible_files_query(user_id)
        query = query.filter(File.updated_at >= cutoff_date)
        query = query.order_by(File.updated_at.desc())
        query = query.limit(limit)

        files = query.all()
        return [f.to_dict() for f in files]

    def search_by_tags(
        self,
        user_id: str,
        encrypted_tags: list[str],
        vaultspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search files by encrypted tags (for E2EE).

        Args:
            user_id: User ID
            encrypted_tags: List of encrypted tags (encrypted client-side)
            vaultspace_id: Optional VaultSpace ID

        Returns:
            List of matching file dictionaries
        """
        query = self._get_accessible_files_query(user_id, vaultspace_id)
        query = query.filter(File.encrypted_metadata.isnot(None))

        files = query.all()
        results = []

        for file_obj in files:
            if not file_obj.encrypted_metadata:
                continue

            try:
                metadata = json.loads(file_obj.encrypted_metadata)
                searchable_index = metadata.get("searchable_index", {})
                file_tags = searchable_index.get("tags", [])

                # Check if any tag matches (client-side encryption means
                # tags are encrypted, so matching happens client-side)
                # Here we just return files that have tags
                if file_tags:
                    results.append(file_obj.to_dict())
            except (json.JSONDecodeError, KeyError):
                continue

        return results

    def index_file(self, file_obj: File) -> None:
        """Index a file in search index.

        Args:
            file_obj: File object to index
        """
        if self.index_service:
            try:
                self.index_service.index_file(file_obj)
            except Exception:
                # Log error but don't fail
                pass

    def rebuild_search_index(self) -> int:
        """Rebuild entire search index.

        Returns:
            Number of files indexed
        """
        if self.index_service:
            try:
                return self.index_service.rebuild_index()
            except Exception:
                return 0
        return 0
