"""Storage cleanup service for orchestrator.

This service runs in the orchestrator (which is not restarted by MTD)
and periodically calls the vault's internal API to clean up orphaned files.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.services.logging import FileLogger
    from ..config import Settings


class StorageCleanupService:
    """Service for periodically cleaning up orphaned files via vault internal API."""

    def __init__(self, settings: Settings, logger: FileLogger):
        """Initialize storage cleanup service.

        Args:
            settings: Orchestrator settings
            logger: Logger instance
        """
        self.settings = settings
        self.logger = logger
        self._worker_thread: threading.Thread | None = None
        self._worker_started = False
        self._stop_event = threading.Event()

    def start_background_worker(self) -> None:
        """Start the background worker thread for storage cleanup.

        This method is idempotent - calling it multiple times will only start
        one worker thread.
        """
        if self._worker_started:
            return

        self._worker_started = True
        self._worker_thread = threading.Thread(
            target=self._storage_cleanup_worker,
            daemon=True,
            name="StorageCleanupWorker",
        )
        self._worker_thread.start()
        self.logger.log("[STORAGE_CLEANUP] Background worker started")

    def stop_background_worker(self) -> None:
        """Stop the background worker thread."""
        if not self._worker_started:
            return

        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        self._worker_started = False
        self.logger.log("[STORAGE_CLEANUP] Background worker stopped")

    def _call_vault_cleanup_api(self, dry_run: bool = False) -> dict | None:
        """Call the vault's internal API to trigger storage cleanup.

        Args:
            dry_run: Whether to perform a dry run (no actual deletion)

        Returns:
            Response data from API, or None if call failed
        """
        import requests

        try:
            # Get internal API token from settings (read from database)
            internal_api_token = self.settings.internal_api_token
            if not internal_api_token:
                # Token not available - skip cleanup
                self.logger.warning(
                    "INTERNAL_API_TOKEN not available. Skipping storage cleanup."
                )
                return

            # Get vault container URL (use first available container)
            # In production, there should always be at least one container running
            vault_url = f"http://vault_web1:5000"  # Default to web1

            # Call internal API endpoint
            response = requests.post(
                f"{vault_url}/api/internal/storage/cleanup",
                json={"dry_run": dry_run},
                headers={"Authorization": f"Bearer {internal_api_token}"},
                timeout=60,  # 60 second timeout for cleanup operation
            )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.log(
                    f"[STORAGE_CLEANUP] API call failed with status {response.status_code}: {response.text}"
                )
                return None

        except requests.exceptions.Timeout:
            self.logger.log(
                "[STORAGE_CLEANUP] API call timed out (cleanup may still be running)"
            )
            return None
        except requests.exceptions.ConnectionError as e:
            self.logger.log(f"[STORAGE_CLEANUP] Failed to connect to vault: {e}")
            return None
        except Exception as e:
            self.logger.log(
                f"[STORAGE_CLEANUP] Unexpected error calling vault API: {e}"
            )
            return None

    def _storage_cleanup_worker(self) -> None:
        """Background worker that periodically triggers storage cleanup.

        This worker runs in a separate thread and calls the vault's internal API
        to clean up orphaned files every 30 minutes.
        """
        # Wait 30 minutes before first run to allow system to stabilize
        # and avoid cleanup during initial setup
        self.logger.log(
            "[STORAGE_CLEANUP] Worker started, waiting 30 minutes before first cleanup"
        )

        # Sleep in small chunks to allow quick shutdown
        for _ in range(180):  # 180 * 10s = 1800s = 30 minutes
            if self._stop_event.wait(timeout=10):
                return

        while not self._stop_event.is_set():
            try:
                self.logger.log("[STORAGE_CLEANUP] Starting orphaned file cleanup")

                # Call vault API to perform cleanup
                result = self._call_vault_cleanup_api(dry_run=False)

                if result:
                    total_deleted = result.get("total_deleted", 0)
                    failed_count = result.get("failed_count", 0)

                    if total_deleted > 0:
                        self.logger.log(
                            f"[STORAGE_CLEANUP] Cleaned up {total_deleted} orphaned files "
                            f"(primary: {result.get('deleted_primary_count', 0)}, "
                            f"source: {result.get('deleted_source_count', 0)})"
                        )
                    else:
                        self.logger.log("[STORAGE_CLEANUP] No orphaned files found")

                    if failed_count > 0:
                        self.logger.log(
                            f"[STORAGE_CLEANUP] Failed to delete {failed_count} files"
                        )
                else:
                    self.logger.log(
                        "[STORAGE_CLEANUP] Cleanup failed (see previous errors)"
                    )

            except Exception as e:
                self.logger.log(f"[STORAGE_CLEANUP] Worker error: {e}")

            # Sleep for 30 minutes before next cleanup
            # Sleep in small chunks (10 seconds) to allow quick shutdown
            for _ in range(180):  # 180 * 10s = 1800s = 30 minutes
                if self._stop_event.wait(timeout=10):
                    return
