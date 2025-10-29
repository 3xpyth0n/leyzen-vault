"""Rotation and uptime tracking services."""

from __future__ import annotations

import random
import time
import traceback
from datetime import datetime, timedelta
from threading import Lock, Thread
from typing import Dict, Optional

from ..config import Settings
from .docker_proxy import DockerProxyError, DockerProxyService
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
            self._threads_started = True

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
                total_seconds = self.container_total_active_seconds.get(
                    active_name, 0
                )
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
        while True:
            try:
                now = datetime.now(self._settings.timezone)

                for name in self._settings.web_containers:
                    cont = self._docker.get_container_safe(name)
                    if not cont:
                        continue

                    try:
                        cont.reload()
                    except DockerProxyError as exc:
                        self._logger.log(
                            f"[UPTIME ERROR] Failed to reload {name}: {exc}"
                        )
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

            self._logger.log(
                f"[CONTROL] Manual rotation requested from {active_name}"
            )

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
            self._next_switch_override = datetime.now(self._settings.timezone) + timedelta(
                seconds=self._settings.rotation_interval
            )
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
        for name in self._settings.web_containers:
            cont = self._docker.get_container_safe(name)
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

        eta = self.next_rotation_eta
        return {
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
        }


__all__ = ["RotationService"]
