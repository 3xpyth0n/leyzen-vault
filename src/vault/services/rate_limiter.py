"""Rate limiting service for Leyzen Vault."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Mapping

from ..config import VaultSettings


class RateLimiter:
    """Rate limiter for uploads per IP address."""

    def __init__(self, settings: VaultSettings):
        """Initialize the rate limiter."""
        self._settings = settings
        self._max_uploads = settings.max_uploads_per_hour
        self._lock = Lock()
        # Dictionary mapping IP -> list of timestamps
        self._upload_timestamps: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, ip: str) -> tuple[bool, str | None]:
        """Check if IP is within rate limit.

        Returns:
            (is_allowed, error_message)
        """
        if not ip or ip == "unknown":
            return True, None  # Allow unknown IPs (shouldn't happen in production)

        current_time = time.time()
        one_hour_ago = current_time - 3600

        with self._lock:
            # Clean old timestamps
            timestamps = self._upload_timestamps[ip]
            self._upload_timestamps[ip] = [ts for ts in timestamps if ts > one_hour_ago]

            # Check limit
            if len(self._upload_timestamps[ip]) >= self._max_uploads:
                return (
                    False,
                    f"Rate limit exceeded: maximum {self._max_uploads} uploads per hour",
                )

            # Record this upload
            self._upload_timestamps[ip].append(current_time)
            return True, None

    def get_remaining_uploads(self, ip: str) -> int:
        """Get remaining uploads for an IP in the current hour."""
        if not ip or ip == "unknown":
            return self._max_uploads

        current_time = time.time()
        one_hour_ago = current_time - 3600

        with self._lock:
            timestamps = self._upload_timestamps[ip]
            recent_uploads = len([ts for ts in timestamps if ts > one_hour_ago])
            return max(0, self._max_uploads - recent_uploads)

    def reset_ip(self, ip: str) -> None:
        """Reset rate limit for a specific IP (for testing/admin)."""
        with self._lock:
            if ip in self._upload_timestamps:
                del self._upload_timestamps[ip]


__all__ = ["RateLimiter"]
