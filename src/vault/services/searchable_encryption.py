"""Searchable encryption service for encrypted search."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from vault.database.schema import File, db
from vault.utils.safe_json import safe_json_loads


class SearchableEncryptionService:
    """Service for searchable encryption (allows searching encrypted data)."""

    def create_searchable_index(
        self,
        file_id: str,
        encrypted_keywords: list[str],
        encrypted_tags: list[str] | None = None,
    ) -> dict[str, str]:
        """Create searchable index for encrypted content.

        Args:
            file_id: File ID
            encrypted_keywords: List of encrypted keywords (encrypted client-side)
            encrypted_tags: Optional encrypted tags

        Returns:
            Dictionary with index metadata
        """
        # Store encrypted keywords as JSON in file metadata
        # In production, use specialized searchable encryption schemes
        index_data = {
            "keywords": encrypted_keywords,
            "tags": encrypted_tags or [],
        }

        file_obj = db.session.query(File).filter_by(id=file_id).first()
        if file_obj:
            # Update encrypted_metadata with searchable index
            metadata = {}
            if file_obj.encrypted_metadata:
                try:
                    metadata = safe_json_loads(
                        file_obj.encrypted_metadata,
                        max_size=1024 * 1024,  # 1MB for metadata
                        max_depth=50,
                        context="file encrypted_metadata",
                    )
                except Exception:
                    # If metadata is invalid JSON, start with empty metadata
                    # This can happen if metadata was corrupted or stored in an invalid format
                    pass

            metadata["searchable_index"] = index_data
            file_obj.encrypted_metadata = json.dumps(metadata)
            db.session.commit()

        return {"status": "indexed", "file_id": file_id}

    def search_encrypted_files(
        self,
        vaultspace_id: str,
        encrypted_query: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Search encrypted files using encrypted query.

        Args:
            vaultspace_id: VaultSpace ID to search in
            encrypted_query: Encrypted search query (encrypted client-side)
            user_id: User ID performing search

        Returns:
            List of matching file dictionaries
        """
        # Note: This is a simplified implementation
        # Real searchable encryption would use cryptographic schemes like
        # Searchable Symmetric Encryption (SSE) or Functional Encryption

        files = db.session.query(File).filter_by(vaultspace_id=vaultspace_id).all()
        results = []

        for file_obj in files:
            if not file_obj.encrypted_metadata:
                continue

            try:
                metadata = safe_json_loads(
                    file_obj.encrypted_metadata,
                    max_size=1024 * 1024,  # 1MB for metadata
                    max_depth=50,
                    context="file encrypted_metadata",
                )
                searchable_index = metadata.get("searchable_index", {})
                keywords = searchable_index.get("keywords", [])

                # Simple matching (in production, use proper SSE)
                # Client should encrypt query with same key
                if encrypted_query in keywords:
                    file_dict = file_obj.to_dict()
                    file_dict["match_score"] = 1.0
                    results.append(file_dict)
            except Exception:
                # Skip files with invalid metadata or parsing errors
                # Continue processing other files
                continue

        return results

    def create_bloom_filter(
        self,
        keywords: list[str],
    ) -> bytes:
        """Create Bloom filter for efficient keyword membership testing.

        Args:
            keywords: List of keywords

        Returns:
            Bloom filter bytes
        """
        # Simplified Bloom filter implementation
        # In production, use proper cryptographic Bloom filters
        filter_size = 1024
        bloom_filter = bytearray(filter_size)

        for keyword in keywords:
            # Hash keyword multiple times
            for i in range(3):
                hash_value = hashlib.sha256(f"{keyword}_{i}".encode()).digest()
                index = int.from_bytes(hash_value[:4], "big") % filter_size
                bloom_filter[index] = 1

        return bytes(bloom_filter)
