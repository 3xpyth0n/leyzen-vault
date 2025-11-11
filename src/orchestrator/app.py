#!/usr/bin/python3
"""Application entry point for the vault orchestrator."""

from __future__ import annotations

import atexit
import importlib
import importlib.util
import signal
import sys
from pathlib import Path
from types import ModuleType

from flask import Flask

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

from common.exceptions import ConfigurationError  # noqa: E402


def _load_orchestrator_package() -> ModuleType:
    """Import the orchestrator package regardless of sys.path layout."""

    try:
        # When executed from the project root the package can be imported normally.
        return importlib.import_module("orchestrator")
    except ModuleNotFoundError:
        # Fallback: check if we're in Docker (code mounted at /app)
        current_dir = Path(__file__).resolve().parent
        init_py = current_dir / "__init__.py"

        if init_py.exists():
            # Docker environment: use /app/__init__.py directly
            orchestrator_dir = current_dir
        else:
            # Local development: use ORCHESTRATOR_DIR
            from common.constants import ORCHESTRATOR_DIR

            orchestrator_dir = ORCHESTRATOR_DIR
            init_py = orchestrator_dir / "__init__.py"
            if not init_py.exists():  # pragma: no cover - defensive guard
                raise

        spec = importlib.util.spec_from_file_location(
            "orchestrator",
            init_py,
            submodule_search_locations=[str(orchestrator_dir)],
        )
        if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
            raise

        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("orchestrator", module)
        spec.loader.exec_module(module)
        return module


orchestrator_pkg = _load_orchestrator_package()
create_app = orchestrator_pkg.create_app


def _register_runtime_hooks(flask_app: Flask) -> None:
    """Attach runtime hooks that require a fully configured Flask app."""

    @flask_app.before_request  # pragma: no cover - Flask hook
    def _ensure_background_workers() -> None:
        """Ensure background workers are started on first request."""
        rotation_service = flask_app.config["ROTATION_SERVICE"]
        rotation_service.start_background_workers()


def _build_placeholder_app(error: ConfigurationError) -> Flask:
    """Return a tiny Flask app that surfaces configuration errors at runtime."""

    placeholder = Flask("orchestrator.config_error")

    @placeholder.route("/", defaults={"path": ""})
    @placeholder.route("/<path:path>")
    def _missing_config(
        path: str,
    ) -> tuple[str, int, dict[str, str]]:  # pragma: no cover - runtime guard
        """Return error message when configuration is missing."""
        # Log the detailed error server-side for debugging
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Configuration error: {error}")

        # Return generic error message to avoid information disclosure
        # Do not expose specific environment variable names or implementation details
        message = (
            "Leyzen Vault orchestrator cannot start because required configuration "
            "is missing or invalid. Please check your environment variables and "
            "refer to the documentation for required settings."
        )
        return message, 500, {"Content-Type": "text/plain; charset=utf-8"}

    placeholder.config["CONFIGURATION_ERROR"] = error
    return placeholder


try:
    app = create_app()
except ConfigurationError as exc:
    app = _build_placeholder_app(exc)
else:
    _register_runtime_hooks(app)


def get_configured_app() -> Flask:
    """Return the real Flask app or raise a helpful error when misconfigured."""

    if "ROTATION_SERVICE" not in app.config:
        error = app.config.get("CONFIGURATION_ERROR")
        if isinstance(error, ConfigurationError):
            raise RuntimeError("Orchestrator configuration is incomplete") from error
        raise RuntimeError("Orchestrator application failed to initialize")

    return app


def main() -> None:
    real_app = get_configured_app()

    rotation_service = real_app.config["ROTATION_SERVICE"]
    rotation_service.start_background_workers()

    logger = real_app.config["LOGGER"]

    def log_shutdown(sig: int | None = None) -> None:
        """Log shutdown message and flush logger."""
        if sig is not None:
            logger.log(f"=== Orchestrator stopped (signal {sig}) ===")
        else:
            logger.log("=== Orchestrator stopped ===")
        # Clean up rotation service resources
        rotation_service.cleanup()
        logger.flush()

    def handle_shutdown(
        sig: int, frame: object
    ) -> None:  # pragma: no cover - runtime signal handler
        """Handle shutdown signals gracefully."""
        log_shutdown(sig)
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Register atexit handler as backup to ensure shutdown message is logged
    # even if signal handler doesn't execute properly
    atexit.register(log_shutdown)

    settings = real_app.config["SETTINGS"]
    # nosec B104: Binding to 0.0.0.0 is intentional and safe in Docker containers.
    # The orchestrator runs in an isolated Docker network and is only accessible
    # internally. External access is controlled by HAProxy which exposes only
    # the configured ports with proper security headers.
    real_app.run(host="0.0.0.0", port=settings.orchestrator_port, debug=False)


if __name__ == "__main__":
    main()
