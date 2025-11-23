"""Cache promotion service for promoting files from tmpfs cache to persistent storage."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from flask import current_app

from vault.services.sync_validation_service import SyncValidationService


class CachePromotionService:
    """Service for promoting files from tmpfs cache to persistent storage.

    This service validates files before promotion and sends them to the orchestrator
    for secure promotion to /data-source. Files are promoted asynchronously after
    a delay to optimize I/O operations.
    """

    def __init__(self) -> None:
        """Initialize the cache promotion service."""
        self._validation_service = SyncValidationService()
        self._promotion_queue: list[dict[str, Any]] = []
        self._queue_lock = Lock()
        self._promotion_delay_seconds = 300  # 5 minutes hardcoded delay
        self._batch_size = 10  # Process files in batches
        self._running = False
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the background promotion thread."""
        if self._running:
            return

        self._running = True
        self._thread = Thread(target=self._promotion_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background promotion thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def queue_file_for_promotion(
        self, file_id: str, file_path: Path, base_dir: Path
    ) -> bool:
        """Queue a file for promotion after validation.

        Args:
            file_id: File identifier
            file_path: Path to the file in cache
            base_dir: Base directory for validation

        Returns:
            True if file was queued, False if validation failed
        """
        # Validate file before queuing
        is_valid, error_msg = self._validation_service.is_file_legitimate(
            file_path, base_dir
        )

        if not is_valid:
            current_app.logger.warning(
                f"[CACHE PROMOTION] File {file_id} failed validation: {error_msg}. Not queued for promotion."
            )
            return False

        # Get file metadata from validation service
        file_metadata = self._validation_service._legitimate_files.get(file_id)
        if not file_metadata:
            current_app.logger.warning(
                f"[CACHE PROMOTION] File {file_id} not found in legitimate files list"
            )
            return False

        # Read file data
        try:
            file_data = file_path.read_bytes()
        except Exception as e:
            current_app.logger.error(
                f"[CACHE PROMOTION] Failed to read file {file_id}: {e}"
            )
            return False

        # Add to queue with timestamp
        with self._queue_lock:
            self._promotion_queue.append(
                {
                    "file_id": file_id,
                    "file_data": file_data,
                    "expected_hash": file_metadata["encrypted_hash"],
                    "expected_size": file_metadata["size"],
                    "queued_at": time.time(),
                    "file_path": file_path,
                }
            )

        current_app.logger.info(
            f"[CACHE PROMOTION] File {file_id} queued for promotion"
        )
        return True

    def _promotion_loop(self) -> None:
        """Background loop for processing promotion queue."""
        while self._running:
            try:
                time.sleep(10)  # Check queue every 10 seconds

                with self._queue_lock:
                    if not self._promotion_queue:
                        continue

                    # Filter files that are ready for promotion (after delay)
                    now = time.time()
                    ready_files = [
                        f
                        for f in self._promotion_queue
                        if now - f["queued_at"] >= self._promotion_delay_seconds
                    ]

                    if not ready_files:
                        continue

                    # Process in batches
                    batch = ready_files[: self._batch_size]

                    # Remove from queue
                    for file_info in batch:
                        self._promotion_queue.remove(file_info)

                # Send batch to orchestrator for promotion
                self._send_batch_to_orchestrator(batch)

            except Exception as e:
                current_app.logger.error(
                    f"[CACHE PROMOTION ERROR] Error in promotion loop: {e}"
                )
                time.sleep(30)  # Wait longer on error

    def _send_batch_to_orchestrator(self, batch: list[dict[str, Any]]) -> None:
        """Send a batch of validated files to orchestrator for promotion.

        Args:
            batch: List of file information dictionaries
        """
        import base64
        import httpx
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Get orchestrator URL from environment or use default
            import os

            orchestrator_url = os.environ.get(
                "ORCHESTRATOR_URL", "http://orchestrator:80"
            )
            promote_url = f"{orchestrator_url}/api/promote-files"

            # Get internal API token from environment
            internal_token = os.environ.get("INTERNAL_API_TOKEN")
            if not internal_token:
                logger.error("[CACHE PROMOTION ERROR] INTERNAL_API_TOKEN not available")
                return

            # Prepare batch data - use base64 encoding for binary data
            batch_data = []
            for file_info in batch:
                batch_data.append(
                    {
                        "file_id": file_info["file_id"],
                        "file_data": base64.b64encode(file_info["file_data"]).decode(
                            "utf-8"
                        ),
                        "expected_hash": file_info["expected_hash"],
                        "expected_size": file_info["expected_size"],
                    }
                )

            # Send to orchestrator
            headers = {
                "Authorization": f"Bearer {internal_token}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
                response = client.post(
                    promote_url, headers=headers, json={"files": batch_data}
                )

                if response.status_code == 200:
                    result = response.json()
                    promoted = result.get("promoted", 0)
                    failed = result.get("failed", 0)
                    logger.info(
                        f"[CACHE PROMOTION] Batch promotion result: {promoted} promoted, {failed} failed"
                    )

                    # Log errors if any
                    errors = result.get("errors", [])
                    for error in errors:
                        logger.warning(f"[CACHE PROMOTION] Promotion error: {error}")
                else:
                    logger.error(
                        f"[CACHE PROMOTION ERROR] Orchestrator returned status {response.status_code}: {response.text}"
                    )

        except Exception as e:
            logger.error(
                f"[CACHE PROMOTION ERROR] Failed to send batch to orchestrator: {e}"
            )

    def promote_all_validated_files(
        self, storage_dir: Path, base_dir: Path
    ) -> dict[str, Any]:
        """Promote all validated files from cache immediately.

        This is used during rotation preparation to ensure all files are promoted.

        Args:
            storage_dir: Storage directory (tmpfs)
            base_dir: Base directory for validation

        Returns:
            Dictionary with promotion statistics
        """
        # Load whitelist
        self._validation_service.load_whitelist()

        files_dir = storage_dir / "files"
        if not files_dir.exists():
            return {"promoted": 0, "rejected": 0, "errors": []}

        promoted = 0
        rejected = 0
        errors: list[str] = []

        # Process all files in cache
        for file_path in files_dir.iterdir():
            if not file_path.is_file():
                continue

            file_id = file_path.name

            # Validate file
            is_valid, error_msg = self._validation_service.is_file_legitimate(
                file_path, base_dir
            )

            if not is_valid:
                rejected += 1
                errors.append(f"File {file_id}: {error_msg}")
                # Delete invalid file for security
                try:
                    file_path.unlink()
                    current_app.logger.warning(
                        f"[CACHE PROMOTION] Deleted invalid file {file_id}: {error_msg}"
                    )
                except Exception as e:
                    current_app.logger.error(
                        f"[CACHE PROMOTION ERROR] Failed to delete invalid file {file_id}: {e}"
                    )
                continue

            # Queue for immediate promotion
            if self.queue_file_for_promotion(file_id, file_path, base_dir):
                promoted += 1
            else:
                rejected += 1

        return {
            "promoted": promoted,
            "rejected": rejected,
            "errors": errors,
        }


__all__ = ["CachePromotionService"]
