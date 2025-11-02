"""Telemetry helper for the rotation service."""

from __future__ import annotations

import math
import time
from collections import deque
from copy import deepcopy
from threading import Lock
from typing import Callable, Dict, Iterable, Optional

from ..config import Settings


class RotationTelemetry:
    """Tracks metrics, histories, and snapshot caching for rotation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        metrics_interval = max(0.2, settings.sse_stream_interval_ms / 1000.0)
        self._metrics_history_window_seconds = 60.0
        self._metrics_history = deque(
            maxlen=self._calculate_history_maxlen(
                self._metrics_history_window_seconds,
                metrics_interval,
                cap=1800,
            )
        )
        self._metrics_history_lock = Lock()

        self._previous_net_snapshot: Optional[Dict[str, float]] = None
        self._latest_metrics: Optional[Dict[str, object]] = None
        self._metrics_updated_at: float = 0.0
        self._metrics_lock = Lock()

        snapshot_interval = float(settings.sse_stream_interval_seconds)
        self._latest_snapshot: Optional[Dict[str, object]] = None
        self._snapshot_updated_at: float = 0.0
        self._snapshot_lock = Lock()

        self._container_history_window_seconds = 300.0
        self._container_history = deque(
            maxlen=self._calculate_history_maxlen(
                self._container_history_window_seconds,
                snapshot_interval,
                cap=1200,
            )
        )
        self._container_history_lock = Lock()

    # ------------------------------------------------------------------
    def build_metrics(
        self,
        running_containers: Iterable[str],
        stats_lookup: Callable[[str], Optional[Dict[str, object]]],
    ) -> Optional[Dict[str, object]]:
        containers = list(running_containers)
        if not containers:
            now = time.time()
            self._previous_net_snapshot = {"timestamp": now, "rx": 0.0, "tx": 0.0}
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

        for name in containers:
            stats = stats_lookup(name)
            if not stats:
                continue

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

        if cpu_samples:
            avg_cpu = sum(cpu_samples) / len(cpu_samples)
            metrics["cpu"] = {"usage": round(avg_cpu, 2)}

        if total_memory_limit > 0:
            metrics["memory"] = {
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
            if net_payload:
                metrics["net_io"] = net_payload

        return metrics if len(metrics) > 1 else None

    # ------------------------------------------------------------------
    def append_metrics_history(self, metrics: Optional[Dict[str, object]]) -> None:
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

    def get_metrics_history(self) -> list[Dict[str, object]]:
        with self._metrics_history_lock:
            return [deepcopy(entry) for entry in self._metrics_history]

    # ------------------------------------------------------------------
    def append_container_history(
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

    def get_container_history(self) -> list[Dict[str, object]]:
        with self._container_history_lock:
            return [deepcopy(entry) for entry in self._container_history]

    # ------------------------------------------------------------------
    def store_latest_metrics(self, metrics: Optional[Dict[str, object]]) -> None:
        with self._metrics_lock:
            self._latest_metrics = metrics
            self._metrics_updated_at = time.time()

    def get_cached_metrics(self) -> tuple[Optional[Dict[str, object]], float]:
        with self._metrics_lock:
            return self._latest_metrics, self._metrics_updated_at

    # ------------------------------------------------------------------
    def update_snapshot_cache(self, snapshot: Dict[str, object]) -> None:
        with self._snapshot_lock:
            self._latest_snapshot = deepcopy(snapshot)
            self._snapshot_updated_at = time.time()

    def get_snapshot_cache(self) -> tuple[Optional[Dict[str, object]], float]:
        with self._snapshot_lock:
            cached = deepcopy(self._latest_snapshot) if self._latest_snapshot else None
            updated = self._snapshot_updated_at
        return cached, updated

    # ------------------------------------------------------------------
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

    def _calculate_history_maxlen(
        self, window_seconds: float, interval_seconds: float, *, cap: int
    ) -> int:
        interval = max(0.05, float(interval_seconds))
        estimate = int(math.ceil(window_seconds / interval))
        return max(1, min(estimate + 2, cap))


__all__ = ["RotationTelemetry"]
