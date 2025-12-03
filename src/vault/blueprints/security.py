"""Security dashboard blueprint for Leyzen Vault."""

from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, current_app, jsonify

from ..database.schema import File, GlobalRole, db
from ..services.audit import AuditService
from ..middleware.jwt_auth import jwt_required
from ..middleware.rbac import require_role
from .utils import _settings, get_client_ip

security_bp = Blueprint("security", __name__, url_prefix="/security")


# All frontend routes are handled by Vue.js SPA
# Only API routes remain here


@security_bp.route("/api/stats", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_stats():
    """Get security and storage statistics.

    Restricted to administrators only to prevent cross-tenant information disclosure.
    """
    audit = current_app.config["VAULT_AUDIT"]
    storage = current_app.config["VAULT_STORAGE"]

    # Get all files from PostgreSQL
    files = db.session.query(File).filter(File.deleted_at.is_(None)).all()

    # Calculate statistics
    total_files = len(files)
    total_size = sum(f.size for f in files)
    total_encrypted_size = sum(f.encrypted_size for f in files)
    avg_size = total_size / total_files if total_files > 0 else 0

    # Files by extension
    files_by_type: dict[str, int] = {}
    for file_obj in files:
        ext = (
            file_obj.original_name.split(".")[-1].lower()
            if "." in file_obj.original_name
            else "no-extension"
        )
        files_by_type[ext] = files_by_type.get(ext, 0) + 1

    # Recent activity (last 7 days)
    settings = _settings()
    seven_days_ago = datetime.now(settings.timezone) - timedelta(days=7)
    recent_logs = audit.get_logs(limit=1000)

    # Filter logs: ensure timestamp comparison is timezone-aware
    recent_activity = []
    for log in recent_logs:
        # Ensure log.timestamp is timezone-aware
        log_timestamp = log.timestamp
        if log_timestamp.tzinfo is None:
            # If timestamp is naive, assume it's UTC and convert to settings timezone
            from datetime import timezone

            log_timestamp = log_timestamp.replace(tzinfo=timezone.utc).astimezone(
                settings.timezone
            )
        else:
            # If timestamp is timezone-aware, convert to settings timezone
            log_timestamp = log_timestamp.astimezone(settings.timezone)

        if log_timestamp >= seven_days_ago:
            recent_activity.append(log)

    # Activity breakdown
    activity_by_action: dict[str, int] = {}
    for log in recent_activity:
        activity_by_action[log.action] = activity_by_action.get(log.action, 0) + 1

    # Success/failure rates
    successful_actions = sum(1 for log in recent_activity if log.success)
    failed_actions = len(recent_activity) - successful_actions

    return (
        jsonify(
            {
                "storage": {
                    "total_files": total_files,
                    "total_size": total_size,
                    "total_encrypted_size": total_encrypted_size,
                    "average_size": avg_size,
                    "files_by_type": files_by_type,
                },
                "activity": {
                    "recent_actions": len(recent_activity),
                    "successful_actions": successful_actions,
                    "failed_actions": failed_actions,
                    "by_action": activity_by_action,
                },
                "recent_logs": [
                    log.to_dict() for log in recent_logs[:50]
                ],  # Last 50 logs
            }
        ),
        200,
    )


__all__ = ["security_bp"]
