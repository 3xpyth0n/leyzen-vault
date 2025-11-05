"""Volume synchronization service for Leyzen Vault."""

from __future__ import annotations

import subprocess

from ..config import Settings
from .logging import FileLogger
from .docker_proxy import DockerProxyService


class SyncService:
    """Handles synchronization of volumes from temporary containers to source.

    Note: This service uses subprocess to execute Docker commands directly
    because the Docker Proxy only allows operations on existing containers
    (inspect, start, stop, wait, unpause) and does not permit creating new
    containers or executing commands inside containers. The synchronization
    requires creating a temporary container to run rsync, which is not possible
    through the restricted Docker Proxy API.

    This is an architectural limitation that was accepted to maintain the
    security model of the Docker Proxy (allowlist-based access control).
    """

    def __init__(
        self, settings: Settings, docker: DockerProxyService, logger: FileLogger
    ) -> None:
        self._settings = settings
        self._docker = docker
        self._logger = logger

    def sync_container_data_to_source(self, container_name: str) -> bool:
        """Synchronize data from a container's temporary volume to the source volume.

        This method creates a temporary container using Docker CLI (via subprocess)
        because the Docker Proxy does not support container creation. The temporary
        container mounts both volumes and runs rsync to synchronize data.

        Args:
            container_name: Name of the container whose data should be synchronized

        Returns:
            True if synchronization succeeded, False otherwise
        """
        if not container_name.startswith("vault_web"):
            self._logger.log(
                f"[SYNC] Skipping sync for non-vault container: {container_name}"
            )
            return False

        # Extract volume suffix from container name
        volume_suffix = container_name.replace("vault_", "")
        temp_volume = f"vault-data-{volume_suffix}"
        source_volume = "vault-data-source"

        self._logger.log(
            f"[SYNC] Starting synchronization from {temp_volume} to {source_volume}"
        )

        try:
            # Create a unique temporary container name
            sync_container_name = f"sync-{container_name}-{hash(temp_volume) % 10000}"

            # Use Docker CLI to create and run a temporary sync container
            # Note: This bypasses the Docker Proxy because the proxy doesn't support
            # container creation (security restriction). The sync container is short-lived
            # and only mounts volumes, it doesn't expose ports or networks.
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                sync_container_name,
                "--volumes-from",
                container_name,
                "-v",
                f"{source_volume}:/source:rw",
                "-v",
                f"{temp_volume}:/temp:ro",
                "alpine:latest",
                "sh",
                "-c",
                "rsync -a --update /temp/ /source/",
            ]

            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,  # Don't raise on non-zero exit
            )

            if result.returncode == 0:
                self._logger.log(
                    f"[SYNC] Successfully synchronized {container_name} to source"
                )
                return True
            else:
                self._logger.log(
                    f"[SYNC ERROR] Failed to synchronize {container_name}: {result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired:
            self._logger.log(
                f"[SYNC ERROR] Synchronization timeout for {container_name}"
            )
            return False
        except FileNotFoundError:
            self._logger.log(
                f"[SYNC ERROR] Docker CLI not found. Ensure Docker is installed and accessible."
            )
            return False
        except Exception as exc:
            self._logger.log(
                f"[SYNC ERROR] Exception during synchronization of {container_name}: {exc}"
            )
            return False


__all__ = ["SyncService"]
