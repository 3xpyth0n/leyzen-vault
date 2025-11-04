"""ASGI-compatible entry point for the orchestrator service."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from types import ModuleType

from uvicorn.middleware.wsgi import WSGIMiddleware


def _load_orchestrator_module() -> ModuleType:
    """Import the orchestrator.app module regardless of the current working directory."""

    try:
        return importlib.import_module("orchestrator.app")
    except ModuleNotFoundError:
        # Fallback: use the shared ORCHESTRATOR_DIR constant from common.constants
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
