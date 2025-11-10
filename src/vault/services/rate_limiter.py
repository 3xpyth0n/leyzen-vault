"""Rate limiting service for Leyzen Vault."""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock

from ..config import VaultSettings
from ..database.schema import RateLimitTracking, db

# Conservative default rate limit for unknown IPs (uploads per hour)
DEFAULT_UNKNOWN_IP_RATE_LIMIT = 10


class RateLimiter:
    """Rate limiter for uploads per IP address using PostgreSQL."""

    def __init__(self, settings: VaultSettings):
        """Initialize the rate limiter."""
        self._settings = settings
        self._max_uploads = settings.max_uploads_per_hour
        self._lock = Lock()
        self._timezone = settings.timezone
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
            ip = "unknown"
            max_uploads = DEFAULT_UNKNOWN_IP_RATE_LIMIT
        else:
            max_uploads = self._max_uploads

        try:
            now = datetime.now(self._timezone)
            window_start = now - timedelta(hours=1)

            # Clean up old entries (older than 2 hours for safety margin)
            # OPTIMIZATION: Only run cleanup every 100 requests to reduce database load
            # Use a simple counter to track requests
            if not hasattr(self, "_cleanup_counter"):
                self._cleanup_counter = 0
            self._cleanup_counter += 1

            if self._cleanup_counter >= 100:
                cleanup_threshold = now - timedelta(hours=2)
                db.session.query(RateLimitTracking).filter(
                    RateLimitTracking.window_start < cleanup_threshold
                ).delete(synchronize_session=False)
                self._cleanup_counter = 0

            # Find or create entry for this IP in the current window
            # Use window_start rounded to the hour for consistent windows
            window_start_rounded = window_start.replace(
                minute=0, second=0, microsecond=0
            )

            entry = (
                db.session.query(RateLimitTracking)
                .filter_by(ip_address=ip, window_start=window_start_rounded)
                .first()
            )

            if entry:
                # Update existing entry
                if entry.request_count >= max_uploads:
                    db.session.commit()
                    return (
                        False,
                        f"Rate limit exceeded: maximum {max_uploads} uploads per hour",
                    )
                entry.request_count += 1
                entry.last_request_time = now
            else:
                # Create new entry for this window
                entry = RateLimitTracking(
                    ip_address=ip,
                    window_start=window_start_rounded,
                    last_request_time=now,
                    request_count=1,
                )
                db.session.add(entry)

            db.session.commit()
            return True, None

        except Exception as e:
            # Check if we're in production mode
            # Fail-closed in production (deny request), fail-open in development (allow request)
            import logging
            import traceback

            logger = logging.getLogger(__name__)

            # Try to get production mode from Flask app config
            is_production = True  # Default to fail-closed for safety
            try:
                from flask import current_app

                if current_app:
                    is_production = current_app.config.get("IS_PRODUCTION", True)
            except RuntimeError:
                # Not in Flask application context, default to fail-closed
                pass
            except Exception:
                # Any other error accessing Flask config, default to fail-closed
                pass

            if is_production:
                # Fail-closed in production: deny request if rate limiting fails
                logger.error(
                    f"Rate limiting error (fail-closed in production): {e}\n{traceback.format_exc()}"
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                return (
                    False,
                    "Rate limiting service unavailable. Please try again later.",
                )
            else:
                # Fail-open in development: allow request if rate limiting fails
                logger.warning(
                    f"Rate limiting error (fail-open in development): {e}\n{traceback.format_exc()}"
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                # Fail-open: allow request to proceed
                return True, None

    def check_rate_limit_custom(
        self,
        ip: str,
        max_attempts: int,
        window_seconds: int,
        action_name: str = "action",
    ) -> tuple[bool, str | None]:
        """Check if IP is within custom rate limit with progressive jailing.

        Implements progressive rate limiting:
        - First violation: standard window
        - Multiple violations: extended window (exponential backoff)
        - Maximum window: 1 hour

        Args:
            ip: Client IP address
            max_attempts: Maximum number of attempts allowed
            window_seconds: Time window in seconds
            action_name: Name of the action for error messages

        Returns:
            (is_allowed, error_message)
        """
        if not ip or ip == "unknown":
            ip = "unknown"

        try:
            now = datetime.now(self._timezone)
            base_window_start = now - timedelta(seconds=window_seconds)

            # Clean up old entries (older than 2x window for safety margin)
            # OPTIMIZATION: Only run cleanup every 100 requests to reduce database load
            if not hasattr(self, "_cleanup_counter_custom"):
                self._cleanup_counter_custom = 0
            self._cleanup_counter_custom += 1

            if self._cleanup_counter_custom >= 100:
                cleanup_threshold = now - timedelta(seconds=window_seconds * 2)
                db.session.query(RateLimitTracking).filter(
                    RateLimitTracking.window_start < cleanup_threshold
                ).delete(synchronize_session=False)
                self._cleanup_counter_custom = 0

            # Use a unique identifier for this action type
            # Combine IP and action name to track different actions separately
            ip_key = f"{ip}:{action_name}"

            # Calculate base window start
            window_start = now - timedelta(seconds=window_seconds)
            window_start_rounded = window_start.replace(microsecond=0)

            # Check for recent violations to implement progressive jailing
            # Look for entries in the last hour where rate limit was exceeded
            violation_window_start = now - timedelta(hours=1)
            recent_violations = (
                db.session.query(RateLimitTracking)
                .filter(
                    RateLimitTracking.ip_address == ip_key,
                    RateLimitTracking.window_start >= violation_window_start,
                    RateLimitTracking.request_count >= max_attempts,
                )
                .count()
            )

            # Calculate progressive jailing: extend window based on violation count
            effective_window_seconds = window_seconds

            # Progressive jailing: double the window for each violation (up to 1 hour max)
            if recent_violations > 0:
                # Exponential backoff: 2^violation_count, capped at 1 hour
                extended_window = window_seconds * (2 ** min(recent_violations, 6))
                effective_window_seconds = min(extended_window, 3600)  # Max 1 hour
                window_start = now - timedelta(seconds=effective_window_seconds)
                window_start_rounded = window_start.replace(microsecond=0)

            entry = (
                db.session.query(RateLimitTracking)
                .filter_by(ip_address=ip_key, window_start=window_start_rounded)
                .first()
            )

            if entry:
                # Update existing entry
                if entry.request_count >= max_attempts:
                    db.session.commit()
                    if recent_violations > 0:
                        wait_minutes = effective_window_seconds // 60
                        return (
                            False,
                            f"Too many attempts. Rate limit extended due to previous violations. Please try again in {wait_minutes} minute{'s' if wait_minutes != 1 else ''}.",
                        )
                    return (
                        False,
                        "Too many attempts. Please try again later.",
                    )
                entry.request_count += 1
                entry.last_request_time = now
            else:
                # Create new entry for this window
                entry = RateLimitTracking(
                    ip_address=ip_key,
                    window_start=window_start_rounded,
                    last_request_time=now,
                    request_count=1,
                )
                db.session.add(entry)

            db.session.commit()
            return True, None

        except Exception as e:
            # Check if we're in production mode
            # Fail-closed in production (deny request), fail-open in development (allow request)
            import logging
            import traceback

            logger = logging.getLogger(__name__)

            # Try to get production mode from Flask app config
            is_production = True  # Default to fail-closed for safety
            try:
                from flask import current_app

                if current_app:
                    is_production = current_app.config.get("IS_PRODUCTION", True)
            except RuntimeError:
                # Not in Flask application context, default to fail-closed
                pass
            except Exception:
                # Any other error accessing Flask config, default to fail-closed
                pass

            if is_production:
                # Fail-closed in production: deny request if rate limiting fails
                logger.error(
                    f"Rate limiting error in check_rate_limit_custom (fail-closed in production): {e}\n{traceback.format_exc()}"
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                return (
                    False,
                    "Rate limiting service unavailable. Please try again later.",
                )
            else:
                # Fail-open in development: allow request if rate limiting fails
                logger.warning(
                    f"Rate limiting error in check_rate_limit_custom (fail-open in development): {e}\n{traceback.format_exc()}"
                )
                try:
                    db.session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                # Fail-open: allow request to proceed
                return True, None

    def get_remaining_uploads(self, ip: str) -> int:
        """Get remaining uploads for an IP in the current hour."""
        if not ip or ip == "unknown":
            ip = "unknown"
            max_uploads = DEFAULT_UNKNOWN_IP_RATE_LIMIT
        else:
            max_uploads = self._max_uploads

        try:
            now = datetime.now(self._timezone)
            window_start_rounded = (now - timedelta(hours=1)).replace(
                minute=0, second=0, microsecond=0
            )

            entry = (
                db.session.query(RateLimitTracking)
                .filter_by(ip_address=ip, window_start=window_start_rounded)
                .first()
            )

            if entry:
                return max(0, max_uploads - entry.request_count)
            return max_uploads

        except Exception as e:
            # Fail closed: return 0 remaining uploads if rate limiting fails
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Rate limiting error in get_remaining_uploads: {e}")
            db.session.rollback()
            # Fail closed: return 0 to be conservative
            return 0

    def reset_ip(self, ip: str) -> None:
        """Reset rate limit for a specific IP (for testing/admin)."""
        try:
            db.session.query(RateLimitTracking).filter_by(ip_address=ip).delete()
            db.session.commit()
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error resetting rate limit for IP {ip}: {e}")
            db.session.rollback()


__all__ = ["RateLimiter"]
