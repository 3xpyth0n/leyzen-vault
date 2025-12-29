"""Search index service using Whoosh for full-text search."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from flask import current_app
from whoosh import index
from whoosh.fields import ID, KEYWORD, NUMERIC, Schema, TEXT
from whoosh.qparser import FuzzyTermPlugin, MultifieldParser, QueryParser
from whoosh.query import And, Term

from vault.database.schema import File, db


class SearchIndexService:
    """Service for managing Whoosh search index."""

    def __init__(self, index_dir: Path | None = None):
        """Initialize search index service.

        Args:
            index_dir: Directory for Whoosh index (default: /data/search_index)
        """
        if index_dir is None:

            try:
                storage_dir = current_app.config.get("VAULT_STORAGE_DIR")
                if storage_dir:
                    index_dir = Path(storage_dir) / "search_index"
                else:
                    index_dir = Path("/data/search_index")
            except RuntimeError:
                # Outside Flask context
                index_dir = Path("/data/search_index")

        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Define schema
        self.schema = Schema(
            file_id=ID(stored=True, unique=True),
            name=TEXT(stored=True),
            mime_type=KEYWORD(stored=True),
            vaultspace_id=ID(stored=True),
            size=NUMERIC(int, stored=True),
            created_at=TEXT(stored=True),
            updated_at=TEXT(stored=True),
        )

        self._index = None
        self._cache: dict[str, tuple[Any, float]] = {}  # query -> (results, timestamp)
        self._cache_ttl = 300  # 5 minutes

    def _get_index(self):
        """Get or create Whoosh index."""
        if self._index is None:
            if index.exists_in(str(self.index_dir)):
                self._index = index.open_dir(str(self.index_dir))
            else:
                self._index = index.create_in(str(self.index_dir), self.schema)
        return self._index

    def index_file(self, file_obj: File) -> None:
        """Index a file (non-blocking, handles lock errors gracefully).

        Args:
            file_obj: File object to index
        """
        try:
            idx = self._get_index()
            # Use delaycommit to reduce lock contention
            writer = idx.writer(delaycommit=True)

            try:
                writer.update_document(
                    file_id=file_obj.id,
                    name=file_obj.original_name or "",
                    mime_type=file_obj.mime_type or "",
                    vaultspace_id=file_obj.vaultspace_id,
                    size=file_obj.size or 0,
                    created_at=(
                        file_obj.created_at.isoformat() if file_obj.created_at else ""
                    ),
                    updated_at=(
                        file_obj.updated_at.isoformat() if file_obj.updated_at else ""
                    ),
                )
                writer.commit()
            except Exception as e:
                writer.cancel()
                # Log but don't raise - indexing failures shouldn't block operations
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(f"Failed to index file {file_obj.id}: {e}")
        except Exception as e:

            # This prevents blocking workers when index operations conflict
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Index unavailable for file {file_obj.id}: {e}")

    def remove_file(self, file_id: str) -> None:
        """Remove a file from index (non-blocking, handles lock errors gracefully).

        Args:
            file_id: File ID to remove
        """
        try:
            idx = self._get_index()
            # Use delaycommit to reduce lock contention
            writer = idx.writer(delaycommit=True)
            try:
                writer.delete_by_term("file_id", file_id)
                writer.commit()
            except Exception as e:
                writer.cancel()
                # Log but don't raise - removal failures shouldn't block operations
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(f"Failed to remove file {file_id} from index: {e}")
        except Exception as e:

            # This prevents blocking workers when index operations conflict
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Index unavailable for removing file {file_id}: {e}")

    def search(
        self,
        query_str: str,
        vaultspace_id: str | None = None,
        mime_type: str | None = None,
        fuzzy: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search files using Whoosh.

        Args:
            query_str: Search query
            vaultspace_id: Optional VaultSpace ID filter
            mime_type: Optional MIME type filter
            fuzzy: Enable fuzzy search
            limit: Maximum results

        Returns:
            List of file dictionaries with match scores
        """
        # Check cache
        cache_key = f"{query_str}:{vaultspace_id}:{mime_type}:{fuzzy}:{limit}"
        if cache_key in self._cache:
            results, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return results

        try:
            idx = self._get_index()
            results = []

            with idx.searcher() as searcher:
                # Build query
                if fuzzy:
                    parser = MultifieldParser(["name", "mime_type"], schema=idx.schema)
                    parser.add_plugin(FuzzyTermPlugin())
                    query = parser.parse(query_str)
                else:
                    parser = QueryParser("name", schema=idx.schema)
                    query = parser.parse(query_str)

                # Add filters
                filters = []
                if vaultspace_id:
                    filters.append(Term("vaultspace_id", vaultspace_id))
                if mime_type:
                    filters.append(Term("mime_type", mime_type))

                if filters:
                    query = And([query] + filters)

                # Execute search
                hits = searcher.search(query, limit=limit)

                for hit in hits:
                    results.append(
                        {
                            "file_id": hit["file_id"],
                            "name": hit["name"],
                            "mime_type": hit.get("mime_type", ""),
                            "vaultspace_id": hit.get("vaultspace_id", ""),
                            "size": hit.get("size", 0),
                            "match_score": hit.score,
                        }
                    )
        except Exception as e:

            # This prevents blocking workers when index operations conflict
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Index unavailable for search '{query_str}': {e}")
            results = []

        # Cache results
        self._cache[cache_key] = (results, time.time())

        # Clean old cache entries
        self._clean_cache()

        return results

    def _clean_cache(self) -> None:
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._cache[key]

    def rebuild_index(self) -> int:
        """Rebuild entire index from database (non-blocking, handles errors gracefully).

        Returns:
            Number of files indexed
        """
        try:
            idx = self._get_index()
            # Use delaycommit to reduce lock contention
            writer = idx.writer(delaycommit=True)

            count = 0
            try:
                # Get all non-deleted files
                files = db.session.query(File).filter(File.deleted_at.is_(None)).all()

                for file_obj in files:
                    writer.update_document(
                        file_id=file_obj.id,
                        name=file_obj.original_name or "",
                        mime_type=file_obj.mime_type or "",
                        vaultspace_id=file_obj.vaultspace_id,
                        size=file_obj.size or 0,
                        created_at=(
                            file_obj.created_at.isoformat()
                            if file_obj.created_at
                            else ""
                        ),
                        updated_at=(
                            file_obj.updated_at.isoformat()
                            if file_obj.updated_at
                            else ""
                        ),
                    )
                    count += 1

                writer.commit()
                return count
            except Exception as e:
                writer.cancel()
                # Log but don't raise - rebuild failures shouldn't block operations
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to rebuild search index: {e}")
                return count  # Return count of files processed before error
        except Exception as e:

            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Index unavailable for rebuild: {e}")
            return 0
