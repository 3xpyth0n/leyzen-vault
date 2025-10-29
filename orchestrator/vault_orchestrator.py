#!/usr/bin/python3
"""Application entry point for the vault orchestrator."""

from __future__ import annotations

import importlib
import importlib.util
import signal
import sys
from pathlib import Path
from types import ModuleType


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


app = create_app()


# Flask 3 removed ``before_first_request``; ``before_serving`` ensures the
# background workers are started whether the app runs via ``flask run`` or the
# embedded development server.
@app.before_request
def _ensure_background_workers():  # pragma: no cover - Flask hook
    rotation_service = app.config["ROTATION_SERVICE"]
    rotation_service.start_background_workers()


def main() -> None:
    rotation_service = app.config["ROTATION_SERVICE"]
    rotation_service.start_background_workers()

    logger = app.config["LOGGER"]

    def handle_shutdown(sig, frame):  # pragma: no cover - runtime signal handler
        logger.log(f"=== Orchestrator stopped (signal {sig}) ===")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    app.run(host="0.0.0.0", port=80, debug=False)


if __name__ == "__main__":
    main()
