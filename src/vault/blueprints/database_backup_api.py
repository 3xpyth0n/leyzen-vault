"""Database backup API routes."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request

from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required, require_role
from vault.database.schema import GlobalRole, User, DatabaseBackup
from vault.database import db
from vault.config import is_setup_complete
from vault.blueprints.utils import get_client_ip

database_backup_api_bp = Blueprint(
    "database_backup_api", __name__, url_prefix="/api/v2/database-backup"
)


@database_backup_api_bp.route("/config", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_database_backup_config():
    """Get database backup configuration (admin only).

    Returns:
        JSON with configuration (credentials are decrypted)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    from vault.services.database_backup_config_service import (
        DatabaseBackupConfigService,
    )

    config = DatabaseBackupConfigService.get_config(secret_key, current_app)

    if not config:
        return (
            jsonify(
                {
                    "enabled": False,
                    "cron_expression": "",
                    "storage_type": "local",
                    "retention_policy": {"type": "count", "value": 10},
                }
            ),
            200,
        )

    # Return config
    safe_config = {
        "enabled": config.get("enabled", False),
        "cron_expression": config.get("cron_expression", ""),
        "storage_type": config.get("storage_type", "local"),
        "retention_policy": config.get(
            "retention_policy", {"type": "count", "value": 10}
        ),
    }

    return jsonify(safe_config), 200


