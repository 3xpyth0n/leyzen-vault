"""ASGI entry point for the Docker proxy service."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from uvicorn.middleware.wsgi import WSGIMiddleware


def _load_proxy_module() -> ModuleType:
    """Import the proxy module regardless of the current working directory."""

    try:
        return importlib.import_module("proxy")
    except ModuleNotFoundError:
        module_path = Path(__file__).resolve().parent / "proxy.py"
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
