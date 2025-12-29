"""File events API blueprint for real-time file synchronization via SSE."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from datetime import timedelta
from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    jsonify,
    make_response,
    request,
    stream_with_context,
)
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required
from vault.services.file_event_service import (
    FileEventService,
    get_file_event_service,
)

logger = logging.getLogger(__name__)

file_events_api_bp = Blueprint(
    "file_events_api", __name__, url_prefix="/api/v2/files/events"
)


def _get_file_event_service() -> FileEventService:
    """Get the file event service instance."""
    return get_file_event_service()


@file_events_api_bp.route("", methods=["GET"])
@csrf.exempt  # SSE doesn't support CSRF tokens
def stream_file_events():
    """Stream file events via Server-Sent Events (SSE).

    Query parameters:
        - vaultspace_id: VaultSpace ID to subscribe to (required)
        - last_event_timestamp: ISO timestamp of last received event (optional, for catch-up)
    Cookies:
        - sse_token: JWT token in HttpOnly cookie (preferred method)

    Returns:
        SSE stream of file events
    """
    token = request.cookies.get("sse_token")

    if not token:
        # Fallback to query parameter (deprecated but kept for compatibility)
        token = request.args.get("token")
        if token:
            logger.warning(
                "Token passed as query parameter is deprecated. "
                "Use /api/v2/files/events/session to establish SSE session with cookie."
            )

    if not token:
        # Fallback to Authorization header if available (for testing with curl, etc.)
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

    if not token:
        return Response("Authentication required", status=401)

    # Validate token manually (same logic as jwt_required middleware)
    from vault.services.auth_service import AuthService
    from vault.services.api_key_service import ApiKeyService

    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        return Response("Server configuration error", status=500)

    settings = current_app.config.get("VAULT_SETTINGS")
    jwt_expiration_hours = settings.jwt_expiration_hours if settings else 120
    auth_service = AuthService(secret_key, jwt_expiration_hours=jwt_expiration_hours)
    user = auth_service.verify_token(token)

    if not user:
        api_key_service = ApiKeyService(secret_key=secret_key)
        user = api_key_service.verify_api_key(token)

    if not user:
        return Response("Invalid or expired token", status=401)

    # Store user in Flask g for consistency
    g.current_user = user

    vaultspace_id = request.args.get("vaultspace_id")
    if not vaultspace_id:
        return Response("vaultspace_id parameter is required", status=400)

    # Parse last event timestamp if provided
    last_event_timestamp = None
    last_timestamp_str = request.args.get("last_event_timestamp")
    if last_timestamp_str:
        try:
            last_event_timestamp = datetime.fromisoformat(
                last_timestamp_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            logger.warning(f"Invalid last_event_timestamp format: {last_timestamp_str}")

    # Verify user has access to this VaultSpace
    try:
        from vault.services.vaultspace_service import VaultSpaceService

        vaultspace_service = VaultSpaceService()
        vaultspace = vaultspace_service.get_vaultspace(vaultspace_id)
        if not vaultspace:
            return Response("VaultSpace not found", status=404)

        # Check if user is owner or has a VaultSpace key (shared access)
        has_access = False
        if vaultspace.owner_user_id == user.id:
            has_access = True
        else:
            # Check if user has a VaultSpace key (shared access)
            vaultspace_key = vaultspace_service.get_vaultspace_key(
                vaultspace_id, user.id
            )
            if vaultspace_key:
                has_access = True

        if not has_access:
            return Response("VaultSpace access denied", status=403)
    except Exception as e:
        logger.error(f"Error verifying VaultSpace access: {e}", exc_info=True)
        return Response("Error verifying access", status=500)

    event_service = _get_file_event_service()

    @stream_with_context
    def generate_events():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'vaultspace_id': vaultspace_id})}\n\n"

            # Get event stream
            event_stream = event_service.get_event_stream(
                vaultspace_id=vaultspace_id,
                last_event_timestamp=last_event_timestamp,
            )

            # Stream events
            for event in event_stream:
                try:
                    # Skip heartbeat events (they're just to keep connection alive)
                    if event.data and event.data.get("type") == "heartbeat":
                        # Send a simple heartbeat comment to keep connection alive
                        yield ": heartbeat\n\n"
                        continue

                    event_data = {
                        "type": "file_event",
                        "event": event.to_dict(),
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                except Exception as e:
                    logger.error(f"Error serializing event: {e}", exc_info=True)
                    continue

        except (GeneratorExit, StopIteration):
            # Client disconnected
            logger.debug(f"SSE client disconnected for vaultspace {vaultspace_id}")
        except Exception as e:
            logger.error(
                f"Error in SSE stream for vaultspace {vaultspace_id}: {e}",
                exc_info=True,
            )
            # Send error event
            try:
                error_data = {
                    "type": "error",
                    "message": "Stream error occurred",
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            except Exception:
                pass

    response = Response(
        generate_events(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        },
    )
    return response


@file_events_api_bp.route("/session", methods=["POST"])
@csrf.exempt
@jwt_required
def establish_sse_session():
    """Establish SSE session by setting authentication cookie.

    This endpoint validates the JWT token from Authorization header
    and sets a secure HttpOnly cookie for SSE authentication.
    This prevents token exposure in URLs, browser history, and logs.

    Request headers:
        Authorization: Bearer <token>

    Returns:
        JSON with success status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header required"}), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid Authorization header format"}), 401

    token = parts[1]

    # Create response
    response = make_response(
        jsonify({"status": "success", "message": "SSE session established"})
    )

    # Set SSE token in HttpOnly cookie for security
    # This prevents token exposure in URL, browser history, logs, and Referer headers
    settings = current_app.config.get("VAULT_SETTINGS")
    jwt_expiration_hours = settings.jwt_expiration_hours if settings else 120
    session_cookie_secure = settings.session_cookie_secure if settings else True

    # Calculate cookie expiration based on JWT expiration
    from datetime import datetime, timezone

    expires = datetime.now(timezone.utc) + timedelta(hours=jwt_expiration_hours)

    response.set_cookie(
        "sse_token",
        token,
        expires=expires,
        httponly=True,
        secure=session_cookie_secure,
        samesite="Lax",
        path="/api/v2/files/events",
    )

    return response


