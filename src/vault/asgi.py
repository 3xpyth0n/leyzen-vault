"""ASGI-compatible entry point for the vault service."""

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

from uvicorn.middleware.wsgi import WSGIMiddleware  # type: ignore[import-not-found]

# Global reference to the Flask app for signal handlers
_flask_app = None
_logger = None


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


def create_asgi_app() -> WSGIMiddleware:
    """Return the vault Flask app wrapped for ASGI servers."""

    global _flask_app, _logger

    try:
        _flask_app = create_app()
        # Try to get logger from app config if available
        _logger = _flask_app.config.get("LOGGER")
    except Exception as e:
        # If create_app fails, use the default application
        print(f"[WARNING] Failed to create configured app: {e}", file=sys.stderr)
        _flask_app = flask_app

    def log_shutdown(sig: int | None = None) -> None:
        """Log shutdown message and flush logger."""
        if _logger is not None:
            if sig is not None:
                _logger.log(f"=== Vault stopped (signal {sig}) ===")
            else:
                _logger.log("=== Vault stopped ===")
            _logger.flush()
        else:
            # Fallback to print if logger is not available
            if sig is not None:
                print(f"[INFO] Vault stopped (signal {sig})", file=sys.stderr)
            else:
                print("[INFO] Vault stopped", file=sys.stderr)

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

    return WSGIMiddleware(_flask_app)


app = create_asgi_app()
