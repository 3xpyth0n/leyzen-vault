"""Application extensions."""

from flask_wtf import CSRFProtect  # type: ignore[import-not-found]
from vault.database.schema import db as _db

csrf = CSRFProtect()


db = _db

__all__ = ["csrf", "db"]
