"""Application extensions."""

from flask_wtf import CSRFProtect  # type: ignore[import-not-found]

csrf = CSRFProtect()

__all__ = ["csrf"]
