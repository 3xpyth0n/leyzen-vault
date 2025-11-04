"""ASGI-compatible entry point for the orchestrator service."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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

from uvicorn.middleware.wsgi import WSGIMiddleware  # type: ignore[import-not-found]


def _load_orchestrator_module() -> ModuleType:
    """Import the orchestrator.app module regardless of the current working directory."""

    try:
        return importlib.import_module("orchestrator.app")
    except ModuleNotFoundError:
        # Fallback: try to load from the current directory (Docker: /app/app.py)
        # or use the shared ORCHESTRATOR_DIR constant from common.constants
        current_dir = Path(__file__).resolve().parent
        app_py = current_dir / "app.py"
        init_py = current_dir / "__init__.py"

        if app_py.exists() and init_py.exists():
            # Docker environment: use /app directly
            # First, load the orchestrator package (__init__.py) properly
            if "orchestrator" not in sys.modules:
                init_spec = importlib.util.spec_from_file_location(
                    "orchestrator",
                    init_py,
                    submodule_search_locations=[str(current_dir)],
                )
                if init_spec is None or init_spec.loader is None:
                    raise
                orchestrator_pkg = importlib.util.module_from_spec(init_spec)
                sys.modules["orchestrator"] = orchestrator_pkg
                init_spec.loader.exec_module(orchestrator_pkg)

            # Now load app.py as orchestrator.app
            module_path = app_py
        else:
            # Local development: use ORCHESTRATOR_DIR
            from common.constants import ORCHESTRATOR_DIR

            module_path = ORCHESTRATOR_DIR / "app.py"

        spec = importlib.util.spec_from_file_location("orchestrator.app", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("orchestrator.app", module)
        spec.loader.exec_module(module)
        return module


orchestrator_module = _load_orchestrator_module()
flask_app = orchestrator_module.app
get_configured_app = orchestrator_module.get_configured_app


def create_app() -> WSGIMiddleware:
    """Return the orchestrator wrapped for ASGI servers."""

    try:
        configured_app = get_configured_app()
    except RuntimeError:
        return WSGIMiddleware(flask_app)

    rotation_service = configured_app.config["ROTATION_SERVICE"]
    rotation_service.start_background_workers()
    return WSGIMiddleware(configured_app)


app = create_app()
