"""ASGI-compatible entry point for the orchestrator service."""

from __future__ import annotations

from uvicorn.middleware.wsgi import WSGIMiddleware

try:
    from orchestrator.app import app as flask_app, get_configured_app
except ModuleNotFoundError:  # pragma: no cover - runtime path fallback
    from app import app as flask_app, get_configured_app  # type: ignore[import-not-found]


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
