"""VaultSpace API routes for Leyzen Vault."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required

from vault.services.vaultspace_service import VaultSpaceService
from vault.blueprints.validators import validate_vaultspace_id

vaultspace_api_bp = Blueprint("vaultspace_api", __name__, url_prefix="/api/vaultspaces")


def _get_vaultspace_service() -> VaultSpaceService:
    """Get VaultSpaceService instance."""
    return VaultSpaceService()


@vaultspace_api_bp.route("", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def create_vaultspace():
    """Create a new VaultSpace.

    Request body:
        {
            "name": "My VaultSpace",
            "encrypted_metadata": "encrypted-metadata" (optional),
            "icon_name": "icon-name" (optional)
        }

    Returns:
        JSON with VaultSpace info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    name = data.get("name", "").strip()
    encrypted_metadata = data.get("encrypted_metadata")
    icon_name = data.get("icon_name")

    if not name:
        return jsonify({"error": "VaultSpace name is required"}), 400

    # Validate icon_name if provided
    if icon_name is not None:
        from vault.utils.valid_icons import is_valid_icon_name

        if icon_name and not is_valid_icon_name(icon_name):
            return jsonify({"error": f"Invalid icon name: {icon_name}"}), 400

    vaultspace_service = _get_vaultspace_service()

    try:
        vaultspace = vaultspace_service.create_vaultspace(
            name=name,
            owner_user_id=user.id,
            encrypted_metadata=encrypted_metadata,
            icon_name=icon_name,
        )
        return (
            jsonify(
                {
                    "vaultspace": vaultspace.to_dict(),
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@vaultspace_api_bp.route("", methods=["GET"])
@jwt_required
def list_vaultspaces():
    """List VaultSpaces for current user.

    Returns:
        JSON with list of VaultSpaces
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_service = _get_vaultspace_service()
    vaultspaces = vaultspace_service.list_vaultspaces(user.id)

    return (
        jsonify(
            {
                "vaultspaces": [vs.to_dict() for vs in vaultspaces],
            }
        ),
        200,
    )


@vaultspace_api_bp.route("/<vaultspace_id>", methods=["GET"])
@jwt_required
def get_vaultspace(vaultspace_id: str):
    """Get VaultSpace details.

    Args:
        vaultspace_id: VaultSpace ID

    Returns:
        JSON with VaultSpace info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    vaultspace_service = _get_vaultspace_service()
    vaultspace = vaultspace_service.get_vaultspace(vaultspace_id)

    if not vaultspace:
        return jsonify({"error": "VaultSpace not found"}), 404

    return (
        jsonify(
            {
                "vaultspace": vaultspace.to_dict(),
            }
        ),
        200,
    )


@vaultspace_api_bp.route("/<vaultspace_id>/share", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def share_vaultspace(vaultspace_id: str):
    """Store VaultSpace key for the owner.

    Request body:
        {
            "encrypted_key": "encrypted-vaultspace-key"
        }

    Returns:
        JSON with VaultSpaceKey info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    encrypted_key = data.get("encrypted_key", "").strip()

    if not encrypted_key:
        return jsonify({"error": "encrypted_key is required"}), 400

    vaultspace_service = _get_vaultspace_service()

    try:
        vaultspace_key = vaultspace_service.store_vaultspace_key_for_user(
            vaultspace_id,
            user.id,
            encrypted_key,
        )
        return (
            jsonify(
                {
                    "vaultspace_key": vaultspace_key.to_dict(),
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@vaultspace_api_bp.route("/<vaultspace_id>/keys", methods=["GET"])
@jwt_required
def get_vaultspace_keys(vaultspace_id: str):
    """Get encrypted VaultSpace keys for current user.

    Args:
        vaultspace_id: VaultSpace ID

    Returns:
        JSON with encrypted key, or error message if key needs to be created
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    vaultspace_service = _get_vaultspace_service()
    vaultspace = vaultspace_service.get_vaultspace(vaultspace_id)

    if not vaultspace:
        return jsonify({"error": "VaultSpace not found"}), 404

    vaultspace_key = vaultspace_service.get_vaultspace_key(vaultspace_id, user.id)

    if not vaultspace_key:
        # Return a helpful error message indicating the key needs to be created
        # The frontend should call POST /share to create the key
        return (
            jsonify(
                {
                    "error": "VaultSpace key not found. Please store the key first using POST /api/vaultspaces/{vaultspace_id}/share",
                    "code": "KEY_NOT_FOUND",
                    "vaultspace_id": vaultspace_id,
                    "needs_key_creation": True,
                }
            ),
            404,
        )

    return (
        jsonify(
            {
                "vaultspace_key": vaultspace_key.to_dict(),
            }
        ),
        200,
    )


@vaultspace_api_bp.route("/<vaultspace_id>", methods=["PUT"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def update_vaultspace(vaultspace_id: str):
    """Update VaultSpace metadata.

    Request body:
        {
            "name": "New Name" (optional),
            "encrypted_metadata": "encrypted-metadata" (optional)
        }

    Returns:
        JSON with updated VaultSpace info
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    name = data.get("name")
    encrypted_metadata = data.get("encrypted_metadata")
    icon_name = data.get("icon_name")

    # Validate icon_name if provided
    if icon_name is not None:
        from vault.utils.valid_icons import is_valid_icon_name

        if icon_name and not is_valid_icon_name(icon_name):
            return jsonify({"error": f"Invalid icon name: {icon_name}"}), 400

    vaultspace_service = _get_vaultspace_service()

    try:
        vaultspace = vaultspace_service.update_vaultspace(
            vaultspace_id=vaultspace_id,
            name=name.strip() if name else None,
            encrypted_metadata=encrypted_metadata,
            icon_name=icon_name,
        )

        if not vaultspace:
            return jsonify({"error": "VaultSpace not found"}), 404

        return (
            jsonify(
                {
                    "vaultspace": vaultspace.to_dict(),
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@vaultspace_api_bp.route("/<vaultspace_id>", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def delete_vaultspace(vaultspace_id: str):
    """Delete a VaultSpace.

    Args:
        vaultspace_id: VaultSpace ID

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_service = _get_vaultspace_service()

    try:
        success = vaultspace_service.delete_vaultspace(vaultspace_id, user.id)

        if not success:
            return jsonify({"error": "VaultSpace not found"}), 404

        return (
            jsonify(
                {
                    "message": "VaultSpace deleted successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@vaultspace_api_bp.route("/<vaultspace_id>/pin", methods=["POST"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def pin_vaultspace(vaultspace_id: str):
    """Pin a VaultSpace for quick access.

    Args:
        vaultspace_id: VaultSpace ID to pin

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    vaultspace_service = _get_vaultspace_service()

    try:
        pinned = vaultspace_service.pin_vaultspace(user.id, vaultspace_id)
        return (
            jsonify(
                {
                    "message": "VaultSpace pinned successfully",
                    "pinned": pinned.to_dict(),
                }
            ),
            201,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@vaultspace_api_bp.route("/<vaultspace_id>/pin", methods=["DELETE"])
@csrf.exempt  # JWT-authenticated API endpoint
@jwt_required
def unpin_vaultspace(vaultspace_id: str):
    """Unpin a VaultSpace.

    Args:
        vaultspace_id: VaultSpace ID to unpin

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    if not validate_vaultspace_id(vaultspace_id):
        return jsonify({"error": "Invalid vaultspace_id format"}), 400

    vaultspace_service = _get_vaultspace_service()

    try:
        success = vaultspace_service.unpin_vaultspace(user.id, vaultspace_id)

        if not success:
            return jsonify({"error": "VaultSpace is not pinned"}), 404

        return (
            jsonify(
                {
                    "message": "VaultSpace unpinned successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 403


@vaultspace_api_bp.route("/pinned", methods=["GET"])
@jwt_required
def get_pinned_vaultspaces():
    """Get all pinned VaultSpaces for current user.

    Returns:
        JSON with list of pinned VaultSpaces
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    vaultspace_service = _get_vaultspace_service()
    pinned_vaultspaces = vaultspace_service.get_pinned_vaultspaces(user.id)

    return (
        jsonify(
            {
                "vaultspaces": [vs.to_dict() for vs in pinned_vaultspaces],
            }
        ),
        200,
    )


@vaultspace_api_bp.route("/pinned/order", methods=["PUT"])
@csrf.exempt
@jwt_required
def update_pinned_order():
    """Update the display order of pinned VaultSpaces.

    Request body should contain:
        {
            "vaultspace_ids": ["id1", "id2", ...]
        }

    Returns:
        JSON with success message
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data or "vaultspace_ids" not in data:
        return jsonify({"error": "vaultspace_ids is required"}), 400

    vaultspace_ids = data.get("vaultspace_ids", [])
    if not isinstance(vaultspace_ids, list):
        return jsonify({"error": "vaultspace_ids must be a list"}), 400

    # Validate all IDs
    for vaultspace_id in vaultspace_ids:
        if not validate_vaultspace_id(vaultspace_id):
            return (
                jsonify({"error": f"Invalid vaultspace_id format: {vaultspace_id}"}),
                400,
            )

    vaultspace_service = _get_vaultspace_service()

    try:
        vaultspace_service.update_pinned_order(user.id, vaultspace_ids)
        return (
            jsonify(
                {
                    "message": "Pinned order updated successfully",
                }
            ),
            200,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
