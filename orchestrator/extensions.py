"""Application extensions."""

from flask_wtf import CSRFProtect

csrf = CSRFProtect()

__all__ = ["csrf"]
