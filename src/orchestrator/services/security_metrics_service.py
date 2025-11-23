"""Security metrics service for intelligent rotation decisions."""

from __future__ import annotations

import httpx
import time
from typing import Any

from ..config import Settings, reload_internal_api_token_from_db
from common.services.logging import FileLogger


class SecurityMetricsService:
    """Service for collecting security metrics and calculating risk scores.

    This service collects security-related metrics from vault containers and
    calculates a risk score (0-100) to determine if immediate rotation is needed.
    """

    # Hardcoded thresholds (no environment variables)
    RISK_THRESHOLD_CRITICAL = 70  # Immediate rotation
    RISK_THRESHOLD_MEDIUM = 50  # Accelerated rotation

    def __init__(self, settings: Settings, logger: FileLogger) -> None:
        """Initialize the security metrics service.

        Args:
            settings: Orchestrator settings
            logger: Logger instance
        """
        self._settings = settings
        self._logger = logger
        self._client = httpx.Client(timeout=httpx.Timeout(10.0))
        self._metrics_cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamp: dict[str, float] = {}
        self._cache_ttl = 30.0  # Cache metrics for 30 seconds
        self._token_unavailable_last_logged: float = 0.0
        self._token_unavailable_log_interval = (
            300.0  # Log once every 5 minutes when token unavailable
        )
        self._token_reload_interval = (
            60.0  # Try to reload token from DB every 60 seconds if unavailable
        )
        self._token_last_reload_attempt: float = 0.0
        self._cached_token: str | None = None

    def get_security_metrics(self, container_name: str) -> dict[str, Any] | None:
        """Get security metrics from a vault container.

        Args:
            container_name: Name of the container

        Returns:
            Dictionary with security metrics or None if unavailable
        """
        # Check cache first
        cached = self._metrics_cache.get(container_name)
        cache_time = self._cache_timestamp.get(container_name, 0)
        if cached and (time.time() - cache_time) < self._cache_ttl:
            return cached

        try:
            # Call internal API endpoint
            url = f"http://{container_name}/api/internal/security-metrics"

            # Get token, with dynamic reload from database if not available
            internal_token = self._get_internal_api_token()

            if not internal_token:
                # Only log this error periodically to avoid log spam
                current_time = time.time()
                if (
                    current_time - self._token_unavailable_last_logged
                    >= self._token_unavailable_log_interval
                ):
                    self._logger.log(
                        f"[SECURITY METRICS] INTERNAL_API_TOKEN not available for {container_name}. "
                        "Security metrics collection is disabled until token is available. "
                        "Set INTERNAL_API_TOKEN environment variable or ensure vault has generated the token in database."
                    )
                    self._token_unavailable_last_logged = current_time
                return None

            headers = {
                "Authorization": f"Bearer {internal_token}",
                "Content-Type": "application/json",
            }

            response = self._client.get(url, headers=headers, timeout=10.0)

            if response.status_code == 200:
                metrics = response.json()
                # Cache the result
                self._metrics_cache[container_name] = metrics
                self._cache_timestamp[container_name] = time.time()
                return metrics
            else:
                self._logger.log(
                    f"[SECURITY METRICS] Failed to get metrics from {container_name}: HTTP {response.status_code}"
                )
                return None

        except httpx.TimeoutException:
            self._logger.log(
                f"[SECURITY METRICS] Timeout getting metrics from {container_name}"
            )
            return None
        except Exception as e:
            self._logger.log(
                f"[SECURITY METRICS] Error getting metrics from {container_name}: {e}"
            )
            return None

    def calculate_risk_score(self, metrics: dict[str, Any]) -> int:
        """Calculate risk score (0-100) from security metrics.

        Args:
            metrics: Dictionary with security metrics

        Returns:
            Risk score from 0 (low risk) to 100 (critical risk)
        """
        if not metrics:
            return 0

        score = 0

        # Factor 1: Suspicious requests (rate limiting, CSP violations)
        suspicious_requests = metrics.get("suspicious_requests", 0)
        if suspicious_requests > 100:
            score += 30
        elif suspicious_requests > 50:
            score += 20
        elif suspicious_requests > 10:
            score += 10

        # Factor 2: Authentication failures
        auth_failures = metrics.get("auth_failures", 0)
        if auth_failures > 50:
            score += 25
        elif auth_failures > 20:
            score += 15
        elif auth_failures > 5:
            score += 5

        # Factor 3: Detected anomalies
        anomalies = metrics.get("anomalies", [])
        high_severity_anomalies = sum(
            1 for a in anomalies if a.get("severity") == "high"
        )
        medium_severity_anomalies = sum(
            1 for a in anomalies if a.get("severity") == "medium"
        )

        if high_severity_anomalies > 0:
            score += 30
        elif medium_severity_anomalies > 2:
            score += 15
        elif medium_severity_anomalies > 0:
            score += 5

        # Factor 4: Application errors
        app_errors = metrics.get("app_errors", 0)
        if app_errors > 100:
            score += 15
        elif app_errors > 50:
            score += 10
        elif app_errors > 10:
            score += 5

        # Factor 5: Abnormal memory usage
        memory_usage_percent = metrics.get("memory_usage_percent", 0)
        if memory_usage_percent > 95:
            score += 10
        elif memory_usage_percent > 85:
            score += 5

        # Cap at 100
        return min(100, score)

    def should_rotate_immediately(self, container_name: str) -> bool:
        """Check if container should be rotated immediately based on risk score.

        Args:
            container_name: Name of the container

        Returns:
            True if rotation should happen immediately
        """
        metrics = self.get_security_metrics(container_name)
        if not metrics:
            return False

        risk_score = self.calculate_risk_score(metrics)
        return risk_score >= self.RISK_THRESHOLD_CRITICAL

    def should_rotate_soon(self, container_name: str) -> bool:
        """Check if container should be rotated soon (accelerated rotation).

        Args:
            container_name: Name of the container

        Returns:
            True if rotation should be accelerated
        """
        metrics = self.get_security_metrics(container_name)
        if not metrics:
            return False

        risk_score = self.calculate_risk_score(metrics)
        return risk_score >= self.RISK_THRESHOLD_MEDIUM

    def get_risk_score(self, container_name: str) -> int:
        """Get current risk score for a container.

        Args:
            container_name: Name of the container

        Returns:
            Risk score from 0 to 100
        """
        metrics = self.get_security_metrics(container_name)
        return self.calculate_risk_score(metrics) if metrics else 0

    def _get_internal_api_token(self) -> str:
        """Get internal API token, with dynamic reload from database if not available.

        Priority:
        1. Cached token (if available)
        2. Token from settings (from environment variable or initial DB read)
        3. Periodic reload from database if token is not available

        Returns:
            The internal API token string, or empty string if not available
        """
        # If we have a cached token, use it
        if self._cached_token:
            return self._cached_token

        # Try settings token (from environment variable or initial DB read)
        internal_token = self._settings.internal_api_token
        if internal_token:
            self._cached_token = internal_token
            return internal_token

        # Token not available - try to reload from database periodically
        current_time = time.time()
        if (
            current_time - self._token_last_reload_attempt
            >= self._token_reload_interval
        ):
            self._token_last_reload_attempt = current_time

            # Try to reload from database
            try:
                reloaded_token = reload_internal_api_token_from_db(self._settings)

                if reloaded_token:
                    self._cached_token = reloaded_token
                    self._logger.log(
                        "[SECURITY METRICS] Successfully loaded INTERNAL_API_TOKEN from database"
                    )
                    return reloaded_token
            except Exception:
                # Silently fail - we'll try again later
                pass

        return ""

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if hasattr(self, "_client") and self._client is not None:
            self._client.close()


__all__ = ["SecurityMetricsService"]
