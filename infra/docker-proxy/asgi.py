"""ASGI entry point for the Docker proxy service."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from uvicorn.middleware.wsgi import WSGIMiddleware  # type: ignore[import-not-found]

# Bootstrap minimal to enable importing common.path_setup
# This must be done before importing common modules
# Standard pattern: Manually add src/ to sys.path, then use bootstrap_entry_point()
# Note: This local calculation is ONLY needed for the initial bootstrap before
# common.constants can be imported. After bootstrap, use SRC_DIR from common.constants.
# In Docker, /common is mounted as a volume, so we check that first.
_COMMON_DIR = Path("/common")
if _COMMON_DIR.exists() and _COMMON_DIR.is_dir():
    # Docker environment: use the mounted /common volume
    # Add / to sys.path so that 'common' can be imported as a package
    root_path = str(_COMMON_DIR.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
else:
    # Local development: calculate path relative to this file
    _SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point  # noqa: E402

# Complete the bootstrap sequence (idempotent)
bootstrap_entry_point()

# Now we can import from common.constants - use centralized values for consistency
from common.constants import DOCKER_PROXY_DIR  # noqa: E402


def _load_proxy_module() -> ModuleType:
    """Import the proxy module regardless of the current working directory."""

    try:
        return importlib.import_module("proxy")
    except ModuleNotFoundError:
        # Fallback: use the shared DOCKER_PROXY_DIR constant from common.constants
        module_path = DOCKER_PROXY_DIR / "proxy.py"
        spec = importlib.util.spec_from_file_location("proxy", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("proxy", module)
        spec.loader.exec_module(module)
        return module


proxy_module = _load_proxy_module()
flask_app = proxy_module.app


def create_app() -> WSGIMiddleware:
    """Wrap the Flask proxy in ASGI middleware for Uvicorn."""

    return WSGIMiddleware(flask_app)


app = create_app()
