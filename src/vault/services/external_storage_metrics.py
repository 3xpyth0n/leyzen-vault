"""Metrics service for external storage operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ExternalStorageMetricsService:
    """Service for tracking external storage metrics."""

    def __init__(self):
        """Initialize metrics service."""
        self._files_synced = 0
        self._files_restored = 0
        self._files_cleaned = 0
        self._sync_successes = 0
        self._sync_failures = 0
        self._cleanup_successes = 0
        self._cleanup_failures = 0
        self._last_sync: datetime | None = None
        self._last_cleanup: datetime | None = None

    def record_sync(self, success: bool) -> None:
        """Record a sync operation.

        Args:
            success: Whether the sync was successful
        """
        if success:
            self._sync_successes += 1
            self._files_synced += 1
        else:
            self._sync_failures += 1
        self._last_sync = datetime.now(timezone.utc)

    def record_restore(self, success: bool) -> None:
        """Record a restore operation.

        Args:
            success: Whether the restore was successful
        """
        if success:
            self._files_restored += 1

    def record_cleanup(self, deleted_count: int, failed_count: int) -> None:
        """Record a cleanup operation.

        Args:
            deleted_count: Number of files deleted
            failed_count: Number of files that failed to delete
        """
        self._files_cleaned += deleted_count
        self._cleanup_successes += deleted_count
        self._cleanup_failures += failed_count
        self._last_cleanup = datetime.now(timezone.utc)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics.

        Returns:
            Dictionary with metrics
        """
        total_sync_attempts = self._sync_successes + self._sync_failures
        sync_success_rate = (
            self._sync_successes / total_sync_attempts
            if total_sync_attempts > 0
            else 0.0
        )

        total_cleanup_attempts = self._cleanup_successes + self._cleanup_failures
        cleanup_success_rate = (
            self._cleanup_successes / total_cleanup_attempts
            if total_cleanup_attempts > 0
            else 0.0
        )

        return {
            "files_synced": self._files_synced,
            "files_restored": self._files_restored,
            "files_cleaned": self._files_cleaned,
            "sync_success_rate": sync_success_rate,
            "cleanup_success_rate": cleanup_success_rate,
            "last_sync": (self._last_sync.isoformat() if self._last_sync else None),
            "last_cleanup": (
                self._last_cleanup.isoformat() if self._last_cleanup else None
            ),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._files_synced = 0
        self._files_restored = 0
        self._files_cleaned = 0
        self._sync_successes = 0
        self._sync_failures = 0
        self._cleanup_successes = 0
        self._cleanup_failures = 0
        self._last_sync = None
        self._last_cleanup = None


__all__ = ["ExternalStorageMetricsService"]
