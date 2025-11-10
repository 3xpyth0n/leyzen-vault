"""Volume synchronization service for Leyzen Vault."""

from __future__ import annotations

import re

import httpx

from ..config import Settings
from common.services.logging import FileLogger
from .docker_proxy import DockerProxyService


class SyncService:
    """Handles synchronization of volumes from temporary containers to source.

    This service uses HTTP API calls to the vault container's internal sync endpoint
    to synchronize data from the ephemeral tmpfs volume (/data) to the persistent
    source volume (/data-source). This approach maintains the security model by
    not requiring Docker CLI access in the orchestrator container.
    """

    def __init__(
        self, settings: Settings, docker: DockerProxyService, logger: FileLogger
    ) -> None:
        self._settings = settings
        self._docker = docker
        self._logger = logger
        self._client = httpx.Client(timeout=httpx.Timeout(300.0))  # 5 minute timeout

    def sync_container_data_to_source(self, container_name: str) -> bool:
        """Synchronize data from a container's temporary volume to the source volume.

        This method calls the vault container's internal sync API endpoint via HTTP
        to synchronize data from /data (tmpfs) to /data-source (persistent). The
        vault container has access to both volumes and performs the synchronization
        internally.

        Args:
            container_name: Name of the container whose data should be synchronized

        Returns:
            True if synchronization succeeded, False otherwise
        """
        # Validate container name with strict regex
        # Maximum length to prevent DoS
        if len(container_name) > 64:
            self._logger.log(f"[SYNC ERROR] Container name too long: {container_name}")
            return False

        # Strict pattern: vault_web followed by number (1-9, then digits)
        container_name_pattern = re.compile(r"^vault_web[1-9][0-9]*$")
        if not container_name_pattern.match(container_name):
            self._logger.log(
                f"[SYNC ERROR] Invalid container name format: {container_name}"
            )
            return False

        self._logger.log(
            f"[SYNC] Starting synchronization for container: {container_name}"
        )

        try:
            # Construct URL to vault container's internal sync endpoint
            # Containers are on the same Docker network, so we can use container name as hostname
            sync_url = f"http://{container_name}/api/internal/sync"

            # Get authentication token from settings (INTERNAL_API_TOKEN, auto-generated from SECRET_KEY)
            token = self._settings.internal_api_token
            if not token:
                self._logger.log(
                    "[SYNC ERROR] INTERNAL_API_TOKEN not available for sync authentication"
                )
                return False

            # Call the sync endpoint
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            self._logger.log(
                f"[SYNC] Calling sync endpoint at {sync_url} for container {container_name}"
            )

            # Send POST request with empty JSON body (Flask requires body when Content-Type is application/json)
            response = self._client.post(
                sync_url, headers=headers, json={}, timeout=300.0
            )

            if response.status_code == 200:
                self._logger.log(
                    f"[SYNC] Successfully synchronized {container_name} to source"
                )
                return True
            elif response.status_code == 401:
                self._logger.log(
                    f"[SYNC ERROR] Authentication failed for {container_name} sync endpoint"
                )
                return False
            else:
                error_msg = response.text.strip()
                self._logger.log(
                    f"[SYNC ERROR] Failed to synchronize {container_name}: HTTP {response.status_code} - {error_msg}"
                )
                return False

        except httpx.TimeoutException:
            self._logger.log(
                f"[SYNC ERROR] Synchronization timeout for {container_name}"
            )
            return False
        except httpx.NetworkError as exc:
            self._logger.log(
                f"[SYNC ERROR] Network error during synchronization of {container_name}: {exc}"
            )
            return False
        except Exception as exc:
            self._logger.log(
                f"[SYNC ERROR] Exception during synchronization of {container_name}: {exc}"
            )
            return False


__all__ = ["SyncService"]
