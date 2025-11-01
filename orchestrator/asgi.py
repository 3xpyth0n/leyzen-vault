"""ASGI-compatible entry point for the orchestrator service."""

from __future__ import annotations

from uvicorn.middleware.wsgi import WSGIMiddleware

from app import app as flask_app


def create_app() -> WSGIMiddleware:
    """Return the orchestrator wrapped for ASGI servers."""

    rotation_service = flask_app.config["ROTATION_SERVICE"]
    rotation_service.start_background_workers()
    return WSGIMiddleware(flask_app)


app = create_app()
