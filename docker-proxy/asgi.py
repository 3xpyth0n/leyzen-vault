"""ASGI entry point for the Docker proxy service."""

from __future__ import annotations

from uvicorn.middleware.wsgi import WSGIMiddleware

from proxy import app as flask_app


def create_app() -> WSGIMiddleware:
    """Wrap the Flask proxy in ASGI middleware for Uvicorn."""

    return WSGIMiddleware(flask_app)


app = create_app()
