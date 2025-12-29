"""ASGI-compatible entry point for the vault service."""

from __future__ import annotations

import atexit
import importlib
import importlib.util
import signal
import sys
import threading
from pathlib import Path
from types import ModuleType

# Bootstrap minimal to enable importing common.path_setup
# This must be done before importing common modules
# Standard pattern: Manually add src/ to sys.path, then use bootstrap_entry_point()

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

from flask import Flask, Response  # noqa: E402
from uvicorn.middleware.wsgi import WSGIMiddleware  # type: ignore[import-not-found]  # noqa: E402

# Global reference to the Flask app for signal handlers
_flask_app = None
_logger = None
_full_app_ready = threading.Event()
_full_app_middleware = None


def _load_vault_module() -> ModuleType:
    """Import the vault.app module regardless of the current working directory."""

    try:
        return importlib.import_module("vault.app")
    except ModuleNotFoundError:
        # Fallback: try to load from the current directory (Docker: /app/src/vault/app.py)
        current_dir = Path(__file__).resolve().parent
        app_py = current_dir / "app.py"
        init_py = current_dir / "__init__.py"

        if app_py.exists() and init_py.exists():
            # Docker environment: use /app/src/vault directly
            # First, load the vault package (__init__.py) properly
            if "vault" not in sys.modules:
                init_spec = importlib.util.spec_from_file_location(
                    "vault",
                    init_py,
                    submodule_search_locations=[str(current_dir)],
                )
                if init_spec is None or init_spec.loader is None:
                    raise
                vault_pkg = importlib.util.module_from_spec(init_spec)
                sys.modules["vault"] = vault_pkg
                init_spec.loader.exec_module(vault_pkg)

            # Now load app.py as vault.app
            module_path = app_py
        else:
            # Local development: calculate path relative to this file
            _SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
            module_path = _SRC_DIR / "vault" / "app.py"

        spec = importlib.util.spec_from_file_location("vault.app", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("vault.app", module)
        spec.loader.exec_module(module)
        return module


vault_module = _load_vault_module()
flask_app = vault_module.application
create_app = vault_module.create_app


def _create_minimal_app() -> Flask:
    """Create a minimal Flask app that responds to /healthz immediately."""
    minimal_app = Flask(__name__)

    @minimal_app.route("/healthz")
    def healthz():
        """Health check endpoint - responds immediately for fast container startup."""
        return Response('{"status":"ok"}', mimetype="application/json", status=200)

    @minimal_app.route("/<path:path>", defaults={"path": ""})
    @minimal_app.route("/")
    def catch_all(path: str = ""):
        """Catch-all route that returns 503 while full app is initializing."""
        return Response(
            '{"status":"initializing"}', mimetype="application/json", status=503
        )

    return minimal_app


def _load_full_app_in_background() -> None:
    """Load the full Flask application in a background thread."""
    global _flask_app, _logger, _full_app_middleware

    try:
        _flask_app = create_app()
        _logger = _flask_app.config.get("LOGGER")
        _full_app_middleware = WSGIMiddleware(_flask_app)
        _full_app_ready.set()
        if _logger:
            # Use lock to ensure only one worker logs the ready message
            from vault.app import _log_once_with_lock

            # Lock ID: Use two 32-bit integers (high, low) for "READY"
            ADVISORY_LOCK_HIGH = 0x52454144  # "READ"
            ADVISORY_LOCK_LOW = 0x59000000  # "Y" (padded)
            _log_once_with_lock(
                _flask_app,
                _logger,
                "[INIT] Full application loaded and ready",
                ADVISORY_LOCK_HIGH,
                ADVISORY_LOCK_LOW,
                also_stdout=False,
            )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create configured app: {e}", exc_info=True)
        _flask_app = flask_app
        _full_app_middleware = WSGIMiddleware(_flask_app)
        _full_app_ready.set()


class LazyWSGIMiddleware:
    """ASGI middleware that starts with a minimal app and switches to full app when ready."""

    def __init__(self, minimal_app: Flask):
        self.minimal_middleware = WSGIMiddleware(minimal_app)

    async def __call__(self, scope, receive, send):
        """Handle ASGI requests, routing to minimal or full app."""
        if _full_app_ready.is_set() and _full_app_middleware is not None:
            # Full app is ready, use it
            # WSGIMiddleware already handles Flask in a thread pool internally
            await _full_app_middleware(scope, receive, send)
        else:
            # Use minimal app (responds to /healthz immediately)
            await self.minimal_middleware(scope, receive, send)


def create_asgi_app() -> LazyWSGIMiddleware:
    """Return a lazy-loading ASGI app that responds to /healthz immediately."""

    global _flask_app, _logger

    # Create minimal app that responds to /healthz immediately
    minimal_app = _create_minimal_app()

    # Start loading full app in background thread
    background_thread = threading.Thread(
        target=_load_full_app_in_background, daemon=True
    )
    background_thread.start()

    def log_shutdown(sig: int | None = None) -> None:
        """Log shutdown message and flush logger."""
        if _logger is not None:
            if sig is not None:
                _logger.log(f"=== Vault stopped (signal {sig}) ===")
            else:
                _logger.log("=== Vault stopped ===")
            _logger.flush()
        else:
            # Fallback to logging if logger is not available
            import logging

            logger = logging.getLogger(__name__)
            if sig is not None:
                logger.info(f"Vault stopped (signal {sig})")
            else:
                logger.info("Vault stopped")

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

    return LazyWSGIMiddleware(minimal_app)


app = create_asgi_app()
