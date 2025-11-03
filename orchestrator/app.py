#!/usr/bin/python3
"""Application entry point for the vault orchestrator."""

from __future__ import annotations

import importlib
import importlib.util
import signal
import sys
from pathlib import Path
from types import ModuleType

from flask import Flask

from leyzen_common.exceptions import ConfigurationError


# Ensure the repository root (which houses the dynamically loaded plugin
# package) is importable even when this module is executed directly from the
# ``orchestrator/`` directory or within the container image.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_orchestrator_package() -> ModuleType:
    """Import the orchestrator package regardless of sys.path layout."""

    try:
        # When executed from the project root the package can be imported normally.
        return importlib.import_module("orchestrator")
    except ModuleNotFoundError:
        package_root = Path(__file__).resolve().parent
        init_py = package_root / "__init__.py"
        if not init_py.exists():  # pragma: no cover - defensive guard
            raise

        spec = importlib.util.spec_from_file_location(
            "orchestrator",
            init_py,
            submodule_search_locations=[str(package_root)],
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
    def _ensure_background_workers():
        rotation_service = flask_app.config["ROTATION_SERVICE"]
        rotation_service.start_background_workers()


def _build_placeholder_app(error: ConfigurationError) -> Flask:
    """Return a tiny Flask app that surfaces configuration errors at runtime."""

    placeholder = Flask("orchestrator.config_error")

    @placeholder.route("/", defaults={"path": ""})
    @placeholder.route("/<path:path>")
    def _missing_config(path: str):  # pragma: no cover - runtime guard
        message = (
            "Leyzen Vault orchestrator cannot start because required environment "
            "variables are missing. Set DOCKER_PROXY_TOKEN, VAULT_PASS, "
            "VAULT_SECRET_KEY, and VAULT_USER before launching the service."
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

    def handle_shutdown(sig, frame):  # pragma: no cover - runtime signal handler
        logger.log(f"=== Orchestrator stopped (signal {sig}) ===")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    real_app.run(host="0.0.0.0", port=80, debug=False)


if __name__ == "__main__":
    main()
