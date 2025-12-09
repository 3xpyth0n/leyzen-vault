"""External storage API routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required, require_role
from vault.database.schema import GlobalRole

external_storage_api_bp = Blueprint(
    "external_storage_api", __name__, url_prefix="/api/v2/external-storage"
)


@external_storage_api_bp.route("/status", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_external_storage_status():
    """Get external storage status.

    Returns:
        JSON with status information:
        {
            "enabled": bool,
            "storage_mode": "local" | "s3" | "hybrid",
            "worker_running": bool,
            "last_sync": datetime | null,
            "last_cleanup": datetime | null
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    from vault.services.external_storage_config_service import (
        ExternalStorageConfigService,
    )

    enabled = ExternalStorageConfigService.is_enabled(secret_key, current_app)
    storage_mode = ExternalStorageConfigService.get_storage_mode(
        secret_key, current_app
    )

    # Check if worker is running
    worker = current_app.config.get("EXTERNAL_STORAGE_WORKER")
    worker_running = worker.is_running() if worker else False

    # Check if manual sync is running
    sync_running = current_app.config.get("EXTERNAL_STORAGE_SYNC_RUNNING", False)

    return (
        jsonify(
            {
                "enabled": enabled,
                "storage_mode": storage_mode,
                "worker_running": worker_running,
                "sync_running": sync_running,
                "last_sync": None,  # TODO: Store and retrieve last sync time
                "last_cleanup": None,  # TODO: Store and retrieve last cleanup time
            }
        ),
        200,
    )


@external_storage_api_bp.route("/sync", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def trigger_sync():
    """Trigger manual synchronization in background (hybrid or s3-only mode).

    Request body (optional):
        {
            "sync_mode": "bidirectional" | "to_s3" | "from_s3" (default: "bidirectional")
        }

    Returns immediately after starting the sync process.
    The synchronization continues in background even if the user leaves the page.

    Returns:
        JSON with sync status (started)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    # Get sync_mode from request body (default: "bidirectional")
    data = request.get_json() or {}
    sync_mode = data.get("sync_mode", "bidirectional")

    # Validate sync_mode
    if sync_mode not in ["bidirectional", "to_s3", "from_s3"]:
        return (
            jsonify(
                {
                    "error": f"Invalid sync_mode: {sync_mode}. Must be 'bidirectional', 'to_s3', or 'from_s3'"
                }
            ),
            400,
        )

    from vault.services.external_storage_config_service import (
        ExternalStorageConfigService,
    )

    # Check if external storage is enabled and configured
    if not ExternalStorageConfigService.is_enabled(secret_key, current_app):
        return (
            jsonify(
                {
                    "error": "External storage is not enabled or configured",
                }
            ),
            400,
        )

    # Verify that S3 configuration is valid (endpoint and bucket are required)
    config = ExternalStorageConfigService.get_config(secret_key, current_app)
    if not config or not config.get("endpoint_url") or not config.get("bucket_name"):
        return (
            jsonify(
                {
                    "error": "S3 configuration is incomplete (endpoint_url and bucket_name are required)",
                }
            ),
            400,
        )

    # Check if sync is already running
    sync_status = current_app.config.get("EXTERNAL_STORAGE_SYNC_RUNNING", False)
    if sync_status:
        current_app.logger.warning(
            "[SYNC] Synchronization already in progress, rejecting request"
        )
        return jsonify({"error": "Synchronization is already in progress"}), 409

    current_app.logger.info(
        f"[SYNC] Starting manual synchronization (mode: {sync_mode})..."
    )

    # Get sync service and trigger sync in background
    try:
        storage = current_app.config.get("VAULT_STORAGE")
        if not storage:
            return jsonify({"error": "Storage not configured"}), 500

        from vault.services.external_storage_service import ExternalStorageService
        from vault.services.external_storage_sync_service import (
            ExternalStorageSyncService,
        )
        import threading

        external_storage = ExternalStorageService(secret_key, current_app)
        sync_service = ExternalStorageSyncService(storage, external_storage)

        # Capture app instance and user info before starting thread
        app_instance = current_app._get_current_object()
        user_id = user.id
        user_ip = request.remote_addr or "unknown"

        # Mark sync as running
        app_instance.config["EXTERNAL_STORAGE_SYNC_RUNNING"] = True

        def sync_worker():
            """Background worker to perform synchronization."""
            # Use app context manager to ensure proper context handling
            with app_instance.app_context():
                try:
                    # Call appropriate sync method based on sync_mode
                    if sync_mode == "to_s3":
                        app_instance.logger.info(
                            "[SYNC] Starting one-way sync to S3 (overwrite) worker..."
                        )
                        results = sync_service.sync_all_files_to_s3()
                        # Map results to consistent format for audit log
                        audit_details = {
                            "sync_mode": "to_s3",
                            "synced_to_s3_count": results.get("synced_to_s3_count", 0),
                            "skipped_count": results.get("skipped_count", 0),
                            "failed_count": results.get("failed_count", 0),
                        }
                        log_message = (
                            f"[SYNC] Sync to S3 completed: {results.get('synced_to_s3_count', 0)} uploaded to S3, "
                            f"{results.get('skipped_count', 0)} skipped, "
                            f"{results.get('failed_count', 0)} failed"
                        )
                    elif sync_mode == "from_s3":
                        app_instance.logger.info(
                            "[SYNC] Starting one-way sync from S3 (overwrite) worker..."
                        )
                        results = sync_service.sync_all_files_from_s3()
                        # Map results to consistent format for audit log
                        audit_details = {
                            "sync_mode": "from_s3",
                            "synced_from_s3_count": results.get(
                                "synced_from_s3_count", 0
                            ),
                            "skipped_count": results.get("skipped_count", 0),
                            "failed_count": results.get("failed_count", 0),
                        }
                        log_message = (
                            f"[SYNC] Sync from S3 completed: {results.get('synced_from_s3_count', 0)} downloaded from S3, "
                            f"{results.get('skipped_count', 0)} skipped, "
                            f"{results.get('failed_count', 0)} failed"
                        )
                    else:
                        # bidirectional (default)
                        app_instance.logger.info(
                            "[SYNC] Starting bidirectional synchronization worker..."
                        )
                        results = sync_service.sync_all_files_bidirectional()
                        audit_details = {
                            "sync_mode": "bidirectional",
                            "synced_to_s3_count": results.get("synced_to_s3_count", 0),
                            "synced_from_s3_count": results.get(
                                "synced_from_s3_count", 0
                            ),
                            "skipped_count": results.get("skipped_count", 0),
                            "failed_count": results.get("failed_count", 0),
                        }
                        log_message = (
                            f"[SYNC] Synchronization completed: {results.get('synced_to_s3_count', 0)} uploaded to S3, "
                            f"{results.get('synced_from_s3_count', 0)} downloaded from S3, "
                            f"{results.get('skipped_count', 0)} skipped, "
                            f"{results.get('failed_count', 0)} failed"
                        )

                    # Audit log
                    audit_service = app_instance.config.get("VAULT_AUDIT")
                    if audit_service:
                        audit_service.log_action(
                            action="external_storage_sync",
                            user_ip=user_ip,
                            details=audit_details,
                            success=True,
                            user_id=user_id,
                        )

                    app_instance.logger.info(log_message)
                except Exception as e:
                    app_instance.logger.error(
                        f"[SYNC] Error in sync worker: {e}", exc_info=True
                    )
                finally:
                    # Mark sync as completed (we're still in app context)
                    try:
                        app_instance.config["EXTERNAL_STORAGE_SYNC_RUNNING"] = False
                        app_instance.logger.info(
                            "[SYNC] Marked synchronization as completed"
                        )
                    except Exception as e:
                        app_instance.logger.warning(
                            f"[SYNC] Failed to mark sync as completed: {e}"
                        )

        # Start sync in background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()

        return (
            jsonify(
                {
                    "status": "started",
                    "message": f"Synchronization ({sync_mode}) started in background",
                }
            ),
            200,
        )
    except Exception as e:
        current_app.config["EXTERNAL_STORAGE_SYNC_RUNNING"] = False
        current_app.logger.error(f"Error triggering sync: {e}")
        return jsonify({"error": f"Sync failed: {str(e)}"}), 500


@external_storage_api_bp.route("/restore/<file_id>", methods=["POST"])
@csrf.exempt  # JWT-authenticated endpoint, CSRF not needed
@jwt_required
@require_role(GlobalRole.ADMIN)
def restore_file(file_id: str):
    """Restore a file from S3 to local storage (hybrid mode only).

    Args:
        file_id: File ID to restore

    Returns:
        JSON with restore result
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    secret_key = current_app.config.get("SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    from vault.services.external_storage_config_service import (
        ExternalStorageConfigService,
    )

    storage_mode = ExternalStorageConfigService.get_storage_mode(
        secret_key, current_app
    )

    if storage_mode != "hybrid":
        return (
            jsonify(
                {
                    "error": "Restore is only available in hybrid mode",
                }
            ),
            400,
        )

    # Get sync service and restore file
    try:
        storage = current_app.config.get("VAULT_STORAGE")
        if not storage:
            return jsonify({"error": "Storage not configured"}), 500

        from vault.services.external_storage_service import ExternalStorageService
        from vault.services.external_storage_sync_service import (
            ExternalStorageSyncService,
        )

        external_storage = ExternalStorageService(secret_key, current_app)
        sync_service = ExternalStorageSyncService(storage, external_storage)

        success, error_msg = sync_service.restore_file_from_s3(file_id)

        if success:
            # Audit log
            audit_service = current_app.config.get("VAULT_AUDIT")
            if audit_service:
                audit_service.log_event(
                    event_type="external_storage_restore",
                    user_id=user.id,
                    status="success",
                    details={"file_id": file_id},
                )

            return (
                jsonify({"success": True, "message": "File restored successfully"}),
                200,
            )
        else:
            return (
                jsonify({"success": False, "error": error_msg or "Restore failed"}),
                400,
            )
    except Exception as e:
        current_app.logger.error(f"Error restoring file: {e}")
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500


@external_storage_api_bp.route("/metrics", methods=["GET"])
@jwt_required
@require_role(GlobalRole.ADMIN)
def get_external_storage_metrics():
    """Get external storage metrics.

    Returns:
        JSON with metrics:
        {
            "files_synced": int,
            "files_restored": int,
            "files_cleaned": int,
            "sync_success_rate": float,
            "cleanup_success_rate": float,
            "last_sync": datetime | null,
            "last_cleanup": datetime | null
        }
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    metrics_service = current_app.config.get("EXTERNAL_STORAGE_METRICS")
    if metrics_service:
        return jsonify(metrics_service.get_metrics()), 200
    else:
        # Return empty metrics if service not initialized
        return (
            jsonify(
                {
                    "files_synced": 0,
                    "files_restored": 0,
                    "files_cleaned": 0,
                    "sync_success_rate": 0.0,
                    "cleanup_success_rate": 0.0,
                    "last_sync": None,
                    "last_cleanup": None,
                }
            ),
            200,
        )
