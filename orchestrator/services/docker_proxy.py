"""Docker proxy helpers."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from ..config import Settings
from .logging import FileLogger


class DockerProxyError(RuntimeError):
    """Base error for controlled Docker proxy failures."""


class DockerProxyNotFound(DockerProxyError):
    """Raised when a container is not present on the proxy side."""


class DockerProxyClient:
    """Minimal wrapper around the docker-proxy API with ACL enforcement."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = (base_url or "http://docker-proxy:2375").rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        request_timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = self._session.request(
                method,
                url,
                timeout=request_timeout,
                headers=headers,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise DockerProxyError(
                f"Failed to reach docker proxy at {self.base_url}: {exc}"
            ) from exc

        if response.status_code == 404:
            raise DockerProxyNotFound(f"Container not found for path {path}")

        if not response.ok:
            raise DockerProxyError(
                f"Proxy error {response.status_code}: {response.text.strip()}"
            )

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise DockerProxyError("Invalid JSON received from proxy") from exc

    def inspect(self, name: str) -> Dict[str, Any]:
        data = self._request("GET", f"containers/{name}/json")
        if not isinstance(data, dict):
            data = {}

        state = data.get("State", {}).get("Status")
        return {"status": state, "attrs": data}

    def stats(self, name: str) -> Dict[str, Any]:
        data = self._request(
            "GET",
            f"containers/{name}/stats",
            params={"stream": "false"},
        )
        if not isinstance(data, dict):
            return {}
        return data

    def start(self, name: str) -> None:
        self._request("POST", f"containers/{name}/start")

    def stop(self, name: str, timeout: Optional[int] = None) -> None:
        params = {"t": timeout} if timeout is not None else None
        self._request("POST", f"containers/{name}/stop", params=params)

    def wait(self, name: str, timeout: Optional[int] = None) -> None:
        request_timeout = timeout if timeout is not None else self.timeout
        self._request("POST", f"containers/{name}/wait", timeout=request_timeout)

    def unpause(self, name: str) -> None:
        self._request("POST", f"containers/{name}/unpause")


class ProxyContainer:
    """Container facade backed by DockerProxyClient responses."""

    def __init__(
        self,
        client: DockerProxyClient,
        name: str,
        payload: Dict[str, Any],
        *,
        cache_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        cache_invalidate: Optional[Callable[[], None]] = None,
        payload_timestamp: Optional[float] = None,
    ):
        self._client = client
        self.name = name
        self._payload = payload
        self._payload_timestamp = payload_timestamp or time.time()
        self._cache_update = cache_update
        self._cache_invalidate = cache_invalidate

    def reload(self) -> None:
        payload = self._client.inspect(self.name)
        self._payload = payload
        self._payload_timestamp = time.time()
        if self._cache_update:
            self._cache_update(payload)

    def ensure_fresh(self, max_age: float) -> None:
        if max_age <= 0:
            self.reload()
            return
        if time.time() - self._payload_timestamp > max_age:
            self.reload()

    @property
    def status(self) -> Optional[str]:
        status = self._payload.get("status")
        if status:
            return status
        attrs = self.attrs
        if isinstance(attrs, dict):
            return attrs.get("State", {}).get("Status")
        return None

    @property
    def attrs(self) -> Dict[str, Any]:
        attrs = self._payload.get("attrs")
        if isinstance(attrs, dict):
            return attrs
        return {}

    def start(self) -> None:
        if self._cache_invalidate:
            self._cache_invalidate()
        self._client.start(self.name)
        self.reload()

    def stop(self, timeout: Optional[int] = None) -> None:
        if self._cache_invalidate:
            self._cache_invalidate()
        self._client.stop(self.name, timeout=timeout)
        self.reload()

    def wait(self, timeout: Optional[int] = None) -> None:
        self._client.wait(self.name, timeout=timeout)

    def unpause(self) -> None:
        if self._cache_invalidate:
            self._cache_invalidate()
        self._client.unpause(self.name)
        self.reload()


INSPECT_CACHE_TTL = 2.0


