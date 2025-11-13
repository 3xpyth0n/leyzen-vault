"""Advanced sharing API routes for public links."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_file

from vault.database.schema import File, db
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.advanced_sharing_service import AdvancedSharingService
from vault.blueprints.utils import get_client_ip

sharing_api_bp = Blueprint("sharing_api", __name__, url_prefix="/api/v2/sharing")


def _get_sharing_service() -> AdvancedSharingService:
    """Get AdvancedSharingService instance."""
    return AdvancedSharingService()


@sharing_api_bp.route("/public-links", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def create_public_link():
    """Create a public share link.

    Request body:
        {
            "resource_id": "file-uuid",
            "resource_type": "file" | "vaultspace",
            "password": "optional-password",
            "expires_in_days": 7 (optional),
            "max_downloads": 10 (optional),
            "max_access_count": 100 (optional),
            "allow_download": true,
            "allow_preview": true,
            "permission_type": "read" | "write" | "admin"
        }

    Returns:
        JSON with share link info (token included)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    resource_id = data.get("resource_id")
    resource_type = data.get("resource_type")

    if not resource_id or not resource_type:
        return jsonify({"error": "resource_id and resource_type are required"}), 400

    sharing_service = _get_sharing_service()

    try:
        share_link = sharing_service.create_public_link(
            resource_id=resource_id,
            resource_type=resource_type,
            created_by=user.id,
            password=data.get("password"),
            expires_in_days=data.get("expires_in_days"),
            max_downloads=data.get("max_downloads"),
            max_access_count=data.get("max_access_count"),
            allow_download=data.get("allow_download", True),
            allow_preview=data.get("allow_preview", True),
            permission_type=data.get("permission_type", "read"),
        )

        # Build share URL
        share_url = f"/share/{share_link.token}"

        return (
            jsonify(
                {
                    "share_link": share_link.to_dict(),
                    "share_url": share_url,
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@sharing_api_bp.route("/public-links", methods=["GET"])
@jwt_required
def list_public_links():
    """List public share links created by the current user.

    Query parameters:
        - resource_id: Optional resource ID filter

    Returns:
        JSON with list of share links
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    resource_id = request.args.get("resource_id")

    sharing_service = _get_sharing_service()
    share_links = sharing_service.list_user_public_links(user.id, resource_id)

    enriched_links: list[dict[str, Any]] = []
    for link in share_links:
        link_data = link.to_dict()

        resource_info = None
        if link.resource_type == "file":
            file_obj = (
                db.session.query(File)
                .filter_by(id=link.resource_id, deleted_at=None)
                .first()
            )
            if file_obj:
                resource_info = file_obj.to_dict()

        link_data["resource"] = resource_info
        enriched_links.append(link_data)

    return jsonify({"share_links": enriched_links, "total": len(enriched_links)}), 200


@sharing_api_bp.route("/public-links/<link_id>", methods=["PUT"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def update_public_link(link_id: str):
    """Update a public share link.

    Request body:
        {
            "expires_in_days": 7 (optional),
            "max_downloads": 10 (optional),
            "max_access_count": 100 (optional),
            "allow_download": true (optional),
            "allow_preview": true (optional),
            "is_active": true (optional)
        }

    Returns:
        JSON with updated share link
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json() or {}

    sharing_service = _get_sharing_service()

    try:
        updated_link = sharing_service.update_public_link(
            link_id=link_id,
            user_id=user.id,
            expires_in_days=data.get("expires_in_days"),
            max_downloads=data.get("max_downloads"),
            max_access_count=data.get("max_access_count"),
            allow_download=data.get("allow_download"),
            allow_preview=data.get("allow_preview"),
            is_active=data.get("is_active"),
        )

        if not updated_link:
            return jsonify({"error": "Share link not found or unauthorized"}), 404

        return jsonify({"share_link": updated_link.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@sharing_api_bp.route("/public-links/<link_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def revoke_public_link(link_id: str):
    """Revoke a public share link.

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    sharing_service = _get_sharing_service()

    success = sharing_service.revoke_public_link(link_id, user.id)
    if not success:
        return jsonify({"error": "Share link not found or unauthorized"}), 404

    return jsonify({"message": "Share link revoked successfully"}), 200


@sharing_api_bp.route("/public-links/<token>/verify", methods=["POST"])
def verify_public_link():
    """Verify a public share link (for password-protected links).

    Request body:
        {
            "password": "optional-password"
        }

    Returns:
        JSON with share link info if valid
    """
    token = request.view_args.get("token")
    if not token:
        return jsonify({"error": "Token required"}), 400

    data = request.get_json() or {}
    password = data.get("password")

    sharing_service = _get_sharing_service()

    if password:
        is_valid, share_link = sharing_service.verify_public_link_password(
            token, password
        )
        if not is_valid:
            return jsonify({"error": "Invalid password"}), 403
    else:
        share_link = sharing_service.get_public_link(token)
        if not share_link:
            current_app.logger.info(
                "get_public_link: share link not found for token=%s", token
            )
            return jsonify({"error": "Share link not found"}), 404

    if not share_link.can_access():
        current_app.logger.info(
            "get_public_link: share link cannot be accessed token=%s active=%s expired=%s download_limit_reached=%s access_limit_reached=%s",
            token,
            share_link.is_active,
            share_link.is_expired(),
            share_link.is_download_limit_reached(),
            share_link.is_access_limit_reached(),
        )
        return jsonify({"error": "Share link expired or limit reached"}), 403

    return jsonify({"share_link": share_link.to_dict()}), 200


@sharing_api_bp.route("/public-links/<token>", methods=["GET"])
def get_public_link(token: str):
    """Get public share link information (public endpoint, no auth required).

    Query parameters:
        - password: Optional password for password-protected links

    Returns:
        JSON with share link info and resource info
    """
    password = request.args.get("password")
    download_requested = request.args.get("download") == "true"

    sharing_service = _get_sharing_service()

    if password:
        is_valid, share_link = sharing_service.verify_public_link_password(
            token, password
        )
        if not is_valid:
            return jsonify({"error": "Invalid password"}), 403
    else:
        share_link = sharing_service.get_public_link(token)
        if not share_link:
            return jsonify({"error": "Share link not found"}), 404

    if not share_link.can_access():
        return jsonify({"error": "Share link expired or limit reached"}), 403

    if download_requested:
        return download_shared_file(token)

    # Get resource info
    resource_info = None
    if share_link.resource_type == "file":
        file_obj = (
            db.session.query(File)
            .filter_by(id=share_link.resource_id, deleted_at=None)
            .first()
        )
        if file_obj:
            resource_info = file_obj.to_dict()
            # Map to legacy format for compatibility
            response_data = {
                "link_id": share_link.token,
                "file_id": share_link.resource_id,
                "filename": file_obj.original_name,
                "size": file_obj.size,
                "expires_at": (
                    share_link.expires_at.isoformat() if share_link.expires_at else None
                ),
                "max_downloads": share_link.max_downloads,
                "download_count": share_link.download_count or 0,
                "is_active": share_link.is_active,
                "is_expired": not share_link.can_access(),
                "is_valid": True,
                "error": None,
                "has_password": share_link.password_hash is not None,
            }
            return jsonify(response_data), 200
    elif share_link.resource_type == "vaultspace":
        from vault.database.schema import VaultSpace

        vaultspace = (
            db.session.query(VaultSpace).filter_by(id=share_link.resource_id).first()
        )
        if vaultspace:
            resource_info = vaultspace.to_dict()

    return (
        jsonify(
            {
                "share_link": share_link.to_dict(),
                "resource": resource_info,
            }
        ),
        200,
    )


@sharing_api_bp.route("/public-links/<token>/access", methods=["POST"])
def access_public_link(token: str):
    """Access a public share link (increments access count).

    Request body:
        {
            "password": "optional-password"
        }

    Returns:
        JSON with share link info and resource info
    """
    data = request.get_json() or {}
    password = data.get("password")

    sharing_service = _get_sharing_service()
    share_link = sharing_service.access_public_link(token, password)

    if not share_link:
        return jsonify({"error": "Invalid token, password, or link expired"}), 403

    # Get resource info
    resource_info = None
    if share_link.resource_type == "file":
        file_obj = (
            db.session.query(File)
            .filter_by(id=share_link.resource_id, deleted_at=None)
            .first()
        )
        if file_obj:
            resource_info = file_obj.to_dict()
    elif share_link.resource_type == "vaultspace":
        from vault.database.schema import VaultSpace

        vaultspace = (
            db.session.query(VaultSpace).filter_by(id=share_link.resource_id).first()
        )
        if vaultspace:
            resource_info = vaultspace.to_dict()

    return (
        jsonify(
            {
                "share_link": share_link.to_dict(),
                "resource": resource_info,
            }
        ),
        200,
    )


@sharing_api_bp.route("/public-links/<token>/download", methods=["GET"])
def download_shared_file(token: str):
    """Download a file via public share link (public endpoint, no auth required).

    Query parameters:
        - password: Optional password for password-protected links

    Returns:
        Encrypted file data as binary stream
    """
    password = request.args.get("password")
    sharing_service = _get_sharing_service()
    storage = current_app.config.get("VAULT_STORAGE")
    audit = current_app.config.get("VAULT_AUDIT")
    user_ip = get_client_ip() or "unknown"

    if not storage:
        return jsonify({"error": "Storage not configured"}), 500

    try:
        # Verify share link
        if password:
            is_valid, share_link = sharing_service.verify_public_link_password(
                token, password
            )
            if not is_valid:
                if audit:
                    audit.log_action(
                        "download",
                        user_ip,
                        {"error": "Invalid password", "token": token[:20]},
                        False,
                    )
                return jsonify({"error": "Invalid password"}), 403
            if not share_link:
                if audit:
                    audit.log_action(
                        "download",
                        user_ip,
                        {"error": "Share link not found", "token": token[:20]},
                        False,
                    )
                return jsonify({"error": "Share link not found"}), 404
        else:
            share_link = sharing_service.get_public_link(token)
            if not share_link:
                if audit:
                    audit.log_action(
                        "download",
                        user_ip,
                        {"error": "Share link not found", "token": token[:20]},
                        False,
                    )
                return jsonify({"error": "Share link not found"}), 404

        # Check if link can be accessed
        if not share_link.is_active:
            return jsonify({"error": "Share link is not active"}), 403
        if share_link.is_expired():
            return jsonify({"error": "Share link has expired"}), 403
        if share_link.is_access_limit_reached():
            return jsonify({"error": "Share link access limit reached"}), 403
        if share_link.resource_type != "file":
            return jsonify({"error": "Resource is not a file"}), 400

        # Get file from database
        file_obj = (
            db.session.query(File)
            .filter_by(id=share_link.resource_id, deleted_at=None)
            .first()
        )
        if not file_obj:
            if audit:
                audit.log_action(
                    "download",
                    user_ip,
                    {
                        "error": "File not found",
                        "resource_id": share_link.resource_id,
                        "token": token[:20],
                    },
                    False,
                    file_id=share_link.resource_id,
                )
            return jsonify({"error": "File not found"}), 404

        # Check if download is allowed
        if not share_link.allow_download:
            return jsonify({"error": "Download not allowed for this share link"}), 403
        if share_link.is_download_limit_reached():
            return jsonify({"error": "Download limit reached for this share link"}), 403

        # Increment access count (for tracking access attempts)
        # This is done before checking file existence to track all access attempts
        accessed_link = sharing_service.access_public_link(token, password)
        if not accessed_link:
            current_app.logger.error(
                "download_shared_file: access_public_link returned None token=%s",
                token,
            )
            return jsonify({"error": "Failed to process download"}), 500

        # Get storage reference
        storage_ref = file_obj.storage_ref or file_obj.id

        # Try storage_ref first, then fallback to file_id if not found
        if not storage.file_exists(storage_ref):
            # If storage_ref is different from file_id, try file_id as fallback
            if storage_ref != file_obj.id and storage.file_exists(file_obj.id):
                storage_ref = file_obj.id
            else:
                current_app.logger.error(
                    "download_shared_file: File not found in storage. storage_ref=%s file_id=%s",
                    storage_ref,
                    file_obj.id,
                )
                if audit:
                    audit.log_action(
                        "download",
                        user_ip,
                        {
                            "error": "File data not found in storage",
                            "file_id": file_obj.id,
                        },
                        False,
                        file_id=file_obj.id,
                    )
                # Note: access_count was incremented, but download_count was not
                return jsonify({"error": "File data not found in storage"}), 404

        # Find file path
        file_path = storage._find_file_path(storage_ref)
        if not file_path:
            current_app.logger.error(
                "download_shared_file: File path not found. storage_ref=%s file_id=%s",
                storage_ref,
                file_obj.id,
            )
            if audit:
                audit.log_action(
                    "download",
                    user_ip,
                    {"error": "File path not found", "file_id": file_obj.id},
                    False,
                    file_id=file_obj.id,
                )
            # Note: access_count was incremented, but download_count was not
            return jsonify({"error": "File not found"}), 404

        # Only increment download count if file exists and is accessible
        # Re-fetch share link to get latest state (access_count was already incremented)
        share_link = sharing_service.get_public_link(token)
        if share_link:
            share_link.download_count += 1
            db.session.commit()

        # Log successful download
        if audit:
            audit.log_action(
                "download",
                user_ip,
                {
                    "file_id": file_obj.id,
                    "filename": file_obj.original_name,
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                    "via_share_link": True,
                    "token": token[:20],
                },
                True,
                file_id=file_obj.id,
            )

        # Return file
        return send_file(
            file_path,
            mimetype="application/octet-stream",
            download_name=file_obj.original_name,
        )
    except Exception as e:
        current_app.logger.exception(
            "Unexpected error while downloading share link token=%s", token
        )
        if audit:
            audit.log_action(
                "download",
                user_ip,
                {"error": str(e), "token": token[:20]},
                False,
            )
        return jsonify({"error": "Internal server error"}), 500
