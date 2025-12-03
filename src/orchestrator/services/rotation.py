"""Rotation and uptime tracking services."""

from __future__ import annotations

import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Lock, Thread


from common.constants import (
    ROTATION_MAX_WORKERS,
    ROTATION_RETRY_INTERVAL,
    ROTATION_QUIET_PERIOD,
    ROTATION_WAIT_LOG_INTERVAL,
    ROTATION_LOOP_SLEEP_INTERVAL,
    ROTATION_ERROR_RETRY_SLEEP,
    ROTATION_LONG_SLEEP,
    ROTATION_METRICS_MIN_INTERVAL,
    ROTATION_DELAY_MIN,
    ROTATION_SNAPSHOT_MIN_INTERVAL,
    ROTATION_FRESHNESS_BASE,
    ROTATION_FRESHNESS_MULTIPLIER,
    ROTATION_METRICS_REPORT_INTERVAL,
)
from common.exceptions import DockerProxyError, DockerProxyNotFound

from ..config import Settings
from .docker_proxy import (
    INSPECT_CACHE_TTL,
    DockerProxyService,
    ProxyContainer,
)
from common.services.logging import FileLogger
from .rotation_telemetry import RotationTelemetry

# Type hint for SecurityMetricsService (imported lazily to avoid circular dependencies)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .security_metrics_service import SecurityMetricsService


