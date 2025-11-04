"""Python path setup utilities for Leyzen Vault modules.

This module centralizes the sys.path manipulation logic used across
different entry points (orchestrator, docker-proxy, compose scripts) to
ensure consistent import resolution for common modules and vault plugins.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Calculate REPO_ROOT locally to avoid circular import issues
# This file is at src/common/path_setup.py, so:
# - parent = common/
# - parent.parent = src/
# - parent.parent.parent = repo root
_REPO_ROOT_CACHE: Path | None = None


def _get_repo_root() -> Path:
    """Get the repository root path, calculating it once and caching the result."""
    global _REPO_ROOT_CACHE
    if _REPO_ROOT_CACHE is None:
        _REPO_ROOT_CACHE = Path(__file__).resolve().parent.parent.parent
    return _REPO_ROOT_CACHE


def bootstrap_src_path() -> None:
    """Bootstrap sys.path to enable importing common modules.

    This function performs the minimal bootstrap needed to import common.path_setup
    and other common modules from entry points that are not executed from the src/
    directory. It should be called before any imports from common.* or vault_plugins.*
    modules.

    This function:
    1. Calculates the repository root and src/ directory paths
    2. Adds src/ to sys.path if not already present

    After calling this function, you can then import setup_python_paths and call it
    to complete the path configuration, or directly import common modules.

    The function is idempotent: calling it multiple times has no additional effect.

    Example usage:
        from pathlib import Path
        import sys

        # Bootstrap minimal to enable importing common.path_setup
        from common.path_setup import bootstrap_src_path
        bootstrap_src_path()

        # Now we can import and use setup_python_paths
        from common.path_setup import setup_python_paths
        setup_python_paths()

        # Now we can import other common modules
        from common.env import load_env_with_override
    """
    # Calculate repository root from the location of this file
    repo_root = _get_repo_root()
    src_dir = repo_root / "src"

    # Add src/ directory to sys.path for common imports
    src_dir_str = str(src_dir)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)


def setup_python_paths() -> None:
    """Configure sys.path to enable imports from common and vault_plugins.

    This function:
    1. Adds the repository root to sys.path
    2. Adds src/ to sys.path for common imports

    This enables imports like:
    - `from common.env import ...`
    - `from vault_plugins.registry import ...`
    - `from compose.base_stack import ...`

    The function is idempotent: calling it multiple times has no additional effect.

    Note: If you're calling this from an entry point that's not in src/, you should
    first call bootstrap_src_path() or bootstrap_entry_point() to enable importing this function.
    """
    # Calculate repository root from the location of this file
    repo_root = _get_repo_root()
    # Add repository root to sys.path if not already present
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    # Add src/ directory to sys.path for common imports
    src_dir = repo_root / "src"
    src_dir_str = str(src_dir)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)


def bootstrap_entry_point() -> None:
    """Complete bootstrap sequence for entry points outside the src/ directory.

    This function performs the complete bootstrap sequence needed for entry points
    (like orchestrator/app.py, docker-proxy/proxy.py, compose/build.py) that are
    executed from outside the src/ directory. It should be called AFTER src/ has
    been manually added to sys.path to enable importing this module.

    The function:
    1. Calls bootstrap_src_path() to ensure src/ is in sys.path (idempotent)
    2. Calls setup_python_paths() to complete path configuration (idempotent)

    This function encapsulates the final two steps of the bootstrap process, eliminating
    the need to call bootstrap_src_path() and setup_python_paths() separately.

    Example usage:
        # In orchestrator/app.py, docker-proxy/proxy.py, or compose/build.py:
        from pathlib import Path
        import sys

        # Step 1: Manually add src/ to sys.path (required before importing this module)
        _REPO_ROOT = Path(__file__).resolve().parent.parent.parent
        _SRC_DIR = _REPO_ROOT / "src"
        if str(_SRC_DIR) not in sys.path:
            sys.path.insert(0, str(_SRC_DIR))

        # Step 2: Import and use bootstrap_entry_point to complete the bootstrap
        from common.path_setup import bootstrap_entry_point
        bootstrap_entry_point()

        # Now we can import other common modules
        from common.env import load_env_with_override
    """
    # Both functions are idempotent, so calling them is safe even if paths are already configured
    bootstrap_src_path()  # Ensures src/ is in sys.path
    setup_python_paths()  # Ensures repo root and src/ are in sys.path


__all__ = [
    "bootstrap_entry_point",
    "bootstrap_src_path",
    "setup_python_paths",
]