@database_backup_api_bp.route("/config", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def save_database_backup_config():
    """Save database backup configuration (admin only).

    Request body:
        {
            "enabled": bool,
            "cron_expression": str,
            "storage_type": "local" | "s3",
            "retention_policy": {"type": "count" | "days", "value": int}
        }

    Returns:
        JSON with success status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    from vault.services.database_backup_config_service import (
        DatabaseBackupConfigService,
    )

    # Build config dictionary
    config = {
        "enabled": data.get("enabled", False),
        "cron_expression": data.get("cron_expression", ""),
        "storage_type": data.get("storage_type", "local"),
        "retention_policy": data.get(
            "retention_policy", {"type": "count", "value": 10}
        ),
    }

    try:
        DatabaseBackupConfigService.store_config(secret_key, config, current_app)

        # Audit log
        audit_service = current_app.config.get("VAULT_AUDIT")
        if audit_service:
            user_ip = request.remote_addr or "unknown"
            audit_service.log_action(
                action="database_backup_config_updated",
                user_ip=user_ip,
                details={
                    "enabled": config["enabled"],
                    "storage_type": config["storage_type"],
                },
                success=True,
                user_id=user.id,
            )

        return (
            jsonify({"success": True, "message": "Configuration saved successfully"}),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"Error saving database backup config: {e}")
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500


@database_backup_api_bp.route("/test-connection", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def test_database_connection():
    """Test connection to remote database (admin only).

    Request body:
        {
            "host": str,
            "port": str,
            "database": str,
            "username": str,
            "password": str
        }

    Returns:
        JSON with connection test result
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    host = data.get("host")
    port = data.get("port", "5432")
    database = data.get("database")
    username = data.get("username")
    password = data.get("password")

    if not all([host, database, username, password]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        from sqlalchemy import create_engine, text

        postgres_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        engine = create_engine(
            postgres_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
        )

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.scalar()

        return jsonify({"success": True, "message": "Connection successful"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200


@database_backup_api_bp.route("/list-public", methods=["GET"])
@csrf.exempt  # Public endpoint for setup
def list_backups_public():
    """List available local database backups (public endpoint for setup).

    This endpoint is only available when database is empty (no users).
    Storage-first approach: scans storage directly, no database access required.

    Returns:
        JSON with list of backups
    """
    try:
        # Check if database is empty (setup not complete)
        if is_setup_complete(current_app):
            return jsonify({"error": "Database already initialized"}), 403

        secret_key = current_app.config.get("SECRET_KEY", "")
        if not secret_key:
            return jsonify({"error": "SECRET_KEY not configured"}), 500

        from vault.services.database_backup_service import DatabaseBackupService

        backup_service = DatabaseBackupService(secret_key, current_app)
        # Discover backups from storage (local only for public endpoint)
        backups = backup_service._discover_backups_from_storage()

        # Format for public endpoint (simplified)
        formatted_backups = []
        for backup in backups:
            backup_id = backup.get("id")
            if backup_id:
                # Extract UUID from full backup_id if needed
                # For public endpoint, we use the full backup_id
                formatted_backups.append(
                    {
                        "id": backup_id,
                        "created_at": backup.get("created_at"),
                        "size_bytes": backup.get("size_bytes", 0),
                        "backup_type": backup.get("backup_type", "local"),
                        "status": backup.get("status", "completed"),
                        "storage_location": backup.get("storage_location", ""),
                    }
                )

        # Sort by creation time (most recent first)
        formatted_backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jsonify({"backups": formatted_backups}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing backups: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@database_backup_api_bp.route("/backups", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def list_database_backups():
    """List all database backups (admin only).

    Returns:
        JSON with list of backups
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    try:
        from vault.services.database_backup_service import DatabaseBackupService

        backup_service = DatabaseBackupService(secret_key, current_app)
        backups = backup_service.list_backups()

        return jsonify({"backups": backups}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing backups: {e}")
        return jsonify({"error": f"Failed to list backups: {str(e)}"}), 500


@database_backup_api_bp.route("/backup", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def create_database_backup():
    """Create a manual database backup (admin only).

    Returns:
        JSON with backup status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    # Check if backup is already running
    backup_running = current_app.config.get("DATABASE_BACKUP_RUNNING", False)
    if backup_running:
        return jsonify({"error": "Backup is already in progress"}), 409

    current_app.logger.info("[BACKUP] Starting manual backup...")

    try:
        from vault.services.database_backup_service import DatabaseBackupService

        # Capture app instance before starting thread
        app_instance = current_app._get_current_object()
        user_id = user.id
        user_ip = get_client_ip() or "unknown"

        # Mark backup as running
        current_app.config["DATABASE_BACKUP_RUNNING"] = True

        data = request.get_json() or {}
        storage_type = data.get("storage_type", "local")

        def backup_worker():
            """Background worker to perform backup."""
            with app_instance.app_context():
                try:
                    backup_service_worker = DatabaseBackupService(
                        secret_key, app_instance
                    )
                    backup_record = backup_service_worker.create_backup(
                        backup_type="manual", storage_type=storage_type
                    )

                    # Audit log
                    audit_service = app_instance.config.get("VAULT_AUDIT")
                    if audit_service:
                        audit_service.log_action(
                            action="database_backup_created",
                            user_ip=user_ip,
                            details={
                                "backup_id": backup_record.id,
                            },
                            success=True,
                            user_id=user_id,
                        )

                    app_instance.logger.info(
                        f"[BACKUP] Manual backup completed: {backup_record.id}"
                    )
                except Exception as e:
                    app_instance.logger.error(
                        f"[BACKUP] Manual backup failed: {e}", exc_info=True
                    )

                    # Audit log
                    audit_service = app_instance.config.get("VAULT_AUDIT")
                    if audit_service:
                        audit_service.log_action(
                            action="database_backup_created",
                            user_ip=user_ip,
                            details={"error": str(e)},
                            success=False,
                            user_id=user_id,
                        )
                finally:
                    app_instance.config["DATABASE_BACKUP_RUNNING"] = False

        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()

        return (
            jsonify({"success": True, "message": "Backup started in background"}),
            200,
        )
    except Exception as e:
        current_app.config["DATABASE_BACKUP_RUNNING"] = False
        current_app.logger.error(f"Error starting backup: {e}")
        return jsonify({"error": f"Failed to start backup: {str(e)}"}), 500


@database_backup_api_bp.route("/restore-public", methods=["POST"])
@csrf.exempt  # Public endpoint for setup
def restore_database_backup_public():
    """Restore database from a backup (public endpoint for setup).

    This endpoint is only available when database is empty (no users).

    Request body:
        {
            "backup_id": str (filename without .dump extension)
        }

    Returns:
        JSON with restore status
    """
    # Check if database is empty (setup not complete)
    if is_setup_complete(current_app):
        return jsonify({"error": "Database already initialized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    backup_id = data.get("backup_id")
    if not backup_id:
        return jsonify({"error": "backup_id is required"}), 400

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    # Check if restore is already running
    restore_running = current_app.config.get("DATABASE_RESTORE_RUNNING", False)
    if restore_running:
        return jsonify({"error": "Restore is already in progress"}), 409

    # Enable maintenance mode
    current_app.config["MAINTENANCE_MODE"] = True

    current_app.logger.info(
        f"[RESTORE PUBLIC] Starting restore from backup {backup_id}..."
    )

    try:
        from vault.services.database_backup_service import DatabaseBackupService

        # Storage-first: find backup in storage (no database access)
        backup_service = DatabaseBackupService(secret_key, current_app)
        backup_file, metadata_path = backup_service._find_backup_by_id_in_storage(
            backup_id
        )

        if not backup_file or not backup_file.exists():
            return jsonify({"error": f"Backup file not found: {backup_id}"}), 404

        # Capture app instance before starting thread
        app_instance = current_app._get_current_object()

        # Mark restore as running
        current_app.config["DATABASE_RESTORE_RUNNING"] = True

        def restore_worker():
            """Background worker to perform restore."""
            with app_instance.app_context():
                try:
                    backup_service_worker = DatabaseBackupService(
                        secret_key, app_instance
                    )

                    # Use radical restore approach (DROP SCHEMA CASCADE)
                    result = backup_service_worker.restore_backup_radical(
                        backup_file, backup_id
                    )

                    # Clear any previous error
                    app_instance.config.pop("DATABASE_RESTORE_ERROR", None)
                    app_instance.logger.info(
                        f"[RESTORE PUBLIC] Restore from backup {backup_id} completed successfully"
                    )
                except Exception as e:
                    error_details = str(e)
                    if hasattr(e, "stderr") and e.stderr:
                        error_details += f"\nError output: {e.stderr}"
                    if hasattr(e, "stdout") and e.stdout:
                        error_details += f"\nOutput: {e.stdout}"
                    app_instance.logger.error(
                        f"[RESTORE PUBLIC] Restore from backup {backup_id} failed: {error_details}",
                        exc_info=True,
                    )
                    # Store generic error message for frontend (security: don't expose details)
                    # Detailed error logs remain in backend logs (docker logs, etc.)
                    app_instance.config["DATABASE_RESTORE_ERROR"] = (
                        "Database restore failed. Please check server logs for details."
                    )
                finally:
                    app_instance.config["DATABASE_RESTORE_RUNNING"] = False
                    app_instance.config["MAINTENANCE_MODE"] = False

        thread = threading.Thread(target=restore_worker, daemon=True)
        thread.start()

        return (
            jsonify({"success": True, "message": "Restore started in background"}),
            200,
        )
    except Exception as e:
        current_app.config["DATABASE_RESTORE_RUNNING"] = False
        current_app.config["MAINTENANCE_MODE"] = False
        current_app.logger.error(f"Error starting restore: {e}")
        return jsonify({"error": f"Failed to start restore: {str(e)}"}), 500


@database_backup_api_bp.route("/restore", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def restore_database_backup():
    """Restore database from a backup (admin only).

    Request body:
        {
            "backup_id": str
        }

    Returns:
        JSON with restore status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    backup_id = data.get("backup_id")
    if not backup_id:
        return jsonify({"error": "backup_id is required"}), 400

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    # Check if restore is already running
    restore_running = current_app.config.get("DATABASE_RESTORE_RUNNING", False)
    if restore_running:
        return jsonify({"error": "Restore is already in progress"}), 409

    # Enable maintenance mode
    current_app.config["MAINTENANCE_MODE"] = True

    try:
        from vault.services.database_backup_service import DatabaseBackupService
        from vault.services.auth_service import AuthService

        # Invalidate all user sessions before restore (disconnect all users)
        # This is critical for security - all users must be logged out before restore
        try:
            auth_service = AuthService(secret_key)
            invalidated_count = auth_service.invalidate_all_sessions()
            current_app.logger.info(
                f"[RESTORE] Invalidated {invalidated_count} user sessions before restore"
            )
        except Exception as e:
            # Log but don't fail - database may be unavailable
            current_app.logger.warning(
                f"[RESTORE] Failed to invalidate sessions (non-critical): {e}"
            )

        # Storage-first: find backup in storage (no database queries)
        backup_service = DatabaseBackupService(secret_key, current_app)
        backup_path_final, metadata_path = backup_service._find_backup_by_id_in_storage(
            backup_id
        )

        if not backup_path_final or not backup_path_final.exists():
            current_app.logger.error(
                f"[RESTORE] Backup {backup_id} not found in storage"
            )
            current_app.config["DATABASE_RESTORE_RUNNING"] = False
            current_app.config["MAINTENANCE_MODE"] = False
            return (
                jsonify(
                    {"error": f"Backup {backup_id} not found in storage (local or S3)"}
                ),
                404,
            )

        # Capture app instance, user ID, and user IP before starting thread
        # CRITICAL: Capture user.id (not user object) to avoid SQLAlchemy detached instance error
        app_instance = current_app._get_current_object()
        user_id = user.id
        user_ip = get_client_ip() or "unknown"

        # Log restore start with timestamp (Docker log)
        start_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        current_app.logger.info(
            f"[RESTORE] [{start_timestamp}] Database restore started"
        )

        # Audit log for restore start (interface web)
        audit_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        audit_service = current_app.config.get("VAULT_AUDIT")
        if audit_service:
            audit_service.log_action(
                action="database_backup_restore_started",
                user_ip=user_ip,
                details={
                    "message": "Database restore started",
                    "date_time": audit_timestamp,
                    "user_email": user.email,
                    "ip": user_ip,
                },
                success=True,
                user_id=user_id,
            )

        # Mark restore as running
        current_app.config["DATABASE_RESTORE_RUNNING"] = True

        def restore_worker():
            """Background worker to perform restore."""
            with app_instance.app_context():
                try:
                    backup_service_worker = DatabaseBackupService(
                        secret_key, app_instance
                    )
                    # Use radical restore approach (DROP SCHEMA CASCADE)
                    result = backup_service_worker.restore_backup_radical(
                        backup_path_final, backup_id
                    )

                    # Log restore completion with timestamp (Docker log)
                    end_timestamp = datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                    app_instance.logger.info(
                        f"[RESTORE] [{end_timestamp}] Database restore completed"
                    )
                except Exception as e:
                    # Log restore failure with timestamp (Docker log)
                    end_timestamp = datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                    app_instance.logger.error(
                        f"[RESTORE] [{end_timestamp}] Database restore failed: {e}",
                        exc_info=True,
                    )

                    # Store generic error message for frontend (security: don't expose details)
                    app_instance.config["DATABASE_RESTORE_ERROR"] = (
                        "Database restore failed. Please check server logs for details."
                    )
                finally:
                    app_instance.config["DATABASE_RESTORE_RUNNING"] = False
                    app_instance.config["MAINTENANCE_MODE"] = False

        thread = threading.Thread(target=restore_worker, daemon=True)
        thread.start()

        return (
            jsonify({"success": True, "message": "Restore started in background"}),
            200,
        )
    except Exception as e:
        current_app.config["DATABASE_RESTORE_RUNNING"] = False
        current_app.config["MAINTENANCE_MODE"] = False
        current_app.logger.error(f"Error starting restore: {e}")
        return jsonify({"error": f"Failed to start restore: {str(e)}"}), 500


@database_backup_api_bp.route("/backups/<backup_id>", methods=["DELETE"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def delete_database_backup(backup_id: str):
    """Delete a database backup (admin only).

    Args:
        backup_id: ID of the backup to delete

    Returns:
        JSON with deletion status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    try:
        from vault.services.database_backup_service import DatabaseBackupService

        backup_service = DatabaseBackupService(secret_key, current_app)
        backup_service.delete_backup(backup_id)

        # Audit log
        audit_service = current_app.config.get("VAULT_AUDIT")
        if audit_service:
            user_ip = request.remote_addr or "unknown"
            audit_service.log_action(
                action="database_backup_deleted",
                user_ip=user_ip,
                details={"backup_id": backup_id},
                success=True,
                user_id=user.id,
            )

        return jsonify({"success": True, "message": "Backup deleted successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting backup: {e}")
        return jsonify({"error": f"Failed to delete backup: {str(e)}"}), 500


@database_backup_api_bp.route("/sync", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def sync_database_backups():
    """Synchronize database backups from storage (admin only).

    Scans storage for backup files that are missing from the database
    and creates records for them.

    Returns:
        JSON with sync results
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    try:
        from vault.services.database_backup_service import DatabaseBackupService

        backup_service = DatabaseBackupService(secret_key, current_app)
        result = backup_service.sync_backups_from_storage()

        # Audit log
        audit_service = current_app.config.get("VAULT_AUDIT")
        if audit_service:
            audit_service.log_action(
                action="database_backup_sync",
                user_ip=request.remote_addr or "unknown",
                details=result,
                success=True,
                user_id=user.id,
            )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Backup synchronization completed",
                    "details": result,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error synchronizing backups: {e}")
        return jsonify({"error": f"Failed to sync backups: {str(e)}"}), 500


@database_backup_api_bp.route("/restore-status", methods=["GET"])
@csrf.exempt  # Public endpoint for setup
def get_restore_status():
    """Get restore status (public endpoint for setup).

    Returns:
        JSON with restore status, error if any, and maintenance mode status
    """
    restore_running = current_app.config.get("DATABASE_RESTORE_RUNNING", False)
    restore_error = current_app.config.get("DATABASE_RESTORE_ERROR", None)
    maintenance_mode = current_app.config.get("MAINTENANCE_MODE", False)

    return (
        jsonify(
            {
                "running": restore_running,
                "error": restore_error,
                "maintenance_mode": maintenance_mode,
            }
        ),
        200,
    )


@database_backup_api_bp.route("/status", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_database_backup_status():
    """Get database backup status (admin only).

    Returns:
        JSON with backup status information
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    from vault.services.database_backup_config_service import (
        DatabaseBackupConfigService,
    )

    enabled = DatabaseBackupConfigService.is_enabled(secret_key, current_app)
    worker = current_app.config.get("DATABASE_BACKUP_WORKER")
    worker_running = worker.is_running() if worker else False
    backup_running = current_app.config.get("DATABASE_BACKUP_RUNNING", False)
    restore_running = current_app.config.get("DATABASE_RESTORE_RUNNING", False)

    # Get last backup from storage (storage-first)
    last_backup = None
    try:
        from vault.services.database_backup_service import DatabaseBackupService

        backup_service = DatabaseBackupService(secret_key, current_app)
        backups = backup_service.list_backups()
        if backups:
            last_backup = backups[0]  # Already sorted by created_at desc
    except Exception as e:
        # Log but don't fail - database may be unavailable
        current_app.logger.debug(
            f"Failed to get last backup from storage (non-critical): {e}"
        )

    return (
        jsonify(
            {
                "enabled": enabled,
                "worker_running": worker_running,
                "backup_running": backup_running,
                "restore_running": restore_running,
                "last_backup": last_backup,
            }
        ),
        200,
    )