class DockerProxyService:
    """High-level helpers around the docker proxy client."""

    def __init__(self, settings: Settings, logger: FileLogger) -> None:
        self._settings = settings
        self._logger = logger
        self.client = DockerProxyClient(
            base_url=settings.docker_proxy_url,
            token=settings.docker_proxy_token,
        )
        self.managed_container_names = set(settings.web_containers)
        self._inspect_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_meta: Dict[str, float] = {}
        self._cache_lock = Lock()

    @property
    def web_containers(self) -> list[str]:
        return list(self._settings.web_containers)

    def get_container_safe(self, name: str) -> Optional[ProxyContainer]:
        if name not in self.managed_container_names:
            self._logger.log(f"[ERROR] Attempt to access unmanaged container {name}")
            return None

        cached = self._get_cached_payload(name)
        if cached is None:
            refreshed = self.refresh_container_cache(name)
            if refreshed is None:
                return None
            payload, timestamp = refreshed
        else:
            payload, timestamp = cached

        return ProxyContainer(
            self.client,
            name,
            payload,
            payload_timestamp=timestamp,
            cache_update=lambda data: self._store_cache(name, data),
            cache_invalidate=lambda: self.invalidate_container_cache(name),
        )

    def get_container_stats(self, name: str) -> Optional[Dict[str, Any]]:
        if name not in self.managed_container_names:
            self._logger.log(
                f"[ERROR] Attempt to read stats for unmanaged container {name}"
            )
            return None

        try:
            return self.client.stats(name)
        except (DockerProxyNotFound, DockerProxyError):
            return None

    def _get_cached_payload(self, name: str) -> Optional[Tuple[Dict[str, Any], float]]:
        with self._cache_lock:
            entry = self._inspect_cache.get(name)
            if entry is None:
                return None

            # If the cached inspect payload is too old return ``None`` so the
            # caller refreshes it from the proxy.  This prevents the
            # orchestrator UI from getting stuck with stale state (e.g. a
            # container forever reported as ``starting``) when no other
            # operation refreshes the cache for a while.
            timestamp = self._cache_meta.get(name)
            if timestamp is not None:
                # The inspect payload contains container state data which can
                # change quickly when a container is warming up.  A short TTL
                # keeps the dashboard responsive without overwhelming the
                # proxy.
                if time.time() - timestamp > INSPECT_CACHE_TTL:
                    self._inspect_cache.pop(name, None)
                    self._cache_meta.pop(name, None)
                    return None

            if timestamp is None:
                timestamp = time.time()

            return entry, timestamp

    def _store_cache(self, name: str, payload: Dict[str, Any]) -> float:
        timestamp = time.time()
        with self._cache_lock:
            self._inspect_cache[name] = payload
            self._cache_meta[name] = timestamp
        return timestamp

    def invalidate_container_cache(self, name: str) -> None:
        with self._cache_lock:
            self._inspect_cache.pop(name, None)
            self._cache_meta.pop(name, None)

    def refresh_container_cache(
        self, name: str
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        try:
            payload = self.client.inspect(name)
        except DockerProxyNotFound:
            self.invalidate_container_cache(name)
            self._logger.log(f"[ERROR] Container {name} not found")
            return None
        except DockerProxyError as exc:
            self._logger.log(f"[ERROR] Error getting container {name}: {exc}")
            return None

        timestamp = self._store_cache(name, payload)
        return payload, timestamp

    def wait_until_healthy(
        self,
        container: ProxyContainer,
        *,
        check_interval: int = 2,
        log_interval: int = 30,
    ) -> bool:
        last_log = time.time()
        name = getattr(container, "name", "<unknown>")

        while True:
            try:
                container.reload()
            except DockerProxyNotFound:
                self._logger.log(
                    f"[WAIT ERROR] Container {name} disappeared during warmup"
                )
                return False
            except DockerProxyError as exc:
                self._logger.log(f"[WAIT ERROR] Failed to reload {name}: {exc}")
                time.sleep(check_interval)
                continue

            health = container.attrs.get("State", {}).get("Health", {}).get("Status")
            status = container.status

            if status == "running" and (health is None or health == "healthy"):
                return True

            if status in {"exited", "dead"}:
                self._logger.log(
                    f"[WAIT ERROR] {name} stopped while warming up (status={status}, health={health})"
                )
                return False

            now = time.time()
            if now - last_log >= log_interval:
                self._logger.log(
                    f"[WAIT] Waiting for {name} to become healthy "
                    f"(status={status}, health={health})"
                )
                last_log = now

            time.sleep(check_interval)

    def stop_container(
        self, name: str, *, reason: Optional[str] = None, timeout: int = 30
    ) -> bool:
        cont = self.get_container_safe(name)
        if not cont:
            return False

        try:
            cont.reload()
        except DockerProxyError as exc:
            self._logger.log(f"[STOP ERROR] Failed to reload {name} before stop: {exc}")

        status = getattr(cont, "status", None)
        if status == "paused":
            try:
                cont.unpause()
                cont.reload()
                status = cont.status
            except DockerProxyError as exc:
                self._logger.log(f"[STOP ERROR] Failed to unpause {name}: {exc}")

        if status not in ("running", "restarting"):
            return False

        try:
            cont.stop(timeout=timeout)
            try:
                cont.wait(timeout=timeout)
            except DockerProxyError:
                pass
            log_reason = f" ({reason})" if reason else ""
            self._logger.log(f"[ACTION] Stopped {name}{log_reason}")
            return True
        except Exception as exc:
            self._logger.log(f"[STOP ERROR] Failed to stop {name}: {exc}")
            return False

    def start_container(
        self, name: str, *, reason: Optional[str] = None
    ) -> Optional[ProxyContainer]:
        cont = self.get_container_safe(name)
        if not cont:
            return None

        try:
            cont.reload()
        except DockerProxyError as exc:
            self._logger.log(
                f"[START ERROR] Failed to reload {name} before start: {exc}"
            )

        status = getattr(cont, "status", None)
        if status == "paused":
            try:
                cont.unpause()
                cont.reload()
                status = cont.status
            except DockerProxyError as exc:
                self._logger.log(f"[START ERROR] Failed to unpause {name}: {exc}")

        if status == "running":
            return cont

        try:
            cont.start()
            log_reason = f" ({reason})" if reason else ""
            self._logger.log(f"[ACTION] Started {name}{log_reason}")
        except Exception as exc:
            self._logger.log(f"[START ERROR] Failed to start {name}: {exc}")
            return None

        return self.get_container_safe(name)

    def ensure_single_active(self, active_name: str, managed_names: list[str]) -> None:
        for name in managed_names:
            if name == active_name:
                continue
            cont = self.get_container_safe(name)
            if cont and cont.status == "running":
                self.stop_container(name, reason="enforcing single active container")


__all__ = [
    "DockerProxyClient",
    "DockerProxyError",
    "DockerProxyNotFound",
    "DockerProxyService",
    "ProxyContainer",
]
