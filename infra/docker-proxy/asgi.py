"""ASGI entry point for the Docker proxy service."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from uvicorn.middleware.wsgi import WSGIMiddleware

# Bootstrap minimal to enable importing common.constants
# This must be done before importing common modules
# Standard pattern: Manually add src/ to sys.path, then use bootstrap_entry_point()
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point

# Complete the bootstrap sequence (idempotent)
bootstrap_entry_point()

# Now we can import from common.constants - use centralized values for consistency
from common.constants import DOCKER_PROXY_DIR, REPO_ROOT, SRC_DIR

# Reassign to use centralized constants (bootstrap already done, these are just for consistency)
_REPO_ROOT = REPO_ROOT
_SRC_DIR = SRC_DIR


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