@file_events_api_bp.route("/recent", methods=["GET"])
@csrf.exempt
@jwt_required
def get_recent_events():
    """Get recent file events for a VaultSpace.

    Query parameters:
        - vaultspace_id: VaultSpace ID (required)
        - limit: Maximum number of events to return (default: 50)

    Returns:
        JSON with list of recent events
    """
    user = get_current_user()
    if not user:
        return Response("Authentication required", status=401)

    vaultspace_id = request.args.get("vaultspace_id")
    if not vaultspace_id:
        return Response("vaultspace_id parameter is required", status=400)

    limit = request.args.get("limit", 50, type=int)
    if limit < 1 or limit > 1000:
        limit = 50

    # Verify user has access to this VaultSpace
    try:
        from vault.services.vaultspace_service import VaultSpaceService

        vaultspace_service = VaultSpaceService()
        vaultspace = vaultspace_service.get_vaultspace(vaultspace_id)
        if not vaultspace:
            return Response("VaultSpace not found", status=404)

        # Check if user is owner or has a VaultSpace key (shared access)
        has_access = False
        if vaultspace.owner_user_id == user.id:
            has_access = True
        else:
            # Check if user has a VaultSpace key (shared access)
            vaultspace_key = vaultspace_service.get_vaultspace_key(
                vaultspace_id, user.id
            )
            if vaultspace_key:
                has_access = True

        if not has_access:
            return Response("VaultSpace access denied", status=403)
    except Exception as e:
        logger.error(f"Error verifying VaultSpace access: {e}", exc_info=True)
        return Response("Error verifying access", status=500)

    event_service = _get_file_event_service()
    events = event_service.get_recent_events(vaultspace_id=vaultspace_id, limit=limit)

    from flask import jsonify

    return jsonify(
        {
            "events": [event.to_dict() for event in events],
            "total": len(events),
        }
    )
