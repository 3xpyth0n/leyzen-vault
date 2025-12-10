"""Background worker for external storage synchronization and cleanup."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from vault.services.external_storage_config_service import (
    ExternalStorageConfigService,
)
from vault.services.external_storage_sync_service import ExternalStorageSyncService
from vault.services.external_storage_validation_service import (
    ExternalStorageValidationService,
)
from vault.services.external_storage_service import ExternalStorageService

logger = logging.getLogger(__name__)


class ExternalStorageWorker:
    """Background worker for external storage operations."""

    def __init__(
        self,
        secret_key: str,
        app: Any,
        local_storage: Any | None = None,
    ):
        """Initialize external storage worker.

        Args:
            secret_key: SECRET_KEY for decrypting configuration
            app: Flask app instance
            local_storage: Local FileStorage instance (for hybrid mode)
        """
        self.secret_key = secret_key
        self.app = app
        self.local_storage = local_storage
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    def _get_storage_mode(self) -> str:
        """Get current storage mode.

        Returns:
            Storage mode string: "local", "s3", or "hybrid"
        """
        # Use app context for database access
        with self.app.app_context():
            return ExternalStorageConfigService.get_storage_mode(
                self.secret_key, self.app
            )

    def _is_enabled(self) -> bool:
        """Check if external storage is enabled.

        Returns:
            True if enabled, False otherwise
        """
        # Use app context for database access
        with self.app.app_context():
            return ExternalStorageConfigService.is_enabled(self.secret_key, self.app)

    def _run_hybrid_sync(self) -> None:
        """Run synchronization in hybrid mode."""
        # Use app context manager to ensure proper context handling
        with self.app.app_context():
            try:
                from vault.storage import FileStorage

                if not self.local_storage:
                    logger.warning(
                        "[WORKER] Local storage not available, skipping hybrid sync"
                    )
                    return

                external_storage = ExternalStorageService(self.secret_key, self.app)
                sync_service = ExternalStorageSyncService(
                    self.local_storage, external_storage
                )

                # Sync pending files
                logger.info("[WORKER] Starting hybrid sync...")
                results = sync_service.sync_all_pending_files()
                logger.info(
                    f"[WORKER] Hybrid sync completed: {results['synced_count']} synced, "
                    f"{results['failed_count']} failed"
                )

                # Sync deletions
                deletion_results = sync_service.sync_deletions()
                if deletion_results["deleted_count"] > 0:
                    logger.info(
                        f"[WORKER] Synced {deletion_results['deleted_count']} deletions"
                    )

            except Exception as e:
                logger.error(f"[WORKER ERROR] Hybrid sync failed: {e}", exc_info=True)

    def _run_s3_cleanup(self) -> None:
        """Run cleanup/validation in S3-only mode."""
        # Use app context manager to ensure proper context handling
        with self.app.app_context():
            try:
                from vault.database.schema import File, db

                external_storage = ExternalStorageService(self.secret_key, self.app)
                validation_service = ExternalStorageValidationService(
                    external_storage, db.session, File
                )

                # Run cleanup
                logger.info("[WORKER] Starting S3 cleanup...")
                results = validation_service.cleanup_orphaned_files(dry_run=False)
                logger.info(
                    f"[WORKER] S3 cleanup completed: {results['deleted_count']} deleted, "
                    f"{results['failed_count']} failed"
                )

            except Exception as e:
                logger.error(f"[WORKER ERROR] S3 cleanup failed: {e}", exc_info=True)

    def _worker_loop(self) -> None:
        """Main worker loop."""
        logger.info("[WORKER] External storage worker started")

        while not self._stop_event.is_set():
            try:
                if not self._is_enabled():
                    # Wait and check again
                    self._stop_event.wait(60)  # Check every minute
                    continue

                storage_mode = self._get_storage_mode()

                if storage_mode == "hybrid":
                    # Run hybrid sync
                    self._run_hybrid_sync()
                    # Wait 1 hour before next sync
                    self._stop_event.wait(3600)
                elif storage_mode == "s3":
                    # Run S3 cleanup
                    self._run_s3_cleanup()
                    # Wait 1 hour before next cleanup
                    self._stop_event.wait(3600)
                else:
                    # Local mode - no work to do
                    self._stop_event.wait(60)  # Check every minute

            except Exception as e:
                logger.error(f"[WORKER ERROR] Worker loop error: {e}", exc_info=True)
                # Wait before retrying
                self._stop_event.wait(60)

        logger.info("[WORKER] External storage worker stopped")

    def start(self) -> None:
        """Start the worker thread."""
        if self._running:
            logger.debug("[WORKER] Worker is already running")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("[WORKER] External storage worker thread started")

    def stop(self) -> None:
        """Stop the worker thread."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("[WORKER] Worker thread did not stop gracefully")

        logger.info("[WORKER] External storage worker stopped")

    def is_running(self) -> bool:
        """Check if worker is running.

        Returns:
            True if running, False otherwise
        """
        return self._running


__all__ = ["ExternalStorageWorker"]
