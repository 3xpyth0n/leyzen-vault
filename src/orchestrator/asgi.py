"""ASGI-compatible entry point for the orchestrator service."""

from __future__ import annotations

import atexit
import importlib
import importlib.util
import signal
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

from flask import Flask  # noqa: E402
from uvicorn.middleware.wsgi import WSGIMiddleware  # type: ignore[import-not-found]  # noqa: E402

# Global references to services for signal handlers
_rotation_service = None
_storage_cleanup_service = None
_logger = None


class HealthCheckMiddleware:
    """Middleware that handles /healthz requests before they reach Flask."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/healthz" or path == "/orchestrator/healthz":
                # Return health check response directly
                response_body = b'{"status":"ok"}'
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"application/json"]],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                    }
                )
                return
        # For all other requests, pass to the wrapped app
        await self.app(scope, receive, send)


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

    global _rotation_service, _storage_cleanup_service, _logger

    try:
        configured_app = get_configured_app()
    except RuntimeError:
        # If app configuration fails, still provide a minimal health check endpoint
        minimal_app = Flask(__name__)

        @minimal_app.route("/healthz")
        def healthz():
            return {"status": "ok"}, 200

        @minimal_app.route("/orchestrator/healthz")
        def orchestrator_healthz():
            return {"status": "ok"}, 200

        return WSGIMiddleware(minimal_app)

    _rotation_service = configured_app.config["ROTATION_SERVICE"]
    _storage_cleanup_service = configured_app.config.get("STORAGE_CLEANUP_SERVICE")
    _logger = configured_app.config["LOGGER"]

    # Start background workers
    _rotation_service.start_background_workers()
    if _storage_cleanup_service:
        _storage_cleanup_service.start_background_worker()

    def log_shutdown(sig: int | None = None) -> None:
        """Log shutdown message and flush logger."""
        if _logger is None:
            return
        if sig is not None:
            _logger.log(f"=== Orchestrator stopped (signal {sig}) ===")
        else:
            _logger.log("=== Orchestrator stopped ===")
        # Clean up rotation service resources
        if _rotation_service is not None:
            _rotation_service.cleanup()
        # Stop storage cleanup worker
        if _storage_cleanup_service is not None:
            _storage_cleanup_service.stop_background_worker()
        _logger.flush()

    def handle_shutdown(
        sig: int, frame: object
    ) -> None:  # pragma: no cover - runtime signal handler
        """Handle shutdown signals gracefully.

        Note: We don't call sys.exit() here because Uvicorn/uvloop handles
        shutdown automatically. Calling sys.exit() causes exceptions in the
        async event loop.
        """
        try:
            log_shutdown(sig)
        except Exception:
            # Ignore errors during shutdown logging
            pass
        # Don't call sys.exit() - let Uvicorn handle shutdown gracefully

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Register atexit handler as backup to ensure shutdown message is logged
    # even if signal handler doesn't execute properly
    atexit.register(log_shutdown)

    return HealthCheckMiddleware(WSGIMiddleware(configured_app))


app = create_app()