class RotationService:
    """Coordinates container rotation and uptime tracking."""

    def __init__(
        self, settings: Settings, docker: DockerProxyService, logger: FileLogger
    ) -> None:
        self._settings = settings
        self._docker = docker
        self._logger = logger

        self.rotation_count = 0
        self.rotation_active = True
        self.rotation_resuming = False
        self.last_active_container: str | None = None
        self.last_rotation_time: datetime | None = None
        self.next_rotation_eta: int | None = None

        self.container_total_active_seconds: dict[str, int] = {
            name: 0 for name in self._settings.web_containers
        }
        self.container_active_since: dict[str, datetime | None] = {
            name: None for name in self._settings.web_containers
        }

        self._threads_started = False
        self._start_lock = Lock()
        self._rotation_lock = Lock()
        self._managed_containers: list[str] = []
        self._active_index: int | None = None
        self._next_switch_override: datetime | None = None
        self._container_cache: dict[str, ProxyContainer] = {}
        self._container_cache_lock = Lock()
        self._stats_error_last_logged: dict[str, float] = {}
        self._telemetry = RotationTelemetry(settings)
        self._sync_service: SyncService | None = None
        self._security_metrics: "SecurityMetricsService | None" = None
        self._shutdown_requested = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_sync_service(self) -> SyncService:
        """Get or create the shared SyncService instance.

        Returns:
            The shared SyncService instance
        """
        if self._sync_service is None:
            from .sync_service import SyncService

            self._sync_service = SyncService(self._settings, self._docker, self._logger)
        return self._sync_service

    def _get_security_metrics_service(self) -> "SecurityMetricsService":
        """Get or create the shared SecurityMetricsService instance.

        Returns:
            The shared SecurityMetricsService instance
        """
        if self._security_metrics is None:
            from .security_metrics_service import SecurityMetricsService

            self._security_metrics = SecurityMetricsService(
                self._settings, self._logger
            )
        return self._security_metrics

    def _get_internal_api_token(self) -> str:
        """Get INTERNAL_API_TOKEN from settings.

        The token is now derived deterministically from SECRET_KEY (like DOCKER_PROXY_TOKEN),
        so it's always available in settings without needing database access.

        Returns:
            The internal API token string, or empty string if not available
        """
        return self._settings.internal_api_token or ""

    def cleanup(self) -> None:
        """Clean up resources, including closing the SyncService and SecurityMetricsService HTTP clients."""
        # Signal threads to stop
        self._shutdown_requested = True
        # Clean up HTTP clients
        if self._sync_service is not None:
            self._sync_service.close()
            self._sync_service = None
        if self._security_metrics is not None:
            self._security_metrics.close()
            self._security_metrics = None

    def mark_active(self, name: str) -> None:
        self.container_active_since[name] = datetime.now(self._settings.timezone)

    def accumulate_and_clear_active(self, name: str) -> int:
        start_ts = self.container_active_since.get(name)
        if not start_ts:
            return 0
        elapsed = int(
            (datetime.now(self._settings.timezone) - start_ts).total_seconds()
        )
        self.container_total_active_seconds[name] = (
            self.container_total_active_seconds.get(name, 0) + elapsed
        )
        self.container_active_since[name] = None
        return elapsed

    # ------------------------------------------------------------------
    # Background workers
    # ------------------------------------------------------------------
    def start_background_workers(self) -> None:
        with self._start_lock:
            if self._threads_started:
                return
            self._logger.log("=== Orchestrator started ===")
            Thread(target=self._orchestrator_loop, daemon=True).start()
            Thread(target=self._uptime_tracker_loop, daemon=True).start()
            Thread(target=self._metrics_collector_loop, daemon=True).start()
            Thread(target=self._snapshot_loop, daemon=True).start()
            self._threads_started = True

    def _log_stats_error(
        self, name: str, message: str, *, now: float | None = None
    ) -> None:
        current = now or time.time()
        last = self._stats_error_last_logged.get(name, 0.0)
        if current - last >= 60:
            self._logger.log(message)
            self._stats_error_last_logged[name] = current

    def _should_rotate_immediately(self, container_name: str) -> bool:
        """Check if container should be rotated immediately based on security metrics.

        Args:
            container_name: Name of the container to check

        Returns:
            True if rotation should happen immediately
        """
        try:
            security_metrics = self._get_security_metrics_service()
            return security_metrics.should_rotate_immediately(container_name)
        except Exception as e:
            self._logger.log(
                f"[SECURITY METRICS ERROR] Failed to check rotation need: {e}"
            )
            return False

    def _prepare_container_for_rotation(self, container_name: str) -> bool:
        """Prepare container for rotation with validation and secure promotion.

        This method calls the prepare-rotation endpoint on the container which:
        1. Validates all files in /data/files/
        2. Sends validated files to orchestrator for secure promotion
        3. Cleans up memory
        4. Verifies all critical files are promoted

        Args:
            container_name: Name of the container to prepare

        Returns:
            True if preparation succeeded, False otherwise
        """
        import httpx

        try:
            # Call prepare-rotation endpoint
            url = f"http://{container_name}/api/internal/prepare-rotation"
            internal_token = self._get_internal_api_token()

            if not internal_token:
                self._logger.log(
                    f"[PREPARE ROTATION ERROR] INTERNAL_API_TOKEN not available. "
                    f"Vault may not have generated the token yet. Will retry on next rotation attempt."
                )
                return False

            headers = {
                "Authorization": f"Bearer {internal_token}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
                response = client.post(url, headers=headers, json={})

                if response.status_code == 200:
                    result = response.json()
                    overall_success = result.get("overall_success", False)

                    # Log statistics
                    validation_stats = result.get("validation", {})
                    promotion_stats = result.get("promotion", {})
                    cleanup_stats = result.get("cleanup", {})
                    verification_stats = result.get("verification", {})

                    self._logger.log(
                        f"[PREPARE ROTATION] Validation: {validation_stats.get('validated', 0)} validated, "
                        f"{validation_stats.get('rejected', 0)} rejected, "
                        f"{validation_stats.get('deleted', 0)} deleted, "
                        f"{validation_stats.get('files_in_queue', 0)} files in promotion queue"
                    )

                    # Log critical errors and debug info if any
                    if "critical_error" in validation_stats:
                        self._logger.log(
                            f"[PREPARE ROTATION CRITICAL ERROR] {validation_stats['critical_error']}"
                        )
                    if "debug_info" in validation_stats:
                        self._logger.log(
                            f"[PREPARE ROTATION DEBUG] {validation_stats['debug_info']}"
                        )
                    if "debug" in validation_stats:
                        self._logger.log(
                            f"[PREPARE ROTATION DEBUG] {validation_stats['debug']}"
                        )

                    # Log warning if files validated but not in queue
                    files_in_queue = validation_stats.get("files_in_queue", 0)
                    validated_count = validation_stats.get("validated", 0)
                    if validated_count > 0 and files_in_queue == 0:
                        self._logger.log(
                            f"[PREPARE ROTATION WARNING] {validated_count} files validated but 0 files in promotion queue. "
                            f"This indicates metadata lookup failed for all validated files."
                        )
                    self._logger.log(
                        f"[PREPARE ROTATION] Promotion: {promotion_stats.get('promoted', 0)} promoted, "
                        f"{promotion_stats.get('failed', 0)} failed"
                    )
                    self._logger.log(
                        f"[PREPARE ROTATION] Cleanup: {'success' if cleanup_stats.get('success') else 'failed'}"
                    )

                    # Log detailed verification stats
                    verification_success = verification_stats.get("success", False)
                    total_files = verification_stats.get("total_files", 0)
                    missing_count = verification_stats.get("missing_count", 0)
                    missing_percentage = verification_stats.get("missing_percentage", 0)
                    found_in_tmpfs = verification_stats.get("found_in_tmpfs", 0)
                    found_in_source = verification_stats.get("found_in_source", 0)

                    self._logger.log(
                        f"[PREPARE ROTATION] Verification: {'success' if verification_success else 'failed'} "
                        f"(total: {total_files}, missing: {missing_count} ({missing_percentage}%), "
                        f"tmpfs: {found_in_tmpfs}, source: {found_in_source})"
                    )

                    if not overall_success:
                        # Log why it failed
                        if not verification_success:
                            self._logger.log(
                                f"[PREPARE ROTATION ERROR] Verification failed: {missing_count} files missing "
                                f"({missing_percentage}%)"
                            )
                        if promotion_stats.get("failed", 0) > 0:
                            self._logger.log(
                                f"[PREPARE ROTATION ERROR] Promotion failed: {promotion_stats.get('failed', 0)} files"
                            )
                        if not cleanup_stats.get("success", False):
                            self._logger.log(f"[PREPARE ROTATION ERROR] Cleanup failed")

                        errors = result.get("errors", [])
                        if errors:
                            for error in errors:
                                self._logger.log(f"[PREPARE ROTATION ERROR] {error}")

                    return overall_success
                else:
                    self._logger.log(
                        f"[PREPARE ROTATION ERROR] Container returned status {response.status_code}: {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            self._logger.log(
                f"[PREPARE ROTATION ERROR] Timeout preparing {container_name}"
            )
            return False
        except Exception as e:
            self._logger.log(
                f"[PREPARE ROTATION ERROR] Failed to prepare {container_name}: {e}"
            )
            return False

    # ------------------------------------------------------------------
    def _orchestrator_loop(self) -> None:
        interval = self._settings.rotation_interval
        web_containers = list(self._settings.web_containers)

        if not web_containers:
            self._logger.log("[WARN] No web containers configured for rotation.")
            return

        managed_containers: list[str]
        retry_interval = ROTATION_RETRY_INTERVAL
        quiet_period = ROTATION_QUIET_PERIOD
        wait_log_interval = ROTATION_WAIT_LOG_INTERVAL
        next_wait_log_time = time.monotonic() + quiet_period
        while True:
            if self._shutdown_requested:
                return
            managed_containers = []
            proxy_error: DockerProxyError | None = None
            for name in web_containers:
                try:
                    cont = self._docker.get_container_safe(name, suppress_errors=False)
                except DockerProxyNotFound:
                    self._logger.log(
                        f"[ERROR] Container {name} declared but not found. It will be skipped."
                    )
                    continue
                except DockerProxyError as exc:
                    proxy_error = exc
                    break

                if cont:
                    managed_containers.append(name)

            if proxy_error is not None:
                monotonic_now = time.monotonic()
                if monotonic_now >= next_wait_log_time:
                    self._logger.log(
                        "[WAIT] Docker proxy unavailable during rotation startup: "
                        f"{proxy_error}. Retrying in {retry_interval:.0f}s."
                    )
                    next_wait_log_time = monotonic_now + wait_log_interval

                delay = retry_interval
                if monotonic_now < next_wait_log_time:
                    delay = min(delay, max(0.0, next_wait_log_time - monotonic_now))

                # Sleep in small chunks to allow quick shutdown
                sleep_remaining = delay
                while sleep_remaining > 0 and not self._shutdown_requested:
                    sleep_chunk = min(sleep_remaining, 1.0)  # Check every second
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                if self._shutdown_requested:
                    return
                continue

            break

        if len(managed_containers) > 1:
            random.shuffle(managed_containers)

        if not managed_containers:
            self._logger.log("[ERROR] No valid container found to manage.")
            return

        with self._rotation_lock:
            self._managed_containers = managed_containers[:]
            self._active_index = None
            self._next_switch_override = None

        self._logger.log("[INIT] Stopping all containers before rotation startup...")
        failed_stops = []
        for name in managed_containers:
            # Use shorter timeout for initial cleanup to avoid long waits
            # If docker-proxy is not ready, we'll continue anyway
            stopped = self._docker.stop_container(
                name, reason="initial cleanup", timeout=10
            )
            if not stopped:
                failed_stops.append(name)

        # For containers that failed to stop, verify their actual state
        # They may already be stopped or the docker-proxy may not be ready yet
        if failed_stops:
            self._logger.log(
                f"[INIT] Some containers could not be stopped cleanly: {failed_stops}. "
                "Verifying actual container states..."
            )
            for name in failed_stops:
                cont = self._docker.get_container_safe(name)
                if cont:
                    status = cont.status
                    if status not in ("running", "restarting"):
                        self._logger.log(
                            f"[INIT] {name} is already {status}, continuing..."
                        )
                    else:
                        self._logger.log(
                            f"[INIT] {name} is still {status}, but continuing with startup..."
                        )
                else:
                    self._logger.log(
                        f"[INIT] {name} not found in docker-proxy, assuming stopped..."
                    )

        active_index = None
        active_name = None
        for idx, name in enumerate(managed_containers):
            candidate = self._docker.start_container(name, reason="initial activation")
            if not candidate:
                continue
            if self._docker.wait_until_healthy(candidate):
                active_index = idx
                active_name = name
                break
            else:
                self._logger.log(
                    f"[WARNING] {name} failed to reach a healthy state during startup — stopping container."
                )
                self._docker.stop_container(name, reason="failed startup health check")

        if active_name is None:
            self._logger.log(
                "[ERROR] Unable to find a healthy container to start rotation."
            )
            return

        self._docker.ensure_single_active(active_name, managed_containers)
        self.mark_active(active_name)
        self.last_active_container = active_name
        with self._rotation_lock:
            self._active_index = active_index
            self._managed_containers = managed_containers[:]
        self.rotation_count = 0
        self.last_rotation_time = datetime.now(self._settings.timezone)
        self._logger.log(f"Initial rotation: {active_name} active")

        next_switch_time: datetime = datetime.now(self._settings.timezone) + timedelta(
            seconds=interval
        )
        self.next_rotation_eta = interval

        while True:
            if self._shutdown_requested:
                return
            try:
                now: datetime = datetime.now(self._settings.timezone)

                # Synchronise with any manual rotation that may have occurred
                # This check ensures the orchestrator uses current active_name/active_index values
                # Prevents attempting to stop containers that were already stopped by manual rotation
                # Ensures automated rotation progresses correctly
                with self._rotation_lock:
                    shared_index = self._active_index
                    shared_name = self.last_active_container

                if shared_name and shared_name != active_name:
                    active_name = shared_name

                if shared_index is not None and shared_index != active_index:
                    active_index = shared_index

                # Periodically verify only one container is active (every 5 iterations to avoid overhead)
                # This prevents both containers from being active simultaneously due to timeouts
                if active_name and self.rotation_count % 5 == 0:
                    self._docker.ensure_single_active(active_name, managed_containers)

                override = None
                with self._rotation_lock:
                    if self._next_switch_override is not None:
                        override = self._next_switch_override
                        self._next_switch_override = None

                if override is not None:
                    next_switch_time = override
                    remaining = (next_switch_time - now).total_seconds()
                    self.next_rotation_eta = max(0, int(remaining))
                    # Sleep in small chunks to allow quick shutdown
                    sleep_remaining = ROTATION_LOOP_SLEEP_INTERVAL
                    while sleep_remaining > 0 and not self._shutdown_requested:
                        sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                        time.sleep(sleep_chunk)
                        sleep_remaining -= sleep_chunk
                    if self._shutdown_requested:
                        return
                    continue

                if self.rotation_resuming:
                    next_switch_time = now + timedelta(seconds=interval)
                    self.next_rotation_eta = None
                    # Sleep in small chunks to allow quick shutdown
                    sleep_remaining = ROTATION_LOOP_SLEEP_INTERVAL
                    while sleep_remaining > 0 and not self._shutdown_requested:
                        sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                        time.sleep(sleep_chunk)
                        sleep_remaining -= sleep_chunk
                    if self._shutdown_requested:
                        return
                    continue

                if not self.rotation_active:
                    next_switch_time = now + timedelta(seconds=interval)
                    self.next_rotation_eta = None
                    # Sleep in small chunks to allow quick shutdown
                    sleep_remaining = ROTATION_LOOP_SLEEP_INTERVAL
                    while sleep_remaining > 0 and not self._shutdown_requested:
                        sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                        time.sleep(sleep_chunk)
                        sleep_remaining -= sleep_chunk
                    if self._shutdown_requested:
                        return
                    continue

                # Check security metrics for intelligent rotation
                should_rotate_immediately = False
                should_rotate_soon = False

                if active_name:
                    try:
                        security_metrics = self._get_security_metrics_service()
                        should_rotate_immediately = (
                            security_metrics.should_rotate_immediately(active_name)
                        )
                        should_rotate_soon = security_metrics.should_rotate_soon(
                            active_name
                        )

                        if should_rotate_immediately:
                            risk_score = security_metrics.get_risk_score(active_name)
                            self._logger.log(
                                f"[SECURITY] Critical risk detected for {active_name} (score: {risk_score}). Rotating immediately."
                            )
                        elif should_rotate_soon:
                            risk_score = security_metrics.get_risk_score(active_name)
                            self._logger.log(
                                f"[SECURITY] Elevated risk detected for {active_name} (score: {risk_score}). Accelerating rotation."
                            )
                    except Exception as e:
                        self._logger.log(
                            f"[SECURITY METRICS ERROR] Failed to check security metrics: {e}"
                        )

                # Adjust rotation timing based on security metrics
                if should_rotate_immediately:
                    # Force immediate rotation
                    next_switch_time = now
                elif should_rotate_soon:
                    # Accelerate rotation (reduce interval by 50%)
                    accelerated_interval = max(interval // 2, 30)  # Minimum 30 seconds
                    next_switch_time = now + timedelta(seconds=accelerated_interval)
                else:
                    # Normal rotation timing
                    remaining = (next_switch_time - now).total_seconds()
                    self.next_rotation_eta = max(0, int(remaining))
                    if now < next_switch_time:
                        # Sleep in small chunks to allow quick shutdown
                        sleep_remaining = ROTATION_LOOP_SLEEP_INTERVAL
                        while sleep_remaining > 0 and not self._shutdown_requested:
                            sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                            time.sleep(sleep_chunk)
                            sleep_remaining -= sleep_chunk
                        if self._shutdown_requested:
                            return
                        continue

                if len(managed_containers) == 1:
                    next_switch_time = now + timedelta(seconds=interval)
                    self.next_rotation_eta = interval
                    continue

                rotated = False
                with self._rotation_lock:
                    rotated, active_index, active_name = self._select_next_active(
                        managed_containers,
                        active_index if active_index is not None else 0,
                        active_name or managed_containers[0],
                        start_reason="preparing for rotation",
                        restore_reason="restoring active after failed candidate",
                    )
                    if rotated:
                        self.rotation_count += 1
                        self.last_rotation_time = datetime.now(self._settings.timezone)
                        self.next_rotation_eta = interval
                        self._next_switch_override = None

                if rotated:
                    self._logger.log(
                        f"Rotation #{self.rotation_count}: {active_name} is now active"
                    )
                else:
                    self._logger.log(
                        f"[WARNING] Rotation skipped — no healthy candidates available. {active_name} remains active."
                    )

                # Reset next switch time for next iteration
                if should_rotate_immediately or should_rotate_soon:
                    # Already set above
                    pass
                else:
                    next_switch_time = datetime.now(
                        self._settings.timezone
                    ) + timedelta(seconds=interval)
                    self.next_rotation_eta = interval
            except Exception:
                self._logger.log(
                    f"Exception in orchestrator loop:\n{traceback.format_exc()}"
                )
                # Sleep in small chunks to allow quick shutdown
                sleep_remaining = ROTATION_LONG_SLEEP
                while sleep_remaining > 0 and not self._shutdown_requested:
                    sleep_chunk = min(sleep_remaining, 1.0)  # Check every second
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                if self._shutdown_requested:
                    return

    def _select_next_active(
        self,
        managed_containers: list[str],
        active_index: int,
        active_name: str,
        *,
        start_reason: str,
        restore_reason: str,
    ) -> tuple[bool, int, str]:
        total_containers = len(managed_containers)
        if total_containers <= 1:
            return False, active_index, active_name

        candidate_indices = [
            idx for idx in range(total_containers) if idx != active_index
        ]
        random.shuffle(candidate_indices)

        for next_index in candidate_indices:
            next_name = managed_containers[next_index]

            # 1. Prepare rotation with validation and secure promotion
            try:
                if not self._prepare_container_for_rotation(active_name):
                    raise RuntimeError(f"Failed to prepare {active_name} for rotation")
            except Exception as exc:
                self._logger.log(
                    f"[ERROR] Failed to prepare {active_name} for rotation: {exc}. Aborting rotation."
                )
                # Stop rotation if preparation fails to prevent data loss
                return False, active_index, active_name

            # 2. Start the new container WITHOUT stopping the current active one
            next_cont = self._docker.start_container(next_name, reason=start_reason)
            if not next_cont:
                # If startup fails, try the next candidate (the current active container remains active)
                self._logger.log(
                    f"[WARNING] Failed to start {next_name} — trying next candidate."
                )
                continue

            # 3. Wait for the new container to be healthy
            if not self._docker.wait_until_healthy(next_cont):
                # If not healthy, stop the new one and try the next candidate
                self._logger.log(
                    f"[WARNING] {next_name} failed to reach a healthy state — stopping container."
                )
                self._docker.stop_container(
                    next_name, reason="failed rotation health check"
                )
                continue  # Try the next candidate, the current active container remains active

            # 4. The new container is healthy: stop the previous active container now
            elapsed = self.accumulate_and_clear_active(active_name)
            if elapsed > 0:
                total_seconds = self.container_total_active_seconds.get(active_name, 0)
                self._logger.log(
                    f"Accumulated {elapsed}s for {active_name} (total={total_seconds}s) before rotation"
                )

            # Use shorter timeout for rotation to speed up the handoff
            released = self._docker.stop_container(
                active_name, reason="releasing for rotation", timeout=10
            )

            if not released:
                self._logger.log(
                    f"[WARNING] Failed to stop {active_name} after {next_name} became healthy. "
                    "Verifying container states and forcing cleanup."
                )
                # Verify actual container states before making decisions
                active_cont = self._docker.get_container_safe(active_name)
                next_cont = self._docker.get_container_safe(next_name)

                active_running = active_cont and active_cont.status == "running"
                next_running = next_cont and next_cont.status == "running"

                if active_running and next_running:
                    # Both are running - force stop the old one with kill
                    self._logger.log(
                        f"[ROTATION] Both containers running - forcing stop of {active_name}"
                    )
                    try:
                        # Try to force stop the old container
                        self._docker.stop_container(
                            active_name, reason="force stop after timeout", timeout=5
                        )
                        # Verify it's actually stopped
                        active_cont = self._docker.get_container_safe(active_name)
                        if active_cont and active_cont.status == "running":
                            # Still running - stop the new one and abort
                            self._logger.log(
                                f"[ROTATION ERROR] {active_name} still running after force stop. "
                                f"Aborting rotation and stopping {next_name}."
                            )
                            self._docker.stop_container(
                                next_name,
                                reason="aborting rotation - old container still running",
                            )
                            self.mark_active(active_name)
                            time.sleep(ROTATION_ERROR_RETRY_SLEEP)
                            continue
                        else:
                            # Old container is now stopped - proceed with rotation
                            self._logger.log(
                                f"[ROTATION] {active_name} stopped successfully after force stop"
                            )
                            # Continue to mark new container as active
                    except Exception as exc:
                        self._logger.log(
                            f"[ROTATION ERROR] Failed to force stop {active_name}: {exc}. "
                            f"Aborting rotation and stopping {next_name}."
                        )
                        self._docker.stop_container(
                            next_name, reason="aborting rotation - force stop failed"
                        )
                        self.mark_active(active_name)
                        time.sleep(ROTATION_ERROR_RETRY_SLEEP)
                        continue
                elif not active_running and next_running:
                    # Old container is already stopped - proceed with rotation
                    self._logger.log(
                        f"[ROTATION] {active_name} is already stopped. Proceeding with rotation."
                    )
                    # Continue to mark new container as active
                else:
                    # Unexpected state - abort rotation
                    self._logger.log(
                        f"[ROTATION ERROR] Unexpected container states: "
                        f"{active_name}={active_cont.status if active_cont else 'None'}, "
                        f"{next_name}={next_cont.status if next_cont else 'None'}. "
                        f"Aborting rotation."
                    )
                    if next_running:
                        self._docker.stop_container(
                            next_name, reason="aborting rotation - unexpected state"
                        )
                    self.mark_active(active_name)
                    time.sleep(ROTATION_ERROR_RETRY_SLEEP)
                    continue

            # 5. Final verification before marking new container as active
            # Ensure old container is actually stopped
            active_cont = self._docker.get_container_safe(active_name)
            if active_cont and active_cont.status == "running":
                self._logger.log(
                    f"[ROTATION WARNING] {active_name} is still running before marking {next_name} as active. "
                    "Forcing stop one more time."
                )
                self._docker.stop_container(
                    active_name, reason="final cleanup before rotation", timeout=5
                )
                # Check again
                active_cont = self._docker.get_container_safe(active_name)
                if active_cont and active_cont.status == "running":
                    self._logger.log(
                        f"[ROTATION ERROR] {active_name} still running after final cleanup. "
                        f"Aborting rotation and stopping {next_name}."
                    )
                    self._docker.stop_container(
                        next_name,
                        reason="aborting rotation - old container still running after cleanup",
                    )
                    self.mark_active(active_name)
                    time.sleep(ROTATION_ERROR_RETRY_SLEEP)
                    continue

            # 6. Rotation successful: mark the new one as active
            self._logger.log(
                f"{next_name} marked ACTIVE at {datetime.now(self._settings.timezone).strftime('%H:%M:%S')}"
            )
            self.mark_active(next_name)
            self._docker.ensure_single_active(next_name, managed_containers)
            self._active_index = next_index
            self.last_active_container = next_name
            return True, next_index, next_name

        self._active_index = active_index
        self.last_active_container = active_name
        return False, active_index, active_name

    def _uptime_tracker_loop(self) -> None:
        local_cache: dict[str, ProxyContainer] = {}
        while True:
            if self._shutdown_requested:
                return
            try:
                now = datetime.now(self._settings.timezone)

                for name in self._settings.web_containers:
                    cont = local_cache.get(name)
                    if cont is None:
                        with self._container_cache_lock:
                            cont = self._container_cache.get(name)
                        if cont is None:
                            cont = self._docker.get_container_safe(name)
                            if cont:
                                local_cache[name] = cont
                                with self._container_cache_lock:
                                    self._container_cache[name] = cont
                            else:
                                continue

                    try:
                        cont.reload()
                    except DockerProxyError as exc:
                        self._logger.log(
                            f"[UPTIME ERROR] Failed to reload {name}: {exc}"
                        )
                        continue
                    except DockerProxyNotFound:
                        self._logger.log(
                            f"[UPTIME ERROR] Container {name} disappeared during tracking"
                        )
                        local_cache.pop(name, None)
                        with self._container_cache_lock:
                            self._container_cache.pop(name, None)
                        self._docker.invalidate_container_cache(name)
                        continue

                    status = cont.status
                    health = cont.attrs.get("State", {}).get("Health", {}).get("Status")

                    if status == "running" and (health is None or health == "healthy"):
                        if not self.container_active_since.get(name):
                            self.container_active_since[name] = now
                    else:
                        active_since = self.container_active_since.get(name)
                        if active_since is not None:
                            elapsed = int((now - active_since).total_seconds())
                            self.container_total_active_seconds[name] = (
                                self.container_total_active_seconds.get(name, 0)
                                + elapsed
                            )
                            self._logger.log(
                                f"[UPTIME] {name} paused (+{elapsed}s, total={self.container_total_active_seconds[name]}s)"
                            )
                            self.container_active_since[name] = None

                # Sleep in small chunks to allow quick shutdown
                sleep_remaining = ROTATION_LOOP_SLEEP_INTERVAL
                while sleep_remaining > 0 and not self._shutdown_requested:
                    sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                if self._shutdown_requested:
                    return
            except Exception as exc:
                self._logger.log(f"[UPTIME TRACKER ERROR] {exc}")
                # Sleep in small chunks to allow quick shutdown
                sleep_remaining = ROTATION_ERROR_RETRY_SLEEP
                while sleep_remaining > 0 and not self._shutdown_requested:
                    sleep_chunk = min(sleep_remaining, 1.0)  # Check every second
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                if self._shutdown_requested:
                    return

    def _metrics_collector_loop(self) -> None:
        base_interval = max(
            ROTATION_METRICS_MIN_INTERVAL,
            self._settings.sse_stream_interval_ms / 1000.0,
        )
        worst_iteration = 0.0
        last_report = time.perf_counter()
        while True:
            if self._shutdown_requested:
                return
            loop_start = time.perf_counter()
            try:
                running_containers: list[str] = []
                for name in self._settings.web_containers:
                    with self._container_cache_lock:
                        cont = self._container_cache.get(name)
                    if cont is None:
                        cont = self._docker.get_container_safe(name)
                        if cont:
                            with self._container_cache_lock:
                                self._container_cache[name] = cont
                    if cont and cont.status == "running":
                        running_containers.append(name)

                stats_map: dict[str, dict[str, object] | None] = {}
                if running_containers:
                    max_workers = min(len(running_containers), ROTATION_MAX_WORKERS)
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {
                            executor.submit(
                                self._docker.get_container_stats, name
                            ): name
                            for name in running_containers
                        }
                        for future in as_completed(futures):
                            name = futures[future]
                            try:
                                stats_map[name] = future.result()
                            except Exception as exc:
                                stats_map[name] = None
                                self._log_stats_error(
                                    name,
                                    f"[METRICS] Stats retrieval failed for {name}: {exc}",
                                    now=time.time(),
                                )

                def stats_lookup(name: str) -> dict[str, object] | None:
                    stats = stats_map.get(name)
                    if stats:
                        self._stats_error_last_logged.pop(name, None)
                        return stats
                    self._log_stats_error(
                        name,
                        f"[METRICS] Stats unavailable for container {name}",
                        now=time.time(),
                    )
                    return None

                metrics = self._telemetry.build_metrics(
                    running_containers, stats_lookup
                )
                if metrics:
                    self._telemetry.append_metrics_history(metrics)
                self._telemetry.store_latest_metrics(metrics)
            except Exception as exc:
                self._logger.log(f"[METRICS LOOP ERROR] {exc}")

            elapsed = time.perf_counter() - loop_start
            if elapsed > worst_iteration:
                worst_iteration = elapsed
            now = time.perf_counter()
            if now - last_report >= ROTATION_METRICS_REPORT_INTERVAL:
                worst_iteration = 0.0
                last_report = now
            delay = max(base_interval - elapsed, ROTATION_DELAY_MIN)
            # Sleep in small chunks to allow quick shutdown
            sleep_remaining = delay
            while sleep_remaining > 0 and not self._shutdown_requested:
                sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                time.sleep(sleep_chunk)
                sleep_remaining -= sleep_chunk
            if self._shutdown_requested:
                return

    def _get_latest_metrics(
        self, running_containers: list[str]
    ) -> dict[str, object] | None:
        cached_metrics, cached_timestamp = self._telemetry.get_cached_metrics()

        if cached_metrics is not None and cached_timestamp:
            age = time.time() - cached_timestamp
            base_interval = max(
                ROTATION_METRICS_MIN_INTERVAL,
                self._settings.sse_stream_interval_ms / 1000.0,
            )
            freshness_window = max(
                ROTATION_FRESHNESS_BASE, base_interval * ROTATION_FRESHNESS_MULTIPLIER
            )
            if age <= freshness_window:
                return cached_metrics

        def live_stats(name: str) -> dict[str, object] | None:
            try:
                stats = self._docker.get_container_stats(name)
            except Exception as exc:
                self._log_stats_error(
                    name,
                    f"[METRICS] Stats retrieval failed for {name}: {exc}",
                    now=time.time(),
                )
                return None
            if stats:
                self._stats_error_last_logged.pop(name, None)
                return stats
            self._log_stats_error(
                name,
                f"[METRICS] Stats unavailable for container {name}",
                now=time.time(),
            )
            return None

        metrics = self._telemetry.build_metrics(running_containers, live_stats)
        if metrics:
            self._telemetry.append_metrics_history(metrics)
        self._telemetry.store_latest_metrics(metrics)
        return metrics

    # ------------------------------------------------------------------
    # Control helpers used by HTTP handlers
    # ------------------------------------------------------------------
    def pause_rotation(self) -> None:
        self.rotation_active = False

    def resume_rotation(self) -> None:
        self.rotation_resuming = True
        self.rotation_active = True

        try:
            if (
                self.last_active_container
                and self.last_active_container in self._settings.web_containers
            ):
                active_name = self.last_active_container
            else:
                active_name = random.choice(self._settings.web_containers)
                self._logger.log(
                    f"[RESUME WARN] No previous active container found, selecting {active_name}"
                )

            self._logger.log(
                f"[RESUME] Cleaning state before rotation — keeping {active_name} active"
            )

            for name in self._settings.web_containers:
                cont = self._docker.get_container_safe(name)
                if not cont:
                    continue

                if name == active_name:
                    if cont.status != "running":
                        try:
                            cont.start()
                            self._logger.log(
                                f"[RESUME] Started {name} as active container"
                            )
                        except Exception as exc:
                            self._logger.log(
                                f"[RESUME ERROR] Failed to start {name}: {exc}"
                            )
                    continue
                else:
                    if cont.status == "running":
                        try:
                            cont.stop()
                            self._logger.log(
                                f"[RESUME] Stopped {name} to restore single active container"
                            )
                        except Exception as exc:
                            self._logger.log(
                                f"[RESUME ERROR] Failed to stop {name}: {exc}"
                            )
        except Exception as exc:
            self._logger.log(f"[RESUME ERROR] Failed during resume: {exc}")
        finally:
            self.rotation_resuming = False

    def force_rotate(self) -> tuple[bool, str, dict[str, object] | None]:
        # Allow manual rotation even when automatic rotation is paused
        with self._rotation_lock:
            if not self._managed_containers or len(self._managed_containers) <= 1:
                return (
                    False,
                    "Not enough containers are available to rotate.",
                    None,
                )

            if self._active_index is None or not self.last_active_container:
                return False, "No active container is currently tracked.", None

            active_index = self._active_index
            active_name = self.last_active_container

            self._logger.log(f"[CONTROL] Manual rotation requested from {active_name}")

            rotated, new_index, new_name = self._select_next_active(
                self._managed_containers,
                active_index,
                active_name,
                start_reason="manual rotation request",
                restore_reason="restoring active after failed manual rotation",
            )

            if not rotated:
                self._logger.log(
                    "[CONTROL] Manual rotation skipped — no healthy candidates available."
                )
                return False, "No healthy candidates were available for rotation.", None

            self.rotation_count += 1
            self.last_rotation_time = datetime.now(self._settings.timezone)
            self.next_rotation_eta = self._settings.rotation_interval
            self._next_switch_override = datetime.now(
                self._settings.timezone
            ) + timedelta(seconds=self._settings.rotation_interval)
            self._active_index = new_index
            self.last_active_container = new_name

            self._logger.log(
                f"[CONTROL] Manual rotation completed: {active_name} -> {new_name}"
            )

            snapshot = self.build_stream_snapshot()
            return True, f"{new_name} is now active.", snapshot

    def kill_all_containers(self) -> list[str]:
        stopped: list[str] = []
        for name in self._settings.web_containers:
            try:
                cont = self._docker.get_container_safe(name)
                if cont and cont.status == "running":
                    cont.stop()
                    stopped.append(name)
                    self._logger.log(f"[CONTROL] Killed container: {name}")
            except Exception as exc:
                self._logger.log(f"[CONTROL ERROR] Failed to kill {name}: {exc}")
        return stopped

    # ------------------------------------------------------------------
    def build_stream_snapshot(self) -> dict[str, object]:
        now = datetime.now(self._settings.timezone)
        containers: dict[str, dict[str, object]] = {}
        running_containers: list[str] = []
        for name in self._settings.web_containers:
            with self._container_cache_lock:
                cont = self._container_cache.get(name)
            if not cont:
                cont = self._docker.get_container_safe(name)
                if cont:
                    with self._container_cache_lock:
                        self._container_cache[name] = cont
            if cont:
                try:
                    cont.ensure_fresh(INSPECT_CACHE_TTL)
                except DockerProxyNotFound:
                    self._logger.log(
                        f"[STREAM WARN] Container {name} disappeared during snapshot"
                    )
                    with self._container_cache_lock:
                        self._container_cache.pop(name, None)
                    self._docker.invalidate_container_cache(name)
                    cont = None
                except DockerProxyError as exc:
                    self._logger.log(
                        f"[STREAM WARN] Failed to refresh {name} for snapshot: {exc}"
                    )
            state = cont.status if cont else "not found"
            health = (
                cont.attrs.get("State", {}).get("Health", {}).get("Status")
                if cont
                else None
            )
            total = float(self.container_total_active_seconds.get(name, 0))
            start_ts = self.container_active_since.get(name)
            if start_ts:
                total += (now - start_ts).total_seconds()
            containers[name] = {
                "state": state,
                "health": health,
                "uptime": round(total, 1),
            }
            if state == "running":
                running_containers.append(name)

        eta = self.next_rotation_eta
        metrics = self._get_latest_metrics(running_containers)
        timestamp_ms = int(now.timestamp() * 1000)
        self._telemetry.append_container_history(timestamp_ms, containers)
        metrics_history = self._telemetry.get_metrics_history()
        container_history = self._telemetry.get_container_history()
        snapshot: dict[str, object] = {
            "containers": containers,
            "rotation_count": self.rotation_count,
            "last_rotation": (
                self.last_rotation_time.strftime("%Y-%m-%d %H:%M:%S")
                if self.last_rotation_time
                else None
            ),
            "rotation_active": self.rotation_active,
            "next_rotation_eta": (
                int(eta) if isinstance(eta, (int, float)) and eta >= 0 else None
            ),
            "metrics": metrics,
        }
        snapshot["timestamp"] = timestamp_ms
        if metrics_history:
            snapshot["metrics_history"] = metrics_history
        if container_history:
            snapshot["container_history"] = container_history
        return snapshot

    def _snapshot_loop(self) -> None:
        interval = max(
            float(self._settings.sse_stream_interval_seconds),
            ROTATION_SNAPSHOT_MIN_INTERVAL,
        )
        while True:
            if self._shutdown_requested:
                return
            loop_start = time.perf_counter()
            try:
                snapshot = self.build_stream_snapshot()
                self._telemetry.update_snapshot_cache(snapshot)
            except (DockerProxyError, DockerProxyNotFound) as exc:
                self._logger.log(
                    f"[STREAM WARN] Snapshot refresh failed due to Docker error: {exc}"
                )
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.log(
                    f"[STREAM ERROR] Unexpected snapshot failure: {exc}\n"
                    f"{traceback.format_exc()}"
                )
            elapsed = time.perf_counter() - loop_start
            delay = max(interval - elapsed, 0.0)
            if delay:
                # Sleep in small chunks to allow quick shutdown
                sleep_remaining = delay
                while sleep_remaining > 0 and not self._shutdown_requested:
                    sleep_chunk = min(sleep_remaining, 0.5)  # Check every 0.5s
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                if self._shutdown_requested:
                    return

    def get_latest_snapshot(self) -> dict[str, object]:
        interval = max(
            float(self._settings.sse_stream_interval_seconds),
            ROTATION_SNAPSHOT_MIN_INTERVAL,
        )
        stale_threshold = interval * 2
        cached, updated = self._telemetry.get_snapshot_cache()
        now = time.time()
        if cached and now - updated <= stale_threshold:
            return cached

        try:
            snapshot = self.build_stream_snapshot()
            self._telemetry.update_snapshot_cache(snapshot)
            return deepcopy(snapshot)
        except (DockerProxyError, DockerProxyNotFound) as exc:
            self._logger.log(
                f"[STREAM WARN] Snapshot rebuild failed due to Docker error: {exc}"
            )
            cached, _ = self._telemetry.get_snapshot_cache()
            if cached:
                return cached
            return {}
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.log(
                f"[STREAM ERROR] Unexpected snapshot rebuild failure: {exc}\n"
                f"{traceback.format_exc()}"
            )
            cached, _ = self._telemetry.get_snapshot_cache()
            if cached:
                return cached
            return {}


__all__ = ["RotationService"]
