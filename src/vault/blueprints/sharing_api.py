"""Advanced sharing API routes for public links."""

from __future__ import annotations

from datetime import datetime, timezone
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
            permission_type=data.get("permission_type", "read"),
        )

        # Build share URL using VAULT_URL if configured, otherwise relative URL
        from vault.services.share_link_service import ShareService

        share_service = ShareService()
        share_url = share_service.get_share_url(share_link.token, resource_id)

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

    # Get ShareService for building share URLs with VAULT_URL
    from vault.services.share_link_service import ShareService

    share_service = ShareService()

    enriched_links: list[dict[str, Any]] = []
    for link in share_links:
        link_data = link.to_dict()

        # Add share_url using VAULT_URL if configured
        share_url = share_service.get_share_url(link.token, link.resource_id)
        link_data["share_url"] = share_url

        resource_info = None
        if link.resource_type == "file":
            file_obj = (
                db.session.query(File)
                .filter_by(id=link.resource_id, deleted_at=None)
                .first()
            )
            if file_obj:
                resource_info = file_obj.to_dict()
            else:
                # Skip links to deleted/non-existent files
                continue
        elif link.resource_type == "vaultspace":
            from vault.database.schema import VaultSpace

            vaultspace = (
                db.session.query(VaultSpace).filter_by(id=link.resource_id).first()
            )
            if vaultspace:
                resource_info = vaultspace.to_dict()
            else:
                # Skip links to non-existent vaultspaces
                continue

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
            "allow_download": true (optional)
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
    # Rate limiting to prevent brute force attacks on share link passwords
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=5,
            window_seconds=300,  # 5 minutes
            action_name="share_link_verify",
            user_id=None,  # Share links are public, no user_id available
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many attempts. Please try again later."}
                ),
                429,
            )

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
            "get_public_link: share link cannot be accessed token=%s expired=%s download_limit_reached=%s access_limit_reached=%s",
            token,
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
    # Rate limiting to prevent enumeration attacks
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=20,
            window_seconds=60,  # 1 minute
            action_name="share_link_info",
            user_id=None,  # Share links are public, no user_id available
        )
        if not is_allowed:
            return (
                jsonify(
                    {"error": error_msg or "Too many requests. Please try again later."}
                ),
                429,
            )

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
                "is_expired": not share_link.can_access(),
                "is_available": share_link.can_access(),
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
    # Rate limiting to prevent abuse
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=10,
            window_seconds=60,  # 1 minute
            action_name="share_link_access",
            user_id=None,  # Share links are public, no user_id available
        )
        if not is_allowed:
            return (
                jsonify(
                    {
                        "error": error_msg
                        or "Too many access attempts. Please try again later."
                    }
                ),
                429,
            )

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
    # Rate limiting to prevent abuse and brute force attacks
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=10,
            window_seconds=60,  # 1 minute
            action_name="share_link_download",
            user_id=None,  # Share links are public, no user_id available
        )
        if not is_allowed:
            return (
                jsonify(
                    {
                        "error": error_msg
                        or "Too many download attempts. Please try again later."
                    }
                ),
                429,
            )

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

        # Get storage reference
        storage_ref = file_obj.storage_ref or file_obj.id

        # Verify file exists in storage BEFORE incrementing counters
        # This prevents race conditions where counters are incremented for non-existent files
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
            return jsonify({"error": "File not found"}), 404

        # SECURITY: Use atomic transaction to increment counters only after file verification
        # This prevents race conditions and ensures counters are accurate
        try:
            # Re-fetch share link within transaction to get latest state
            share_link = sharing_service.get_public_link(token)
            if not share_link:
                return jsonify({"error": "Share link not found"}), 404

            # Double-check limits within transaction (may have changed)
            if share_link.is_expired():
                return jsonify({"error": "Share link has expired"}), 403
            if share_link.is_access_limit_reached():
                return jsonify({"error": "Share link access limit reached"}), 403
            if share_link.is_download_limit_reached():
                return (
                    jsonify({"error": "Download limit reached for this share link"}),
                    403,
                )

            # Increment both access and download counts atomically
            share_link.access_count += 1
            share_link.download_count += 1
            share_link.last_accessed_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to increment share link counters: {e}")
            # Continue with download even if counter increment fails
            # (logging is more important than blocking the download)

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


@sharing_api_bp.route("/public-links/<link_id>/send-email", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def send_share_link_email(link_id: str):
    """Send a share link via email.

    Request body:
        {
            "to_email": "recipient@example.com",
            "share_url": "full_url_with_key"
        }

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    to_email = data.get("to_email")
    share_url = data.get("share_url")

    if not to_email or not share_url:
        return (
            jsonify({"error": "to_email and share_url are required"}),
            400,
        )

    # Validate email format
    import re

    email_pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    if not re.match(email_pattern, to_email):
        return jsonify({"error": "Invalid email format"}), 400

    # Validate that share_url contains decryption key in fragment
    if "#key=" not in share_url:
        return (
            jsonify(
                {
                    "error": "Share URL must include decryption key in fragment (#key=...)"
                }
            ),
            400,
        )

    sharing_service = _get_sharing_service()

    # Verify that the link exists and belongs to the user
    share_link = sharing_service._get_share_link_by_identifier(link_id)
    if not share_link:
        return jsonify({"error": "Share link not found"}), 404

    if share_link.created_by != user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Check if link is still available
    if not share_link.can_access():
        return (
            jsonify({"error": "Share link expired or limit reached"}),
            403,
        )

    # Get file name for email template
    file_name = "Shared File"
    if share_link.resource_type == "file":
        file_obj = (
            db.session.query(File)
            .filter_by(id=share_link.resource_id, deleted_at=None)
            .first()
        )
        if file_obj:
            file_name = file_obj.original_name

    # Send email using EmailService
    from vault.services.email_service import EmailService

    email_service = EmailService()
    sender_name = user.email if hasattr(user, "email") else None

    success = email_service.send_share_link_email(
        to_email=to_email,
        share_url=share_url,
        file_name=file_name,
        sender_name=sender_name,
    )

    if not success:
        return (
            jsonify(
                {"error": "Failed to send email. Please check SMTP configuration."}
            ),
            500,
        )

    return jsonify({"message": "Share link sent via email successfully"}), 200
