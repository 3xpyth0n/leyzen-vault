"""Folder management API endpoints."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..services.audit import AuditService
from ..storage import FileStorage
from ..middleware.jwt_auth import jwt_required, get_current_user
from .utils import get_client_ip

folders_bp = Blueprint("folders", __name__)


def _get_storage() -> FileStorage:
    """Get the file storage instance from Flask config."""
    return current_app.config["VAULT_STORAGE"]


def _get_audit() -> AuditService:
    """Get the audit service instance from Flask config."""
    return current_app.config["VAULT_AUDIT"]


def _compute_name_hash(name: str) -> str:
    """Compute SHA-256 hash of folder name for search."""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


def _check_duplicate_folder_name(
    vaultspace_id: str,
    parent_id: str | None,
    name_hash: str,
    exclude_folder_id: str | None = None,
) -> bool:
    """Check if a folder with the same name hash already exists in the same parent.

    Args:
        vaultspace_id: VaultSpace ID
        parent_id: Parent folder ID (None for root folder)
        name_hash: Folder name hash to check
        exclude_folder_id: Optional folder ID to exclude from check (for renaming)

    Returns:
        True if a duplicate exists, False otherwise
    """
    from vault.database.schema import File, db

    query = (
        db.session.query(File)
        .filter_by(
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            mime_type="application/x-directory",
            encrypted_hash=name_hash,
        )
        .filter(File.deleted_at.is_(None))
    )
    if exclude_folder_id:
        query = query.filter(File.id != exclude_folder_id)
    existing = query.first()
    return existing is not None


@folders_bp.route("/api/folders", methods=["POST"])
@jwt_required
def create_folder():
    """Create a new folder."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    if not request.is_json:
        audit.log_action(
            "folder_create",
            user_ip,
            {"error": "Request must be JSON"},
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.json
    encrypted_name = data.get("encrypted_name")
    name_hash = data.get("name_hash")
    parent_id = data.get("parent_id")  # Can be None for root folder
    vaultspace_id = data.get("vaultspace_id")  # Required

    if not encrypted_name or not name_hash:
        audit.log_action(
            "folder_create",
            user_ip,
            {"error": "Missing encrypted_name or name_hash"},
            False,
        )
        return jsonify({"error": "encrypted_name and name_hash are required"}), 400

    if not vaultspace_id:
        audit.log_action(
            "folder_create",
            user_ip,
            {"error": "Missing vaultspace_id"},
            False,
        )
        return jsonify({"error": "vaultspace_id is required"}), 400

    from vault.database.schema import File, db

    # Validate parent_id if provided (must be a folder)
    if parent_id is not None:
        parent = (
            db.session.query(File)
            .filter_by(
                id=parent_id, mime_type="application/x-directory", deleted_at=None
            )
            .first()
        )
        if parent is None:
            audit.log_action(
                "folder_create",
                user_ip,
                {"error": f"Parent folder {parent_id} not found"},
                False,
            )
            return jsonify({"error": "Parent folder not found"}), 404

    # Generate folder ID
    import uuid

    folder_id = str(uuid.uuid4())

    # Get current time with timezone
    settings = current_app.config.get("VAULT_SETTINGS")
    if settings:
        from zoneinfo import ZoneInfo

        current_time = datetime.now(settings.timezone)
    else:
        current_time = datetime.now(timezone.utc)

    # Get current user ID
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    current_user_id = user.id

    # Check for duplicate folder names in the same parent (using name hash)
    if _check_duplicate_folder_name(vaultspace_id, parent_id, name_hash):
        audit.log_action(
            "folder_create",
            user_ip,
            {
                "error": "duplicate_folder_name",
                "parent_id": parent_id,
                "vaultspace_id": vaultspace_id,
            },
            False,
        )
        return (
            jsonify(
                {"error": "A folder with this name already exists in this location"}
            ),
            409,
        )

    try:
        # Create folder as a File with mime_type='application/x-directory'
        folder_obj = File(
            id=folder_id,
            vaultspace_id=vaultspace_id,
            parent_id=parent_id,
            owner_user_id=current_user_id,
            original_name=encrypted_name,  # Store encrypted name in original_name
            size=0,
            encrypted_size=0,
            encrypted_hash=name_hash,  # Store name_hash in encrypted_hash
            encrypted_metadata=encrypted_name,  # Also store in metadata
            storage_ref="",  # Folders don't have storage
            mime_type="application/x-directory",
            created_at=current_time,
            updated_at=current_time,
        )
        db.session.add(folder_obj)
        db.session.commit()

        audit.log_action(
            "folder_create",
            user_ip,
            {
                "folder_id": folder_id,
                "parent_id": parent_id,
            },
            True,
        )

        # Return folder dict
        folder_dict = {
            "folder_id": folder_obj.id,
            "encrypted_name": folder_obj.original_name,
            "name_hash": folder_obj.encrypted_hash,
            "parent_id": folder_obj.parent_id,
            "created_at": folder_obj.created_at.isoformat(),
            "updated_at": folder_obj.updated_at.isoformat(),
        }
        return jsonify(folder_dict), 201
    except Exception as e:
        db.session.rollback()
        audit.log_action(
            "folder_create",
            user_ip,
            {"error": str(e), "folder_id": folder_id},
            False,
        )
        return jsonify({"error": str(e)}), 400


@folders_bp.route("/api/folders/<folder_id>", methods=["GET"])
@jwt_required
def get_folder(folder_id: str):
    """Get folder contents (files and subfolders)."""
    from vault.database.schema import File, User, GlobalRole, db

    folder_obj = (
        db.session.query(File)
        .filter_by(id=folder_id, mime_type="application/x-directory", deleted_at=None)
        .first()
    )
    if not folder_obj:
        return jsonify({"error": "Folder not found"}), 404

    # Get current user ID and check if admin
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    current_user_id = user.id
    # Check if user is admin
    user_obj = (
        db.session.query(User).filter_by(id=current_user_id, is_active=True).first()
    )
    is_admin = False
    if user_obj:
        is_admin = user_obj.global_role in (GlobalRole.ADMIN, GlobalRole.SUPERADMIN)

    # Get files in this folder (non-directory files)
    files_query = (
        db.session.query(File)
        .filter_by(parent_id=folder_id, deleted_at=None)
        .filter(File.mime_type != "application/x-directory")
    )

    if not is_admin:
        files_query = files_query.filter_by(owner_user_id=current_user_id)

    file_objs = files_query.all()

    # Get subfolders (directory files)
    folders_query = db.session.query(File).filter_by(
        parent_id=folder_id, mime_type="application/x-directory", deleted_at=None
    )

    if not is_admin:
        folders_query = folders_query.filter_by(owner_user_id=current_user_id)

    folder_objs = folders_query.all()

    # Convert to dict format
    folder_dict = {
        "folder_id": folder_obj.id,
        "encrypted_name": folder_obj.original_name,
        "name_hash": folder_obj.encrypted_hash,
        "parent_id": folder_obj.parent_id,
        "created_at": folder_obj.created_at.isoformat(),
        "updated_at": folder_obj.updated_at.isoformat(),
    }

    from vault.models import FileMetadata

    files = []
    for file_obj in file_objs:
        metadata = FileMetadata(
            file_id=file_obj.id,
            original_name=file_obj.original_name,
            size=file_obj.size,
            encrypted_size=file_obj.encrypted_size,
            created_at=file_obj.created_at,
            encrypted_hash=file_obj.encrypted_hash,
            folder_id=file_obj.parent_id,
            encrypted_tags=None,
            encrypted_description=file_obj.encrypted_metadata,
            mime_type=file_obj.mime_type,
            thumbnail_hash=None,
            user_id=file_obj.owner_user_id,
        )
        files.append(metadata)

    subfolders = []
    for folder_obj in folder_objs:
        subfolder_dict = {
            "folder_id": folder_obj.id,
            "encrypted_name": folder_obj.original_name,
            "name_hash": folder_obj.encrypted_hash,
            "parent_id": folder_obj.parent_id,
            "created_at": folder_obj.created_at.isoformat(),
            "updated_at": folder_obj.updated_at.isoformat(),
        }
        subfolders.append(subfolder_dict)

    return (
        jsonify(
            {
                "folder": folder_dict,
                "files": [f.to_dict() for f in files],
                "subfolders": subfolders,
            }
        ),
        200,
    )


@folders_bp.route("/api/folders/<folder_id>", methods=["PUT"])
@jwt_required
def update_folder(folder_id: str):
    """Update folder metadata (rename or move)."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    if not request.is_json:
        audit.log_action(
            "folder_update",
            user_ip,
            {"error": "Request must be JSON", "folder_id": folder_id},
            False,
        )
        return jsonify({"error": "Request must be JSON"}), 400

    from vault.database.schema import File, db

    # Verify folder exists
    folder_obj = (
        db.session.query(File)
        .filter_by(id=folder_id, mime_type="application/x-directory", deleted_at=None)
        .first()
    )
    if not folder_obj:
        audit.log_action(
            "folder_update",
            user_ip,
            {"error": "Folder not found", "folder_id": folder_id},
            False,
        )
        return jsonify({"error": "Folder not found"}), 404

    data = request.json
    encrypted_name = data.get("encrypted_name")
    name_hash = data.get("name_hash")
    parent_id = data.get("parent_id")  # Can be explicit None to move to root

    # Validate parent_id if provided (must be a folder and not create cycle)
    if parent_id is not None:
        parent = (
            db.session.query(File)
            .filter_by(
                id=parent_id, mime_type="application/x-directory", deleted_at=None
            )
            .first()
        )
        if parent is None:
            audit.log_action(
                "folder_update",
                user_ip,
                {
                    "error": f"Parent folder {parent_id} not found",
                    "folder_id": folder_id,
                },
                False,
            )
            return jsonify({"error": "Parent folder not found"}), 404

        # Check for cycle (parent cannot be a descendant of folder_id)
        current_parent = parent_id
        visited = set()
        while current_parent is not None:
            if current_parent == folder_id:
                audit.log_action(
                    "folder_update",
                    user_ip,
                    {
                        "error": "Cannot move folder into itself or descendant",
                        "folder_id": folder_id,
                    },
                    False,
                )
                return (
                    jsonify({"error": "Cannot move folder into itself or descendant"}),
                    400,
                )
            if current_parent in visited:
                break
            visited.add(current_parent)
            parent_obj = (
                db.session.query(File)
                .filter_by(
                    id=current_parent,
                    mime_type="application/x-directory",
                    deleted_at=None,
                )
                .first()
            )
            if not parent_obj:
                break
            current_parent = parent_obj.parent_id

    # Get current time with timezone
    settings = current_app.config.get("VAULT_SETTINGS")
    if settings:
        from zoneinfo import ZoneInfo

        current_time = datetime.now(settings.timezone)
    else:
        current_time = datetime.now(timezone.utc)

    try:
        # Check for duplicate folder names if name is being updated
        if name_hash is not None:
            # Check for duplicates in the target parent (which may be different if moving)
            target_parent_id = (
                parent_id if parent_id is not None else folder_obj.parent_id
            )
            if _check_duplicate_folder_name(
                folder_obj.vaultspace_id,
                target_parent_id,
                name_hash,
                exclude_folder_id=folder_id,
            ):
                audit.log_action(
                    "folder_update",
                    user_ip,
                    {
                        "error": "duplicate_folder_name",
                        "folder_id": folder_id,
                        "parent_id": target_parent_id,
                    },
                    False,
                )
                return (
                    jsonify(
                        {
                            "error": "A folder with this name already exists in this location"
                        }
                    ),
                    409,
                )

        # Update folder
        if encrypted_name is not None:
            folder_obj.original_name = encrypted_name
        if name_hash is not None:
            folder_obj.encrypted_hash = name_hash
        if parent_id is not None:
            folder_obj.parent_id = parent_id
        folder_obj.updated_at = current_time
        db.session.commit()

        audit.log_action(
            "folder_update",
            user_ip,
            {
                "folder_id": folder_id,
                "parent_id": parent_id,
            },
            True,
        )

        folder_dict = {
            "folder_id": folder_obj.id,
            "encrypted_name": folder_obj.original_name,
            "name_hash": folder_obj.encrypted_hash,
            "parent_id": folder_obj.parent_id,
            "created_at": folder_obj.created_at.isoformat(),
            "updated_at": folder_obj.updated_at.isoformat(),
        }
        return jsonify(folder_dict), 200
    except Exception as e:
        db.session.rollback()
        audit.log_action(
            "folder_update",
            user_ip,
            {"error": str(e), "folder_id": folder_id},
            False,
        )
        return jsonify({"error": str(e)}), 400


@folders_bp.route("/api/folders/<folder_id>", methods=["DELETE"])
@jwt_required
def delete_folder(folder_id: str):
    """Delete a folder."""
    user_ip = get_client_ip() or "unknown"
    audit = _get_audit()

    from vault.database.schema import File, db

    folder_obj = (
        db.session.query(File)
        .filter_by(id=folder_id, mime_type="application/x-directory", deleted_at=None)
        .first()
    )
    if not folder_obj:
        audit.log_action(
            "folder_delete",
            user_ip,
            {"error": "Folder not found", "folder_id": folder_id},
            False,
        )
        return jsonify({"error": "Folder not found"}), 404

    # Check if recursive deletion is requested
    recursive = request.args.get("recursive", "false").lower() == "true"

    try:
        if recursive:
            # Recursively delete all children (files and subfolders)
            def delete_recursive(parent_id):
                children = (
                    db.session.query(File)
                    .filter_by(parent_id=parent_id, deleted_at=None)
                    .all()
                )
                for child in children:
                    delete_recursive(child.id)
                    child.deleted_at = datetime.now(timezone.utc)

            delete_recursive(folder_id)

        # Soft delete the folder
        folder_obj.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        audit.log_action(
            "folder_delete",
            user_ip,
            {
                "folder_id": folder_id,
                "recursive": recursive,
            },
            True,
        )
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        audit.log_action(
            "folder_delete",
            user_ip,
            {"error": str(e), "folder_id": folder_id},
            False,
        )
        return jsonify({"error": str(e)}), 500


@folders_bp.route("/api/folders/<folder_id>/path", methods=["GET"])
@jwt_required
def get_folder_path(folder_id: str):
    """Get the path from root to the specified folder."""
    from vault.database.schema import File, db

    folder_obj = (
        db.session.query(File)
        .filter_by(id=folder_id, mime_type="application/x-directory", deleted_at=None)
        .first()
    )
    if not folder_obj:
        return jsonify({"error": "Folder not found"}), 404

    # Build path by traversing up the parent chain
    path = []
    current = folder_obj
    visited = set()

    while current is not None:
        if current.id in visited:
            break  # Avoid cycles
        visited.add(current.id)

        folder_dict = {
            "folder_id": current.id,
            "encrypted_name": current.original_name,
            "name_hash": current.encrypted_hash,
            "parent_id": current.parent_id,
            "created_at": current.created_at.isoformat(),
            "updated_at": current.updated_at.isoformat(),
        }
        path.insert(0, folder_dict)

        if current.parent_id:
            current = (
                db.session.query(File)
                .filter_by(
                    id=current.parent_id,
                    mime_type="application/x-directory",
                    deleted_at=None,
                )
                .first()
            )
        else:
            current = None

    return jsonify({"path": path}), 200


@folders_bp.route("/api/folders", methods=["GET"])
@jwt_required
def list_folders():
    """List folders, optionally filtered by parent."""
    from vault.database.schema import File, User, GlobalRole, db

    parent_id = request.args.get("parent_id")  # None for root folders
    if parent_id == "":
        parent_id = None

    # Get current user ID and check if admin
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    current_user_id = user.id
    # Check if user is admin
    user_obj = (
        db.session.query(User).filter_by(id=current_user_id, is_active=True).first()
    )
    is_admin = False
    if user_obj:
        is_admin = user_obj.global_role in (GlobalRole.ADMIN, GlobalRole.SUPERADMIN)

    # Query folders (files with mime_type='application/x-directory')
    query = db.session.query(File).filter_by(
        mime_type="application/x-directory", deleted_at=None
    )

    if not is_admin:
        query = query.filter_by(owner_user_id=current_user_id)

    if parent_id is not None:
        query = query.filter_by(parent_id=parent_id)
    else:
        query = query.filter_by(parent_id=None)

    folder_objs = query.all()

    folders = []
    for folder_obj in folder_objs:
        folder_dict = {
            "folder_id": folder_obj.id,
            "encrypted_name": folder_obj.original_name,
            "name_hash": folder_obj.encrypted_hash,
            "parent_id": folder_obj.parent_id,
            "created_at": folder_obj.created_at.isoformat(),
            "updated_at": folder_obj.updated_at.isoformat(),
        }
        folders.append(folder_dict)

    return jsonify({"folders": folders}), 200


__all__ = ["folders_bp"]
