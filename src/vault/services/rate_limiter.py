"""Rate limiting service for Leyzen Vault."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Mapping

from ..config import VaultSettings

# Conservative default rate limit for unknown IPs (uploads per hour)
DEFAULT_UNKNOWN_IP_RATE_LIMIT = 10


class RateLimiter:
    """Rate limiter for uploads per IP address."""

    def __init__(self, settings: VaultSettings):
        """Initialize the rate limiter."""
        self._settings = settings
        self._max_uploads = settings.max_uploads_per_hour
        self._lock = Lock()
        # Dictionary mapping IP -> list of timestamps
        self._upload_timestamps: dict[str, list[float]] = defaultdict(list)
        # Track unknown IP occurrences for logging
        self._unknown_ip_count = 0

    def check_rate_limit(self, ip: str) -> tuple[bool, str | None]:
        """Check if IP is within rate limit.

        Args:
            ip: Client IP address (may be "unknown" if cannot be determined)

        Returns:
            (is_allowed, error_message)
        """
        # Apply conservative rate limit to unknown IPs instead of unlimited access
        if not ip or ip == "unknown":
            # Log unknown IP occurrences (throttled to avoid log spam)
            with self._lock:
                self._unknown_ip_count += 1
                # Log every 10th occurrence to avoid spam
                if self._unknown_ip_count % 10 == 1:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Rate limiting: Client IP cannot be determined (unknown IP). "
                        f"Applying conservative default limit of {DEFAULT_UNKNOWN_IP_RATE_LIMIT} uploads/hour. "
                        f"Configure PROXY_TRUST_COUNT correctly if behind a proxy."
                    )

            # Apply conservative default limit for unknown IPs
            current_time = time.time()
            one_hour_ago = current_time - 3600
            unknown_ip_key = "unknown"

            with self._lock:
                timestamps = self._upload_timestamps[unknown_ip_key]
                self._upload_timestamps[unknown_ip_key] = [
                    ts for ts in timestamps if ts > one_hour_ago
                ]

                if (
                    len(self._upload_timestamps[unknown_ip_key])
                    >= DEFAULT_UNKNOWN_IP_RATE_LIMIT
                ):
                    return (
                        False,
                        f"Rate limit exceeded: maximum {DEFAULT_UNKNOWN_IP_RATE_LIMIT} uploads per hour for unknown IP",
                    )

                self._upload_timestamps[unknown_ip_key].append(current_time)
                return True, None

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
            # Apply conservative default limit for unknown IPs
            current_time = time.time()
            one_hour_ago = current_time - 3600
            unknown_ip_key = "unknown"

            with self._lock:
                timestamps = self._upload_timestamps.get(unknown_ip_key, [])
                recent_uploads = len([ts for ts in timestamps if ts > one_hour_ago])
                return max(0, DEFAULT_UNKNOWN_IP_RATE_LIMIT - recent_uploads)

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
