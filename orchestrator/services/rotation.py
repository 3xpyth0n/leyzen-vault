"""Rotation and uptime tracking services."""

from __future__ import annotations

import math
import random
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Lock, Thread
from typing import Dict, List, Optional

from ..config import Settings
from .docker_proxy import (
    INSPECT_CACHE_TTL,
    DockerProxyError,
    DockerProxyNotFound,
    DockerProxyService,
    ProxyContainer,
)
from .logging import FileLogger


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
        self.last_active_container: Optional[str] = None
        self.last_rotation_time: Optional[datetime] = None
        self.next_rotation_eta: Optional[int] = None

        self.container_total_active_seconds: Dict[str, int] = {
            name: 0 for name in self._settings.web_containers
        }
        self.container_active_since: Dict[str, Optional[datetime]] = {
            name: None for name in self._settings.web_containers
        }

        self._threads_started = False
        self._start_lock = Lock()
        self._rotation_lock = Lock()
        self._managed_containers: list[str] = []
        self._active_index: Optional[int] = None
        self._next_switch_override: Optional[datetime] = None
        self._container_cache: Dict[str, ProxyContainer] = {}
        self._container_cache_lock = Lock()
        self._previous_net_snapshot: Optional[Dict[str, float]] = None
        self._stats_error_last_logged: Dict[str, float] = {}
        self._latest_metrics: Optional[Dict[str, object]] = None
        self._metrics_updated_at: float = 0.0
        self._metrics_lock = Lock()
        metrics_interval = max(0.2, self._settings.sse_stream_interval_ms / 1000.0)
        self._metrics_history_window_seconds = 60.0
        self._metrics_history = deque(
            maxlen=self._calculate_history_maxlen(
                self._metrics_history_window_seconds,
                metrics_interval,
                cap=1800,
            )
        )
        self._metrics_history_lock = Lock()
        self._latest_snapshot: Optional[Dict[str, object]] = None
        self._snapshot_updated_at: float = 0.0
        self._snapshot_lock = Lock()
        snapshot_interval = float(self._settings.sse_stream_interval_seconds)
        self._container_history_window_seconds = 60.0
        self._container_history = deque(
            maxlen=self._calculate_history_maxlen(
                self._container_history_window_seconds,
                snapshot_interval,
                cap=1200,
            )
        )
        self._container_history_lock = Lock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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

    def _update_snapshot_cache(self, snapshot: Dict[str, object]) -> None:
        with self._snapshot_lock:
            self._latest_snapshot = snapshot
            self._snapshot_updated_at = time.time()

    def _get_snapshot_cache(self) -> tuple[Optional[Dict[str, object]], float]:
        with self._snapshot_lock:
            cached = deepcopy(self._latest_snapshot) if self._latest_snapshot else None
            updated = self._snapshot_updated_at
        return cached, updated

    def _log_stats_error(
        self, name: str, message: str, *, now: Optional[float] = None
    ) -> None:
        current = now or time.time()
        last = self._stats_error_last_logged.get(name, 0.0)
        if current - last >= 60:
            self._logger.log(message)
            self._stats_error_last_logged[name] = current

    def _compute_cpu_percent(self, stats: Dict[str, object]) -> Optional[float]:
        cpu_stats = stats.get("cpu_stats")
        precpu_stats = stats.get("precpu_stats")
        if not isinstance(cpu_stats, dict) or not isinstance(precpu_stats, dict):
            return None

        cpu_usage = cpu_stats.get("cpu_usage")
        pre_cpu_usage = precpu_stats.get("cpu_usage")
        system_cpu = cpu_stats.get("system_cpu_usage")
        pre_system_cpu = precpu_stats.get("system_cpu_usage")

        if (
            not isinstance(cpu_usage, dict)
            or not isinstance(pre_cpu_usage, dict)
            or not isinstance(system_cpu, (int, float))
            or not isinstance(pre_system_cpu, (int, float))
        ):
            return None

        total_usage = cpu_usage.get("total_usage")
        pre_total_usage = pre_cpu_usage.get("total_usage")
        if not isinstance(total_usage, (int, float)) or not isinstance(
            pre_total_usage, (int, float)
        ):
            return None

        cpu_delta = total_usage - pre_total_usage
        system_delta = system_cpu - pre_system_cpu

        if cpu_delta <= 0 or system_delta <= 0:
            return None

        online_cpus = cpu_stats.get("online_cpus")
        if not isinstance(online_cpus, (int, float)) or online_cpus <= 0:
            per_cpu_usage = cpu_usage.get("percpu_usage")
            if isinstance(per_cpu_usage, list) and per_cpu_usage:
                online_cpus = len(per_cpu_usage)
            else:
                online_cpus = 1

        percent = (cpu_delta / system_delta) * float(online_cpus) * 100.0
        return max(0.0, percent)

    def _collect_metrics(
        self,
        running_containers: list[str],
        stats_map: Optional[Dict[str, Optional[Dict[str, object]]]] = None,
    ) -> Optional[Dict[str, object]]:
        if not running_containers:
            now = time.time()
            self._previous_net_snapshot = {
                "timestamp": now,
                "rx": 0.0,
                "tx": 0.0,
            }
            return {
                "timestamp": int(now * 1000),
                "cpu": {"usage": 0.0},
                "memory": {"used": 0, "total": 0},
                "net_io": {"rx_rate": 0.0, "tx_rate": 0.0},
            }

        now = time.time()
        cpu_samples: list[float] = []
        total_memory_used = 0.0
        total_memory_limit = 0.0
        total_rx = 0.0
        total_tx = 0.0

        for name in running_containers:
            stats: Optional[Dict[str, object]] = None
            if stats_map is not None:
                stats = stats_map.get(name)
            if stats is None:
                stats = self._docker.get_container_stats(name)
            if not stats:
                self._log_stats_error(
                    name, f"[METRICS] Stats unavailable for container {name}", now=now
                )
                continue

            self._stats_error_last_logged.pop(name, None)

            cpu_percent = self._compute_cpu_percent(stats)
            if cpu_percent is not None:
                cpu_samples.append(cpu_percent)

            mem_stats = stats.get("memory_stats")
            if isinstance(mem_stats, dict):
                usage = mem_stats.get("usage")
                limit = mem_stats.get("limit")
                cache = (
                    mem_stats.get("stats", {}).get("cache")
                    if isinstance(mem_stats.get("stats"), dict)
                    else 0
                )
                if isinstance(usage, (int, float)):
                    used_value = float(usage)
                    if isinstance(cache, (int, float)) and cache > 0:
                        used_value = max(0.0, used_value - float(cache))
                    total_memory_used += used_value
                if isinstance(limit, (int, float)) and limit > 0:
                    total_memory_limit += float(limit)

            networks = stats.get("networks")
            if isinstance(networks, dict):
                for data in networks.values():
                    if not isinstance(data, dict):
                        continue
                    rx = data.get("rx_bytes")
                    tx = data.get("tx_bytes")
                    if isinstance(rx, (int, float)):
                        total_rx += float(rx)
                    if isinstance(tx, (int, float)):
                        total_tx += float(tx)

        metrics: Dict[str, object] = {"timestamp": int(now * 1000)}

        cpu_payload: Optional[Dict[str, float]] = None
        if cpu_samples:
            avg_cpu = sum(cpu_samples) / len(cpu_samples)
            cpu_payload = {"usage": round(avg_cpu, 2)}

        memory_payload: Optional[Dict[str, int]] = None
        if total_memory_limit > 0:
            memory_payload = {
                "used": int(total_memory_used),
                "total": int(total_memory_limit),
            }

        prev_snapshot = self._previous_net_snapshot
        rx_rate = tx_rate = None
        if prev_snapshot and isinstance(prev_snapshot, dict):
            prev_time = prev_snapshot.get("timestamp")
            prev_rx = prev_snapshot.get("rx")
            prev_tx = prev_snapshot.get("tx")
            if (
                isinstance(prev_time, (int, float))
                and now > prev_time
                and isinstance(prev_rx, (int, float))
                and isinstance(prev_tx, (int, float))
            ):
                elapsed = now - prev_time
                rx_rate = (total_rx - prev_rx) / elapsed
                tx_rate = (total_tx - prev_tx) / elapsed

        self._previous_net_snapshot = {
            "timestamp": now,
            "rx": total_rx,
            "tx": total_tx,
        }

        net_payload: Optional[Dict[str, float]] = None
        if isinstance(rx_rate, (int, float)) or isinstance(tx_rate, (int, float)):
            net_payload = {}
            if isinstance(rx_rate, (int, float)):
                net_payload["rx_rate"] = max(0.0, float(rx_rate))
            if isinstance(tx_rate, (int, float)):
                net_payload["tx_rate"] = max(0.0, float(tx_rate))

        if cpu_payload is not None:
            metrics["cpu"] = cpu_payload
        if memory_payload is not None:
            metrics["memory"] = memory_payload
        if net_payload:
            metrics["net_io"] = net_payload

        return metrics if len(metrics) > 1 else None

    # ------------------------------------------------------------------
    def _calculate_history_maxlen(
        self, window_seconds: float, interval_seconds: float, *, cap: int
    ) -> int:
        interval = max(0.05, float(interval_seconds))
        estimate = int(math.ceil(window_seconds / interval))
        return max(1, min(estimate + 2, cap))

    def _append_metrics_history(self, metrics: Optional[Dict[str, object]]) -> None:
        if not metrics:
            return

        timestamp = metrics.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            timestamp = int(time.time() * 1000)
        sample: Dict[str, object] = {"timestamp": int(timestamp)}

        for key in ("cpu", "memory", "net_io"):
            value = metrics.get(key)
            if isinstance(value, dict) and value:
                sample[key] = deepcopy(value)

        with self._metrics_history_lock:
            self._metrics_history.append(sample)

    def _get_metrics_history(self) -> list[Dict[str, object]]:
        with self._metrics_history_lock:
            return [deepcopy(entry) for entry in self._metrics_history]

    def _append_container_history(
        self, timestamp_ms: int, containers: Dict[str, Dict[str, object]]
    ) -> None:
        sanitized: Dict[str, Dict[str, Optional[str]]] = {}
        for name, info in containers.items():
            state = info.get("state")
            health = info.get("health")
            state_value = (
                state
                if isinstance(state, str)
                else (str(state) if state is not None else None)
            )
            health_value = (
                health
                if isinstance(health, str)
                else (str(health) if health is not None else None)
            )
            sanitized[name] = {"state": state_value, "health": health_value}

        if not sanitized:
            return

        sample = {"timestamp": int(timestamp_ms), "containers": sanitized}
        with self._container_history_lock:
            self._container_history.append(sample)

    def _get_container_history(self) -> list[Dict[str, object]]:
        with self._container_history_lock:
            return [deepcopy(entry) for entry in self._container_history]

    # ------------------------------------------------------------------
    def _orchestrator_loop(self) -> None:
        interval = self._settings.rotation_interval
        web_containers = list(self._settings.web_containers)

        if not web_containers:
            self._logger.log("[WARN] No web containers configured for rotation.")
            return

        managed_containers: list[str] = []
        for name in web_containers:
            if self._docker.get_container_safe(name):
                managed_containers.append(name)
            else:
                self._logger.log(
                    f"[ERROR] Container {name} declared but not found. It will be skipped."
                )

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
        for name in managed_containers:
            self._docker.stop_container(name, reason="initial cleanup")

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

        next_switch_time = datetime.now(self._settings.timezone) + timedelta(
            seconds=interval
        )
        self.next_rotation_eta = interval

        while True:
            try:
                now = datetime.now(self._settings.timezone)

                # Synchronise with any manual rotation that may have happened
                # since the previous loop iteration. Without this check the
                # orchestrator would continue operating with stale
                # ``active_name`` / ``active_index`` values which leads to it
                # trying to stop the previously active container (already
                # stopped by the manual rotation). That in turn prevents the
                # automated rotation from progressing as expected.
                with self._rotation_lock:
                    shared_index = self._active_index
                    shared_name = self.last_active_container

                if shared_name and shared_name != active_name:
                    active_name = shared_name

                if shared_index is not None and shared_index != active_index:
                    active_index = shared_index

                override = None
                with self._rotation_lock:
                    if self._next_switch_override is not None:
                        override = self._next_switch_override
                        self._next_switch_override = None

                if override is not None:
                    next_switch_time = override
                    remaining = (next_switch_time - now).total_seconds()
                    self.next_rotation_eta = max(0, int(remaining))
                    time.sleep(1)
                    continue

                if self.rotation_resuming:
                    next_switch_time = now + timedelta(seconds=interval)
                    self.next_rotation_eta = None
                    time.sleep(1)
                    continue

                if not self.rotation_active:
                    next_switch_time = now + timedelta(seconds=interval)
                    self.next_rotation_eta = None
                    time.sleep(1)
                    continue

                remaining = (next_switch_time - now).total_seconds()
                self.next_rotation_eta = max(0, int(remaining))
                if now < next_switch_time:
                    time.sleep(1)
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

                next_switch_time = datetime.now(self._settings.timezone) + timedelta(
                    seconds=interval
                )
                self.next_rotation_eta = interval
            except Exception:
                self._logger.log(
                    f"Exception in orchestrator loop:\n{traceback.format_exc()}"
                )
                time.sleep(5)

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

            released = self._docker.stop_container(
                active_name, reason="releasing shared database for rotation"
            )
            elapsed = self.accumulate_and_clear_active(active_name)
            if elapsed > 0:
                total_seconds = self.container_total_active_seconds.get(active_name, 0)
                self._logger.log(
                    f"Accumulated {elapsed}s for {active_name} (total={total_seconds}s) before rotation"
                )

            if not released:
                self._logger.log(
                    f"[WARNING] Failed to stop {active_name} prior to rotation; will retry later."
                )
                self.mark_active(active_name)
                time.sleep(2)
                continue

            next_cont = self._docker.start_container(next_name, reason=start_reason)
            if not next_cont:
                restore = self._docker.start_container(
                    active_name, reason=restore_reason
                )
                if restore and self._docker.wait_until_healthy(restore):
                    self.mark_active(active_name)
                    self._docker.ensure_single_active(active_name, managed_containers)
                else:
                    self._logger.log(
                        f"[ERROR] Unable to restart {active_name} after {next_name} failed to launch."
                    )
                continue

            if not self._docker.wait_until_healthy(next_cont):
                self._logger.log(
                    f"[WARNING] {next_name} failed to reach a healthy state — stopping container."
                )
                self._docker.stop_container(
                    next_name, reason="failed rotation health check"
                )
                restore = self._docker.start_container(
                    active_name, reason=restore_reason
                )
                if restore and self._docker.wait_until_healthy(restore):
                    self.mark_active(active_name)
                    self._docker.ensure_single_active(active_name, managed_containers)
                else:
                    self._logger.log(
                        f"[ERROR] Unable to restore {active_name} after unhealthy rotation candidate {next_name}."
                    )
                continue

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
        local_cache: Dict[str, ProxyContainer] = {}
        while True:
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
                        if self.container_active_since.get(name):
                            elapsed = int(
                                (
                                    now - self.container_active_since[name]
                                ).total_seconds()
                            )
                            self.container_total_active_seconds[name] = (
                                self.container_total_active_seconds.get(name, 0)
                                + elapsed
                            )
                            self._logger.log(
                                f"[UPTIME] {name} paused (+{elapsed}s, total={self.container_total_active_seconds[name]}s)"
                            )
                            self.container_active_since[name] = None

                time.sleep(1)
            except Exception as exc:
                self._logger.log(f"[UPTIME TRACKER ERROR] {exc}")
                time.sleep(2)

    def _metrics_collector_loop(self) -> None:
        base_interval = max(0.2, self._settings.sse_stream_interval_ms / 1000.0)
        worst_iteration = 0.0
        last_report = time.perf_counter()
        while True:
            loop_start = time.perf_counter()
            try:
                running_containers: List[str] = []
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

                stats_map: Dict[str, Optional[Dict[str, object]]] = {}
                if running_containers:
                    max_workers = min(len(running_containers), 8)
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

                metrics = self._collect_metrics(running_containers, stats_map)
                if metrics:
                    self._append_metrics_history(metrics)
                with self._metrics_lock:
                    self._latest_metrics = metrics
                    self._metrics_updated_at = time.time()
            except Exception as exc:
                self._logger.log(f"[METRICS LOOP ERROR] {exc}")

            elapsed = time.perf_counter() - loop_start
            if elapsed > worst_iteration:
                worst_iteration = elapsed
            if elapsed > 1.0:
                self._logger.log(
                    f"[METRICS LOOP WARN] Iteration exceeded 1s budget: {elapsed:.3f}s"
                )
            now = time.perf_counter()
            if now - last_report >= 60.0:
                self._logger.log(
                    f"[METRICS LOOP] Worst iteration in last interval: {worst_iteration:.3f}s"
                )
                worst_iteration = 0.0
                last_report = now
            delay = max(base_interval - elapsed, 0.05)
            time.sleep(delay)

    def _get_latest_metrics(
        self, running_containers: List[str]
    ) -> Optional[Dict[str, object]]:
        with self._metrics_lock:
            cached_metrics = self._latest_metrics
            cached_timestamp = self._metrics_updated_at

        if cached_metrics is not None and cached_timestamp:
            age = time.time() - cached_timestamp
            base_interval = max(0.2, self._settings.sse_stream_interval_ms / 1000.0)
            freshness_window = max(0.5, base_interval * 2.5)
            if age <= freshness_window:
                return cached_metrics

        metrics = self._collect_metrics(running_containers)
        if metrics:
            self._append_metrics_history(metrics)
        with self._metrics_lock:
            self._latest_metrics = metrics
            self._metrics_updated_at = time.time()
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

    def force_rotate(self) -> tuple[bool, str, Optional[Dict[str, object]]]:
        if not self.rotation_active:
            return False, "Rotation is paused; resume before rotating.", None

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
    def build_stream_snapshot(self) -> Dict[str, object]:
        now = datetime.now(self._settings.timezone)
        containers: Dict[str, Dict[str, object]] = {}
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
        self._append_container_history(timestamp_ms, containers)
        metrics_history = self._get_metrics_history()
        container_history = self._get_container_history()
        snapshot: Dict[str, object] = {
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
        if metrics_history:
            snapshot["metrics_history"] = metrics_history
        if container_history:
            snapshot["container_history"] = container_history
        return snapshot

    def _snapshot_loop(self) -> None:
        interval = max(float(self._settings.sse_stream_interval_seconds), 0.1)
        while True:
            loop_start = time.perf_counter()
            try:
                snapshot = self.build_stream_snapshot()
                self._update_snapshot_cache(snapshot)
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
                time.sleep(delay)

    def get_latest_snapshot(self) -> Dict[str, object]:
        interval = max(float(self._settings.sse_stream_interval_seconds), 0.1)
        stale_threshold = interval * 2
        cached, updated = self._get_snapshot_cache()
        now = time.time()
        if cached and now - updated <= stale_threshold:
            return cached

        try:
            snapshot = self.build_stream_snapshot()
            self._update_snapshot_cache(snapshot)
            return deepcopy(snapshot)
        except (DockerProxyError, DockerProxyNotFound) as exc:
            self._logger.log(
                f"[STREAM WARN] Snapshot rebuild failed due to Docker error: {exc}"
            )
            cached, _ = self._get_snapshot_cache()
            if cached:
                return cached
            return {}
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.log(
                f"[STREAM ERROR] Unexpected snapshot rebuild failure: {exc}\n"
                f"{traceback.format_exc()}"
            )
            cached, _ = self._get_snapshot_cache()
            if cached:
                return cached
            return {}


__all__ = ["RotationService"]
