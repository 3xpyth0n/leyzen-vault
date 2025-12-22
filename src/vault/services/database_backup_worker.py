"""Background worker for database backup scheduling and retention."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any

from croniter import croniter

from vault.services.database_backup_config_service import (
    DatabaseBackupConfigService,
)
from vault.services.database_backup_service import DatabaseBackupService

logger = logging.getLogger(__name__)


class DatabaseBackupWorker:
    """Background worker for database backup operations."""

    def __init__(
        self,
        secret_key: str,
        app: Any,
    ):
        """Initialize database backup worker.

        Args:
            secret_key: SECRET_KEY for decrypting configuration
            app: Flask app instance
        """
        self.secret_key = secret_key
        self.app = app
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_backup_time: datetime | None = None
        self._cron_iter: croniter | None = None

    def _is_enabled(self) -> bool:
        """Check if database backup is enabled.

        Returns:
            True if enabled, False otherwise
        """
        with self.app.app_context():
            return DatabaseBackupConfigService.is_enabled(self.secret_key, self.app)

    def _get_config(self) -> dict[str, Any] | None:
        """Get backup configuration.

        Returns:
            Configuration dictionary or None
        """
        with self.app.app_context():
            return DatabaseBackupConfigService.get_config(self.secret_key, self.app)

    def _run_scheduled_backup(self) -> None:
        """Run a scheduled backup if it's time."""
        try:
            with self.app.app_context():
                config = self._get_config()
                if not config or not config.get("enabled"):
                    return

                cron_expression = config.get("cron_expression")
                if not cron_expression:
                    return

                # Check if it's time for a backup
                now = datetime.now(timezone.utc)
                if self._last_backup_time is None:
                    # First run, check if we should backup now
                    self._cron_iter = croniter(cron_expression, now)
                    next_time = self._cron_iter.get_next(datetime)
                    # If next time is very close (within 1 minute), do backup now
                    if (next_time - now).total_seconds() < 60:
                        self._do_backup()
                        self._last_backup_time = now
                else:
                    # Check if enough time has passed
                    if self._cron_iter is None:
                        self._cron_iter = croniter(
                            cron_expression, self._last_backup_time
                        )

                    next_time = self._cron_iter.get_next(datetime)
                    if now >= next_time:
                        self._do_backup()
                        self._last_backup_time = now
                        # Reset cron iter for next time
                        self._cron_iter = croniter(cron_expression, now)

        except Exception as e:
            logger.error(
                f"[BACKUP WORKER] Error in scheduled backup check: {e}", exc_info=True
            )

    def _do_backup(self) -> None:
        """Execute a backup."""
        try:
            logger.info("[BACKUP WORKER] Starting scheduled backup")
            config = self._get_config()
            storage_type = config.get("storage_type", "local") if config else "local"
            backup_service = DatabaseBackupService(self.secret_key, self.app)
            backup_record = backup_service.create_backup(
                backup_type="scheduled", storage_type=storage_type
            )
            logger.info(
                f"[BACKUP WORKER] Scheduled backup completed: {backup_record.id}"
            )

            # Run retention cleanup after backup
            self._cleanup_old_backups()
        except Exception as e:
            logger.error(f"[BACKUP WORKER] Scheduled backup failed: {e}", exc_info=True)

    def _cleanup_old_backups(self) -> None:
        """Clean up old backups according to retention policy."""
        try:
            with self.app.app_context():
                config = self._get_config()
                if not config:
                    return

                retention_policy = config.get("retention_policy")
                if not retention_policy:
                    return

                from vault.database.schema import DatabaseBackup
                from vault.database import db

                # Get all completed backups
                backups = (
                    db.session.query(DatabaseBackup)
                    .filter_by(status="completed")
                    .order_by(DatabaseBackup.created_at.desc())
                    .all()
                )

                if retention_policy.get("type") == "count":
                    # Keep only N most recent backups
                    max_count = retention_policy.get("value", 10)
                    if len(backups) > max_count:
                        backups_to_delete = backups[max_count:]
                        for backup in backups_to_delete:
                            try:
                                backup_service = DatabaseBackupService(
                                    self.secret_key, self.app
                                )
                                backup_service.delete_backup(backup.id)
                                logger.info(
                                    f"[BACKUP WORKER] Deleted old backup: {backup.id}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"[BACKUP WORKER] Failed to delete backup {backup.id}: {e}"
                                )

                elif retention_policy.get("type") == "days":
                    # Delete backups older than N days
                    days = retention_policy.get("value", 30)
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                    for backup in backups:
                        if backup.created_at < cutoff_date:
                            try:
                                backup_service = DatabaseBackupService(
                                    self.secret_key, self.app
                                )
                                backup_service.delete_backup(backup.id)
                                logger.info(
                                    f"[BACKUP WORKER] Deleted old backup: {backup.id}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"[BACKUP WORKER] Failed to delete backup {backup.id}: {e}"
                                )

        except Exception as e:
            logger.error(f"[BACKUP WORKER] Error in cleanup: {e}", exc_info=True)

    def _worker_loop(self) -> None:
        """Main worker loop."""
        logger.info("[BACKUP WORKER] Database backup worker started")

        while not self._stop_event.is_set():
            try:
                if not self._is_enabled():
                    # Wait and check again
                    self._stop_event.wait(60)  # Check every minute
                    continue

                # Check if it's time for a scheduled backup
                self._run_scheduled_backup()

                # Wait 1 minute before next check
                self._stop_event.wait(60)

            except Exception as e:
                logger.error(f"[BACKUP WORKER] Worker loop error: {e}", exc_info=True)
                # Wait before retrying
                self._stop_event.wait(60)

        logger.info("[BACKUP WORKER] Database backup worker stopped")

    def start(self) -> None:
        """Start the worker thread."""
        if self._running:
            logger.debug("[BACKUP WORKER] Worker is already running")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("[BACKUP WORKER] Database backup worker thread started")

    def stop(self) -> None:
        """Stop the worker thread."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[BACKUP WORKER] Database backup worker thread stopped")

    def is_running(self) -> bool:
        """Check if worker is running.

        Returns:
            True if running, False otherwise
        """
        return self._running


__all__ = ["DatabaseBackupWorker"]
