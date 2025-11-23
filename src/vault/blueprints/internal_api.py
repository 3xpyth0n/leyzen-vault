"""Internal API endpoints for orchestrator operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from vault.extensions import csrf
from vault.services.rate_limiter import RateLimiter

internal_api_bp = Blueprint("internal_api", __name__, url_prefix="/api/internal")


def _validate_internal_token() -> bool:
    """Validate internal API token from request headers.

    INTERNAL_API_TOKEN is auto-generated from SECRET_KEY if not explicitly set.
    Tokens are generated deterministically, so all services using the same SECRET_KEY
    will generate the same tokens without needing to share or persist them.

    Additional security measures:
    - IP whitelist verification (if configured)
    - Strict rate limiting (max 60 requests/minute)
    - Detailed logging of all access attempts
    - User-Agent validation (optional)

    Returns:
        True if token is valid, False otherwise
    """
    from vault.blueprints.utils import get_client_ip

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        current_app.logger.warning(
            "Internal API access denied: Missing or invalid Authorization header"
        )
        return False

    token = auth_header[len("Bearer ") :].strip()

    # Get INTERNAL_API_TOKEN from config (auto-generated from SECRET_KEY if not set)
    expected_token = current_app.config.get("INTERNAL_API_TOKEN")
    if not expected_token:
        # Log error if INTERNAL_API_TOKEN is not available
        current_app.logger.error(
            "INTERNAL_API_TOKEN not configured. Internal API access denied. "
            "Token should be auto-generated from SECRET_KEY."
        )
        return False

    # 1. IP whitelist verification (if configured)
    allowed_ips = current_app.config.get("INTERNAL_API_ALLOWED_IPS", [])
    if allowed_ips:
        client_ip = get_client_ip() or "unknown"
        if client_ip not in allowed_ips:
            current_app.logger.warning(
                f"Internal API access denied from IP: {client_ip} (not in whitelist)"
            )
            return False

    # 2. Strict rate limiting (max 60 requests/minute)
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        client_ip = get_client_ip() or "unknown"
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=60,
            window_seconds=60,
            action_name="internal_api",
            user_id=None,
        )
        if not is_allowed:
            current_app.logger.warning(
                f"Internal API rate limit exceeded from IP: {client_ip}"
            )
            return False

    # 3. Token validation using constant-time comparison
    import hmac

    token_valid = hmac.compare_digest(token, expected_token)

    # 4. Detailed logging of all access attempts
    client_ip = get_client_ip() or "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    if token_valid:
        current_app.logger.info(
            f"Internal API access granted: IP={client_ip}, "
            f"Path={request.path}, Method={request.method}, User-Agent={user_agent[:50]}"
        )
    else:
        current_app.logger.warning(
            f"Internal API access denied: Invalid token from IP={client_ip}, "
            f"Path={request.path}, Method={request.method}, User-Agent={user_agent[:50]}"
        )

    return token_valid


def _validate_container_name(container_name: str) -> bool:
    """Validate container name format matches SyncService validation.

    Validates that container name:
    - Starts with "vault_web"
    - Followed by a number (1-9 followed by digits)
    - Maximum length of 64 characters
    - No special characters except underscore

    Args:
        container_name: Container name to validate

    Returns:
        True if container name is valid, False otherwise
    """
    import re

    # Maximum length to prevent DoS
    if len(container_name) > 64:
        return False

    # Strict pattern: vault_web followed by number (1-9, then digits)
    # This matches the expected format: vault_web1, vault_web2, etc.
    container_name_pattern = re.compile(r"^vault_web[1-9][0-9]*$")
    return bool(container_name_pattern.match(container_name))


@internal_api_bp.route("/sync", methods=["POST"])
@csrf.exempt  # Internal API, CSRF not needed
def sync_volumes():
    """Synchronize data from /data to /data-source.

    This endpoint is called by the orchestrator to synchronize data from the
    ephemeral tmpfs volume (/data) to the persistent source volume (/data-source)
    before container rotation.

    Request headers:
        Authorization: Bearer <INTERNAL_API_TOKEN>

    Note: INTERNAL_API_TOKEN is auto-generated from SECRET_KEY if not explicitly set.

    Returns:
        JSON with sync status
    """
    # Validate internal token
    if not _validate_internal_token():
        return jsonify({"error": "Unauthorized"}), 401

    # Validate container name if provided in request
    # Container name can come from request body, query params, or Host header
    container_name = None
    try:
        if request.is_json:
            json_data = request.get_json(silent=True)
            if json_data:
                container_name = json_data.get("container_name")
    except Exception:
        # If JSON parsing fails, continue without container name from body
        pass

    if not container_name:
        container_name = request.args.get("container_name")
    if not container_name:
        # Try to extract from Host header (format: container_name:port or container_name)
        host_header = request.headers.get("Host", "")
        if host_header:
            container_name = host_header.split(":")[0]

    if container_name and not _validate_container_name(container_name):
        current_app.logger.warning(
            f"[SYNC SECURITY] Invalid container name format: {container_name}"
        )
        return jsonify({"error": "Invalid container name format"}), 400

    # Rate limiting: max 1 sync per 30 seconds per token
    rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
    if rate_limiter:
        # Use token as identifier for rate limiting
        auth_header = request.headers.get("Authorization", "")
        token = (
            auth_header[len("Bearer ") :].strip()
            if auth_header.startswith("Bearer ")
            else "unknown"
        )
        # Use token hash as identifier to avoid storing full token
        import hashlib
        from vault.blueprints.utils import get_client_ip

        client_ip = get_client_ip() or "unknown"
        # For internal API, we use token hash as user_id equivalent
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        is_allowed, error_msg = rate_limiter.check_rate_limit_custom(
            client_ip,
            max_attempts=1,
            window_seconds=60,
            action_name="internal_sync",
            user_id=f"token:{token_hash}",
        )
        if not is_allowed:
            current_app.logger.warning(
                f"[SYNC RATE LIMIT] Rate limit exceeded for sync endpoint: {error_msg}"
            )
            return (
                jsonify({"error": "Rate limit exceeded. Please wait before retrying."}),
                429,
            )

    source_dir = Path("/data")
    target_dir = Path("/data-source")

    try:
        from common.services.file_promotion_service import FilePromotionService
        from common.services.sync_validation_service import SyncValidationService
        from vault.database.schema import File

        # Initialize validation service and load whitelist
        validation_service = SyncValidationService(
            db_session=db.session, File_model=File, logger=current_app.logger
        )
        validation_service.load_whitelist()

        # Initialize promotion service
        promotion_service = FilePromotionService(
            validation_service=validation_service, logger_instance=current_app.logger
        )

        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Sync files directory if it exists
        source_files = source_dir / "files"
        target_files = target_dir / "files"

        files_synced = 0
        files_rejected = 0
        files_deleted = 0

        if source_files.exists() and source_files.is_dir():
            # Create target directory if it doesn't exist
            target_files.mkdir(parents=True, exist_ok=True)

            # Recursively validate and sync directory from source to target
            def sync_directory_validated(
                src: Path, dst: Path, base_dir: Path
            ) -> tuple[int, int, int]:
                """Recursively validate and sync directory from src to dst.

                Returns:
                    Tuple of (files_synced, files_rejected, files_deleted)
                """
                synced = 0
                rejected = 0
                deleted = 0

                if not dst.exists():
                    dst.mkdir(parents=True, exist_ok=True)

                for item in src.iterdir():
                    src_item = src / item.name
                    dst_item = dst / item.name

                    if src_item.is_dir():
                        # Recursively sync subdirectories
                        sub_synced, sub_rejected, sub_deleted = (
                            sync_directory_validated(src_item, dst_item, base_dir)
                        )
                        synced += sub_synced
                        rejected += sub_rejected
                        deleted += sub_deleted
                    else:
                        # Validate file before synchronizing
                        is_valid, error_msg = validation_service.is_file_legitimate(
                            src_item, base_dir
                        )

                        if is_valid:
                            # File is legitimate, use promotion service to synchronize it
                            file_id = item.name
                            success, promotion_error = promotion_service.promote_file(
                                file_id=file_id,
                                source_path=src_item,
                                target_dir=target_dir,
                                base_dir=base_dir,
                            )

                            if success:
                                synced += 1
                                current_app.logger.info(
                                    f"[SYNC VALID] Synchronized legitimate file: {src_item.relative_to(base_dir)}"
                                )
                            else:
                                rejected += 1
                                current_app.logger.error(
                                    f"[SYNC ERROR] Failed to promote file {file_id}: {promotion_error}"
                                )
                        else:
                            # File is suspicious, delete it immediately
                            try:
                                file_size = src_item.stat().st_size
                                file_hash = validation_service.compute_file_hash(
                                    src_item
                                )

                                # Delete the suspicious file
                                src_item.unlink()
                                deleted += 1

                                current_app.logger.warning(
                                    f"[SYNC SECURITY] Deleted suspicious file: {src_item.relative_to(base_dir)} "
                                    f"(reason: {error_msg}, size: {file_size}, hash_prefix: {file_hash[:8]}...)"
                                )

                                # Also log as error for alerting
                                current_app.logger.error(
                                    f"[SYNC SECURITY ALERT] Suspicious file deleted during sync: "
                                    f"path={src_item.relative_to(base_dir)}, "
                                    f"reason={error_msg}, size={file_size}, hash_prefix: {file_hash[:8]}..."
                                )
                            except Exception as e:
                                current_app.logger.error(
                                    f"[SYNC ERROR] Failed to delete suspicious file {src_item}: {e}"
                                )
                                rejected += 1

                return synced, rejected, deleted

            files_synced, files_rejected, files_deleted = sync_directory_validated(
                source_files, target_files, source_files
            )

            # Run cleanup of orphaned files after sync
            cleanup_result = promotion_service.cleanup_orphaned_files(
                target_dir=target_dir,
                base_dir=source_files,
                dry_run=False,
            )
            files_deleted += cleanup_result.get("deleted_count", 0)

            current_app.logger.info(
                f"Successfully synchronized {files_synced} legitimate files from {source_files} to {target_files}, "
                f"rejected {files_rejected} files, deleted {files_deleted} suspicious/orphaned files"
            )
        else:
            # Source directory doesn't exist, which is fine (no files to sync)
            # But still run cleanup to remove orphaned files
            cleanup_result = promotion_service.cleanup_orphaned_files(
                target_dir=target_dir,
                base_dir=source_files if source_files.exists() else target_files,
                dry_run=False,
            )
            files_deleted = cleanup_result.get("deleted_count", 0)
            current_app.logger.info(
                f"No files directory to sync. Cleaned up {files_deleted} orphaned files."
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Synchronization completed",
                    "files_synced": files_synced,
                    "files_rejected": files_rejected,
                    "files_deleted": files_deleted,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Failed to synchronize volumes: {e}", exc_info=True)
        return jsonify({"error": "Synchronization failed"}), 500


@internal_api_bp.route("/storage/cleanup", methods=["POST"])
@csrf.exempt  # Internal API, CSRF not needed
def storage_cleanup():
    """Clean up orphaned files from storage.

    This endpoint is called by the orchestrator to periodically clean up
    orphaned files - files that exist on disk but have no corresponding
    database records.

    Request headers:
        Authorization: Bearer <INTERNAL_API_TOKEN>

    Request body (optional):
        {
            "dry_run": true/false  # Default: false
        }

    Note: INTERNAL_API_TOKEN is auto-generated from SECRET_KEY if not explicitly set.

    Returns:
        JSON with cleanup results
    """
    # Validate internal token
    if not _validate_internal_token():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    dry_run = data.get("dry_run", False)  # Default to actual cleanup for automated runs

    try:
        from vault.services.storage_reconciliation_service import (
            StorageReconciliationService,
        )

        storage = current_app.config.get("VAULT_STORAGE")
        if not storage:
            return jsonify({"error": "Storage not configured"}), 500

        reconciliation_service = StorageReconciliationService(storage)
        results = reconciliation_service.cleanup_orphaned_files(dry_run=dry_run)

        total_deleted = len(results["deleted_primary"]) + len(results["deleted_source"])

        if total_deleted > 0:
            current_app.logger.info(
                f"Storage cleanup: Deleted {total_deleted} orphaned files "
                f"(primary: {len(results['deleted_primary'])}, "
                f"source: {len(results['deleted_source'])})"
            )

        if results["failed"]:
            current_app.logger.warning(
                f"Storage cleanup: Failed to delete {len(results['failed'])} files"
            )

        # Convert sets to lists for JSON serialization
        stats = results.get("stats", {})
        if "primary" in stats and isinstance(stats["primary"], set):
            stats["primary"] = list(stats["primary"])
        if "source" in stats and isinstance(stats["source"], set):
            stats["source"] = list(stats["source"])

        # Add counts to response
        results["deleted_primary_count"] = len(results["deleted_primary"])
        results["deleted_source_count"] = len(results["deleted_source"])
        results["failed_count"] = len(results["failed"])
        results["total_deleted"] = total_deleted

        # Convert lists to ensure all are JSON serializable
        response_data = {
            "dry_run": results["dry_run"],
            "deleted_primary": results["deleted_primary"],
            "deleted_source": results["deleted_source"],
            "failed": results["failed"],
            "deleted_primary_count": results["deleted_primary_count"],
            "deleted_source_count": results["deleted_source_count"],
            "failed_count": results["failed_count"],
            "total_deleted": total_deleted,
            "stats": stats,
        }

        return jsonify(response_data), 200

    except Exception as e:
        current_app.logger.error(f"Storage cleanup failed: {e}", exc_info=True)
        return jsonify({"error": "Storage cleanup failed", "details": str(e)}), 500


@internal_api_bp.route("/security-metrics", methods=["GET"])
@csrf.exempt  # Internal API, CSRF not needed
def security_metrics():
    """Get security metrics for the current container.

    This endpoint exposes security metrics to the orchestrator for intelligent
    rotation decisions.

    Request headers:
        Authorization: Bearer <INTERNAL_API_TOKEN>

    Returns:
        JSON with security metrics including:
        - suspicious_requests: Number of suspicious requests (anomalies + denied access + rate limit exceeded)
        - auth_failures: Number of authentication failures (last hour)
        - auth_failures_by_ip: Dictionary mapping IP addresses to failure counts
        - auth_failures_by_user: Dictionary mapping user IDs to failure counts
        - auth_failures_by_action: Dictionary mapping action types to failure counts
        - anomalies: List of detected anomalies from BehavioralAnalysisService
        - app_errors: Number of application errors
        - memory_usage_percent: Memory usage percentage
    """
    # Validate internal token
    if not _validate_internal_token():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from datetime import datetime, timedelta, timezone
        from collections import defaultdict

        from vault.database.schema import (
            AuditLogEntry,
            BehaviorAnalytics,
            RateLimitTracking,
            User,
            db,
        )
        from vault.utils.safe_json import safe_json_loads

        metrics: dict[str, Any] = {
            "suspicious_requests": 0,
            "auth_failures": 0,
            "auth_failures_by_ip": {},
            "auth_failures_by_user": {},
            "auth_failures_by_action": {},
            "anomalies": [],
            "app_errors": 0,
            "memory_usage_percent": 0,
        }

        recent_threshold = datetime.now(timezone.utc) - timedelta(hours=1)

        # Track suspicious requests
        suspicious_count = 0

        # 1. Count anomalies from BehavioralAnalysisService for active users
        try:
            from vault.services.behavioral_analysis_service import (
                BehavioralAnalysisService,
            )

            behavioral_service = BehavioralAnalysisService()

            # Get active users (users with activity in last 24 hours)
            # Limit to first 100 users to avoid performance issues
            active_users_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
            active_users = (
                db.session.query(User.id)
                .join(
                    BehaviorAnalytics,
                    BehaviorAnalytics.user_id == User.id,
                )
                .filter(BehaviorAnalytics.timestamp >= active_users_threshold)
                .distinct()
                .limit(100)
                .all()
            )

            all_anomalies = []
            for (user_id,) in active_users:
                try:
                    user_anomalies = behavioral_service.detect_anomalies(user_id)
                    all_anomalies.extend(user_anomalies)
                    suspicious_count += len(user_anomalies)
                except Exception:
                    # Skip users with errors in anomaly detection
                    pass

            metrics["anomalies"] = all_anomalies
        except Exception as e:
            current_app.logger.debug(
                f"Error getting behavioral anomalies: {e}", exc_info=True
            )

        # 2. Count access denied from ZeroTrustService via audit logs
        try:
            # Query audit logs for access denied (success=False with suspicious actions)
            # Actions that indicate suspicious access attempts
            suspicious_actions = [
                "access_denied",
                "unauthorized_access",
                "forbidden",
                "zero_trust_denied",
            ]

            denied_access_count = (
                db.session.query(AuditLogEntry)
                .filter(
                    AuditLogEntry.action.in_(suspicious_actions),
                    AuditLogEntry.success == False,
                    AuditLogEntry.timestamp >= recent_threshold,
                )
                .count()
            )

            suspicious_count += denied_access_count
        except Exception as e:
            current_app.logger.debug(
                f"Error counting denied access: {e}", exc_info=True
            )

        # 3. Count rate limit exceeded requests
        try:
            rate_limiter = current_app.config.get("VAULT_RATE_LIMITER")
            if rate_limiter:
                # Count entries where request_count >= max_attempts (rate limit exceeded)
                # This indicates suspicious activity
                # Use the same timezone as RateLimiter for consistency
                rate_limiter_timezone = rate_limiter._timezone
                rate_limit_threshold = datetime.now(rate_limiter_timezone) - timedelta(
                    hours=1
                )
                rate_limit_exceeded = (
                    db.session.query(RateLimitTracking)
                    .filter(
                        RateLimitTracking.window_start >= rate_limit_threshold,
                        RateLimitTracking.request_count >= rate_limiter._max_uploads,
                    )
                    .count()
                )

                suspicious_count += rate_limit_exceeded
        except Exception as e:
            current_app.logger.debug(
                f"Error counting rate limit exceeded: {e}", exc_info=True
            )

        metrics["suspicious_requests"] = suspicious_count

        # Get authentication failures from audit logs
        try:
            # Query audit logs for auth failures
            auth_failures_query = db.session.query(AuditLogEntry).filter(
                AuditLogEntry.action.in_(["auth_login", "auth_signup"]),
                AuditLogEntry.success == False,
                AuditLogEntry.timestamp >= recent_threshold,
            )

            auth_failures = auth_failures_query.all()

            # Calculate total
            metrics["auth_failures"] = len(auth_failures)

            # Calculate aggregations
            failures_by_ip: dict[str, int] = defaultdict(int)
            failures_by_user: dict[str, int] = defaultdict(int)
            failures_by_action: dict[str, int] = defaultdict(int)

            for entry in auth_failures:
                # By IP
                failures_by_ip[entry.user_ip] += 1

                # By action
                failures_by_action[entry.action] += 1

                # By user (extract from details JSON)
                try:
                    if entry.details:
                        details = safe_json_loads(
                            entry.details,
                            max_size=10 * 1024,  # 10KB for audit details
                            max_depth=20,
                            context="audit log details",
                        )
                        user_id = details.get("user_id")
                        if user_id:
                            failures_by_user[user_id] += 1
                except Exception:
                    # Skip entries with invalid JSON in details
                    pass

            metrics["auth_failures_by_ip"] = dict(failures_by_ip)
            metrics["auth_failures_by_user"] = dict(failures_by_user)
            metrics["auth_failures_by_action"] = dict(failures_by_action)
        except Exception as e:
            current_app.logger.debug(f"Error getting auth failures: {e}", exc_info=True)

        # Get memory usage
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            metrics["memory_usage_percent"] = round(memory_percent, 2)
        except ImportError:
            # psutil not available, skip memory metric
            pass
        except Exception:
            pass

        return jsonify(metrics), 200

    except Exception as e:
        current_app.logger.error(f"Failed to get security metrics: {e}", exc_info=True)
        return (
            jsonify({"error": "Failed to get security metrics", "details": str(e)}),
            500,
        )


@internal_api_bp.route("/prepare-rotation", methods=["POST"])
@csrf.exempt  # Internal API, CSRF not needed
def prepare_rotation():
    """Prepare container for rotation with validation and secure promotion.

    This endpoint:
    1. Validates all files in /data/files/ using SyncValidationService
    2. Sends validated files to orchestrator for secure promotion
    3. Cleans up memory
    4. Verifies all critical files are promoted

    Request headers:
        Authorization: Bearer <INTERNAL_API_TOKEN>

    Returns:
        JSON with preparation status and statistics
    """
    # Validate internal token
    if not _validate_internal_token():
        return jsonify({"error": "Unauthorized"}), 401

    current_app.logger.info(
        "[PREPARE ROTATION] ===== Starting prepare-rotation endpoint ====="
    )

    try:
        from common.services.sync_validation_service import SyncValidationService
        from vault.database.schema import File, db

        storage = current_app.config.get("VAULT_STORAGE")
        if not storage:
            return jsonify({"error": "Storage not configured"}), 500

        stats: dict[str, Any] = {
            "validation": {
                "validated": 0,
                "rejected": 0,
                "deleted": 0,
                "files_in_queue": 0,
            },
            "promotion": {"promoted": 0, "failed": 0},
            "cleanup": {"success": False},
            "verification": {"success": False},
            "overall_success": False,
        }

        # Step 1: Validation
        current_app.logger.info("[PREPARE ROTATION] Starting validation phase")
        validation_service = SyncValidationService(
            db_session=db.session, File_model=File, logger=current_app.logger
        )
        validation_service.load_whitelist()

        # Log whitelist size for debugging
        whitelist_size = len(validation_service._legitimate_files)
        whitelist_keys_sample = list(validation_service._legitimate_files.keys())[:5]
        current_app.logger.info(
            f"[PREPARE ROTATION] Loaded {whitelist_size} files in whitelist. "
            f"Sample keys: {whitelist_keys_sample}"
        )

        storage_dir = storage.storage_dir
        base_dir = storage_dir / "files"
        source_dir = Path("/data-source")

        files_dir = storage_dir / "files"
        validated_files: list[dict[str, Any]] = []

        if files_dir.exists():
            files_in_tmpfs = [f for f in files_dir.iterdir() if f.is_file()]
            current_app.logger.info(
                f"[PREPARE ROTATION] Found {len(files_in_tmpfs)} files in tmpfs. "
                f"Whitelist has {len(validation_service._legitimate_files)} entries"
            )

            # SIMPLE LOGIC: For each file, check if it's in whitelist. If yes, promote. If no, delete.
            whitelist_keys_sample = list(validation_service._legitimate_files.keys())[
                :5
            ]
            current_app.logger.info(
                f"[PREPARE ROTATION] Sample whitelist keys: {whitelist_keys_sample}"
            )

            for file_path in files_dir.iterdir():
                if not file_path.is_file():
                    continue

                file_id = file_path.name
                current_app.logger.info(
                    f"[PREPARE ROTATION] Processing file: {file_id}, "
                    f"in whitelist: {file_id in validation_service._legitimate_files}"
                )

                # Check if file is in whitelist (this is the filename as stored in database)
                if file_id in validation_service._legitimate_files:
                    current_app.logger.info(
                        f"[PREPARE ROTATION] File {file_id} IS in whitelist, promoting..."
                    )
                    # File is legitimate - read and promote it
                    try:
                        file_metadata = validation_service._legitimate_files[file_id]
                        file_data = file_path.read_bytes()

                        # Verify we have required metadata
                        if (
                            not isinstance(file_metadata, dict)
                            or "encrypted_hash" not in file_metadata
                            or "size" not in file_metadata
                        ):
                            current_app.logger.error(
                                f"[PREPARE ROTATION] File {file_id} in whitelist but metadata invalid: {type(file_metadata)}"
                            )
                            stats["validation"]["rejected"] += 1
                            file_path.unlink()
                            stats["validation"]["deleted"] += 1
                            continue

                        # Add to promotion queue
                        validated_files.append(
                            {
                                "file_id": file_id,
                                "file_data": file_data,
                                "expected_hash": file_metadata["encrypted_hash"],
                                "expected_size": file_metadata["size"],
                            }
                        )
                        stats["validation"]["validated"] += 1
                        current_app.logger.info(
                            f"[PREPARE ROTATION] File {file_id} added to promotion queue "
                            f"(size: {len(file_data)}, hash: {file_metadata['encrypted_hash'][:16]}...)"
                        )
                    except Exception as e:
                        current_app.logger.error(
                            f"[PREPARE ROTATION] Error processing legitimate file {file_id}: {e}",
                            exc_info=True,
                        )
                        stats["validation"]["rejected"] += 1
                        try:
                            file_path.unlink()
                            stats["validation"]["deleted"] += 1
                        except:
                            pass
                else:
                    # File is NOT in whitelist - delete it
                    current_app.logger.warning(
                        f"[PREPARE ROTATION] File {file_id} not in whitelist - deleting"
                    )
                    try:
                        file_path.unlink()
                        stats["validation"]["deleted"] += 1
                    except Exception as e:
                        current_app.logger.error(
                            f"[PREPARE ROTATION] Failed to delete invalid file {file_id}: {e}"
                        )
        else:
            current_app.logger.info(
                "[PREPARE ROTATION] No files directory in tmpfs (empty cache is normal)"
            )

        # Step 2: Secure promotion to persistent storage
        # Update stats with files in queue
        stats["validation"]["files_in_queue"] = len(validated_files)
        current_app.logger.info(
            f"[PREPARE ROTATION] After processing: {len(validated_files)} files in queue, "
            f"{stats['validation']['validated']} validated, {stats['validation']['rejected']} rejected"
        )

        # Add debug info to stats so it appears in orchestrator logs
        if len(validated_files) == 0 and stats["validation"]["validated"] > 0:
            stats["validation"]["debug_info"] = (
                f"WARNING: {stats['validation']['validated']} files validated but 0 files in promotion queue. "
                f"This indicates metadata lookup failed for all validated files."
            )
        current_app.logger.info(
            f"[PREPARE ROTATION] validated_files count: {len(validated_files)}, "
            f"validated count: {stats['validation']['validated']}"
        )

        if validated_files:
            current_app.logger.info(
                f"[PREPARE ROTATION] Promoting {len(validated_files)} validated files"
            )
            # Log first few file IDs being promoted
            sample_file_ids = [f["file_id"] for f in validated_files[:3]]
            current_app.logger.info(
                f"[PREPARE ROTATION] Sample files to promote: {sample_file_ids}"
            )

            # Initialize promotion service
            from common.services.file_promotion_service import FilePromotionService

            promotion_service = FilePromotionService(
                validation_service=validation_service,
                logger_instance=current_app.logger,
            )

            # Promote files directly to persistent storage
            promoted_count = 0
            failed_count = 0
            promotion_errors = []

            for file_info in validated_files:
                file_id = file_info["file_id"]
                try:
                    # Get source path from tmpfs (files are already validated and in tmpfs)
                    source_path = storage.get_file_path(file_id)
                    target_dir = storage.source_dir

                    if not source_path.exists():
                        error_msg = f"File {file_id} not found at {source_path}"
                        current_app.logger.warning(f"[PREPARE ROTATION] {error_msg}")
                        failed_count += 1
                        promotion_errors.append(error_msg)
                        continue

                    if not target_dir:
                        error_msg = "Target directory not configured"
                        current_app.logger.warning(f"[PREPARE ROTATION] {error_msg}")
                        failed_count += 1
                        promotion_errors.append(error_msg)
                        continue

                    # Promote file using FilePromotionService
                    success, error_msg = promotion_service.promote_file(
                        file_id=file_id,
                        source_path=source_path,
                        target_dir=target_dir,
                        base_dir=base_dir,
                    )

                    if success:
                        promoted_count += 1
                        current_app.logger.info(
                            f"[PREPARE ROTATION] Successfully promoted file {file_id}"
                        )
                    else:
                        failed_count += 1
                        error_msg = error_msg or "Unknown promotion error"
                        promotion_errors.append(f"File {file_id}: {error_msg}")
                        current_app.logger.warning(
                            f"[PREPARE ROTATION] Failed to promote file {file_id}: {error_msg}"
                        )

                except Exception as e:
                    failed_count += 1
                    error_msg = f"File {file_id}: {str(e)}"
                    promotion_errors.append(error_msg)
                    current_app.logger.error(
                        f"[PREPARE ROTATION] Exception promoting file {file_id}: {e}",
                        exc_info=True,
                    )

            stats["promotion"]["promoted"] = promoted_count
            stats["promotion"]["failed"] = failed_count
            stats["promotion"]["errors"] = promotion_errors

            if failed_count > 0:
                current_app.logger.warning(
                    f"[PREPARE ROTATION] Promotion had {failed_count} failures"
                )
                for error in promotion_errors[:5]:
                    current_app.logger.warning(
                        f"[PREPARE ROTATION] Promotion error: {error}"
                    )
        else:
            current_app.logger.warning(
                f"[PREPARE ROTATION] No files to promote (validated_files is empty, "
                f"but {stats['validation']['validated']} files were validated). "
                f"This indicates metadata lookup failed for all validated files."
            )

        # Step 3: Memory cleanup
        current_app.logger.info("[PREPARE ROTATION] Starting memory cleanup")
        try:
            from vault.services.memory_cleanup_service import MemoryCleanupService

            cleanup_service = MemoryCleanupService()
            cleanup_stats = cleanup_service.cleanup()
            stats["cleanup"]["success"] = cleanup_stats.get("memory_freed", False)
            stats["cleanup"]["details"] = cleanup_stats
        except Exception as e:
            current_app.logger.error(f"[PREPARE ROTATION] Memory cleanup failed: {e}")
            stats["cleanup"]["error"] = str(e)

        # Step 4: Verification
        current_app.logger.info("[PREPARE ROTATION] Starting verification phase")
        try:
            # Verify that all files in database exist either in tmpfs or /data-source
            from vault.database.schema import File, db

            files = db.session.query(File).filter(File.deleted_at.is_(None)).all()
            total_files_in_db = len(files)
            current_app.logger.info(
                f"[PREPARE ROTATION] Checking {total_files_in_db} files from database"
            )

            missing_files = []
            found_in_tmpfs = 0
            found_in_source = 0

            for file_obj in files:
                file_id = file_obj.id
                # Use storage_ref for file lookup (files are stored by storage_ref, not by id)
                storage_ref = file_obj.storage_ref

                # Check tmpfs (uses storage_ref)
                tmpfs_path = storage.get_file_path(storage_ref)
                # Check persistent storage (uses storage_ref)
                source_path = source_dir / "files" / storage_ref

                if tmpfs_path.exists():
                    found_in_tmpfs += 1
                elif source_path.exists():
                    found_in_source += 1
                else:
                    missing_files.append(file_id)

            # Verification is successful if:
            # - All files are accounted for (in tmpfs or source), OR
            # - Missing files are a small percentage (files might be new or deleted)
            total_files = len(files)
            missing_count = len(missing_files)
            missing_percentage = (
                (missing_count / total_files * 100) if total_files > 0 else 0
            )

            stats["verification"]["found_in_tmpfs"] = found_in_tmpfs
            stats["verification"]["found_in_source"] = found_in_source
            stats["verification"]["total_files"] = total_files
            stats["verification"]["missing_count"] = missing_count
            stats["verification"]["missing_percentage"] = round(missing_percentage, 2)

            # Allow up to 10% missing files (tolerance for new/deleted files)
            # But fail if more than 10% are missing (potential data loss)
            if missing_count > 0:
                if missing_percentage <= 10.0:
                    stats["verification"]["success"] = True
                    current_app.logger.warning(
                        f"[PREPARE ROTATION] Verification: {missing_count} files missing "
                        f"({missing_percentage:.1f}%) - within tolerance "
                        f"(found in tmpfs: {found_in_tmpfs}, found in source: {found_in_source})"
                    )
                    # Log first few missing files for debugging
                    for file_id in missing_files[:3]:
                        current_app.logger.warning(
                            f"[PREPARE ROTATION] Missing file (within tolerance): {file_id}"
                        )
                else:
                    stats["verification"]["success"] = False
                    stats["verification"]["missing_files"] = missing_files
                    current_app.logger.error(
                        f"[PREPARE ROTATION] Verification failed: {missing_count} files missing "
                        f"({missing_percentage:.1f}%) - exceeds 10% tolerance "
                        f"(found in tmpfs: {found_in_tmpfs}, found in source: {found_in_source})"
                    )
                    # Log first few missing files for debugging
                    for file_id in missing_files[:5]:
                        current_app.logger.error(
                            f"[PREPARE ROTATION] Missing file: {file_id}"
                        )
            else:
                stats["verification"]["success"] = True
                current_app.logger.info(
                    f"[PREPARE ROTATION] Verification successful: all files accounted for "
                    f"(tmpfs: {found_in_tmpfs}, source: {found_in_source})"
                )

        except Exception as e:
            current_app.logger.error(
                f"[PREPARE ROTATION] Verification failed with exception: {e}",
                exc_info=True,
            )
            stats["verification"]["error"] = str(e)
            # On exception, mark as failed but log the error
            stats["verification"]["success"] = False
            # Try to still get basic stats even on error
            try:
                from vault.database.schema import File, db

                files = db.session.query(File).filter(File.deleted_at.is_(None)).all()
                stats["verification"]["total_files"] = len(files)
            except Exception:
                pass

        # Overall success if:
        # - No promotion failures (if files were promoted)
        # - Verification succeeded (all files accounted for)
        # - Cleanup succeeded
        # Note: It's OK if no files were validated (tmpfs might be empty if all files already promoted)
        stats["overall_success"] = (
            stats["promotion"]["failed"] == 0
            and stats["verification"]["success"]
            and stats["cleanup"]["success"]
        )

        if stats["overall_success"]:
            current_app.logger.info(
                "[PREPARE ROTATION] Preparation completed successfully"
            )
            return jsonify(stats), 200
        else:
            current_app.logger.warning(
                "[PREPARE ROTATION] Preparation completed with issues"
            )
            return jsonify(stats), 200  # Return 200 but with success=False

    except Exception as e:
        current_app.logger.error(
            f"[PREPARE ROTATION] Preparation failed: {e}", exc_info=True
        )
        return jsonify({"error": "Preparation failed", "details": str(e)}), 500


__all__ = ["internal_api_bp"]
