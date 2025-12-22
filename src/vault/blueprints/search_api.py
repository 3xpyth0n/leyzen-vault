"""Search API routes for Leyzen Vault."""

from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request

from vault.middleware import get_current_user, jwt_required
from vault.services.search_service import SearchService

search_api_bp = Blueprint("search_api", __name__, url_prefix="/api/search")


def _get_search_service() -> SearchService:
    """Get SearchService instance."""
    return SearchService()


@search_api_bp.route("/files", methods=["GET"])
@jwt_required
def search_files():
    """Search files and folders.

    Query parameters:
        - q: Search query (filename)
        - vaultspace_id: Optional VaultSpace ID
        - mime_type: Optional MIME type filter
        - min_size: Optional minimum file size (bytes)
        - max_size: Optional maximum file size (bytes)
        - created_after: Optional ISO date string
        - created_before: Optional ISO date string
        - updated_after: Optional ISO date string
        - updated_before: Optional ISO date string
        - files_only: true/false (default: false)
        - folders_only: true/false (default: false)
        - sort_by: relevance, name, date, size (default: relevance)
        - sort_order: asc, desc (default: desc)
        - limit: Maximum results (default: 100)
        - offset: Offset for pagination (default: 0)
        - encrypted_query: Optional encrypted query for searchable encryption

    Returns:
        JSON with search results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    search_service = _get_search_service()

    # Parse query parameters
    query = request.args.get("q", "").strip() or None
    vaultspace_id = request.args.get("vaultspace_id", "").strip() or None
    parent_id = request.args.get("parent_id", "").strip() or None
    mime_type = request.args.get("mime_type", "").strip() or None
    encrypted_query = request.args.get("encrypted_query", "").strip() or None

    # Parse size filters
    min_size = request.args.get("min_size")
    min_size = int(min_size) if min_size else None
    max_size = request.args.get("max_size")
    max_size = int(max_size) if max_size else None

    # Parse date filters
    created_after_str = request.args.get("created_after")
    created_after = (
        datetime.fromisoformat(created_after_str.replace("Z", "+00:00"))
        if created_after_str
        else None
    )
    created_before_str = request.args.get("created_before")
    created_before = (
        datetime.fromisoformat(created_before_str.replace("Z", "+00:00"))
        if created_before_str
        else None
    )
    updated_after_str = request.args.get("updated_after")
    updated_after = (
        datetime.fromisoformat(updated_after_str.replace("Z", "+00:00"))
        if updated_after_str
        else None
    )
    updated_before_str = request.args.get("updated_before")
    updated_before = (
        datetime.fromisoformat(updated_before_str.replace("Z", "+00:00"))
        if updated_before_str
        else None
    )

    # Parse boolean filters
    files_only = request.args.get("files_only", "false").lower() == "true"
    folders_only = request.args.get("folders_only", "false").lower() == "true"

    # Parse sorting
    sort_by = request.args.get("sort_by", "relevance")
    sort_order = request.args.get("sort_order", "desc")

    # Parse pagination
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    try:
        results = search_service.search_files(
            user_id=user.id,
            query=query,
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            mime_type=mime_type,
            min_size=min_size,
            max_size=max_size,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            files_only=files_only,
            folders_only=folders_only,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            encrypted_query=encrypted_query,
        )

        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@search_api_bp.route("/recent", methods=["GET"])
@jwt_required
def search_recent():
    """Get recently accessed or modified files.

    Query parameters:
        - days: Number of days to look back (default: 7)
        - limit: Maximum results (default: 50)

    Returns:
        JSON with recent files
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    search_service = _get_search_service()

    days = int(request.args.get("days", 7))
    limit = int(request.args.get("limit", 50))

    try:
        results = search_service.search_recent_files(
            user_id=user.id,
            days=days,
            limit=limit,
        )

        return jsonify({"results": results, "total": len(results)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@search_api_bp.route("/tags", methods=["POST"])
@jwt_required
def search_by_tags():
    """Search files by encrypted tags.

    Request body:
        {
            "tags": ["encrypted_tag1", "encrypted_tag2"],
            "vaultspace_id": "vaultspace-uuid" (optional)
        }

    Returns:
        JSON with matching files
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    encrypted_tags = data.get("tags", [])
    if not isinstance(encrypted_tags, list):
        return jsonify({"error": "tags must be a list"}), 400

    vaultspace_id = data.get("vaultspace_id")

    search_service = _get_search_service()

    try:
        results = search_service.search_by_tags(
            user_id=user.id,
            encrypted_tags=encrypted_tags,
            vaultspace_id=vaultspace_id,
        )

        return jsonify({"results": results, "total": len(results)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
