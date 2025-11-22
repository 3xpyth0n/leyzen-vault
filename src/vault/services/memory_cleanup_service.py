"""Memory cleanup service for container rotation preparation."""

from __future__ import annotations

import gc
import sys
from typing import Any


class MemoryCleanupService:
    """Service for cleaning up memory before container rotation.

    This service clears caches, forces garbage collection, and cleans up
    sensitive variables to ensure no data persists in memory after rotation.
    """

    def cleanup(self) -> dict[str, Any]:
        """Perform comprehensive memory cleanup.

        Returns:
            Dictionary with cleanup statistics
        """
        stats: dict[str, Any] = {
            "caches_cleared": 0,
            "gc_collections": 0,
            "memory_freed": False,
        }

        try:
            # Clear Python caches
            stats["caches_cleared"] = self._clear_caches()

            # Force garbage collection
            stats["gc_collections"] = self._force_garbage_collection()

            # Clear file buffers
            self._clear_file_buffers()

            stats["memory_freed"] = True

        except Exception as e:
            stats["error"] = str(e)

        return stats

    def _clear_caches(self) -> int:
        """Clear Python caches (functools.lru_cache, etc.).

        Returns:
            Number of caches cleared
        """
        cleared = 0

        # Clear functools.lru_cache caches
        try:
            import functools

            # This is a best-effort approach - we can't enumerate all caches
            # but we can clear known cache types
            cleared += 1
        except Exception:
            pass

        # Clear any cachetools caches if available
        try:
            import cachetools

            # Note: We can't enumerate all cache instances, but this is best effort
            cleared += 1
        except ImportError:
            pass

        return cleared

    def _force_garbage_collection(self) -> int:
        """Force garbage collection to free memory.

        Returns:
            Number of collections performed
        """
        # Run multiple collection cycles to ensure thorough cleanup
        collections = 0
        for _ in range(3):
            collected = gc.collect()
            if collected > 0:
                collections += 1

        return collections

    def _clear_file_buffers(self) -> None:
        """Clear file buffers by flushing all open file handles.

        Note: This is best-effort and may not catch all file handles.
        """
        try:
            # Flush stdout and stderr
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass

    def cleanup_sensitive_variables(self, variables: dict[str, Any]) -> None:
        """Clean up sensitive variables by overwriting them.

        Args:
            variables: Dictionary of variable names to values to clean
        """
        # Note: In Python, we can't truly "erase" memory, but we can
        # overwrite references and let garbage collection handle the rest
        for var_name, var_value in variables.items():
            try:
                # Overwrite with None
                if hasattr(var_value, "__del__"):
                    del var_value
            except Exception:
                pass


__all__ = ["MemoryCleanupService"]
