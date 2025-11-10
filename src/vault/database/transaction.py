"""Database transaction management utilities.

This module provides context managers for consistent database transaction handling
across services to ensure proper rollback on errors.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from vault.database.schema import db


@contextmanager
def db_transaction() -> Generator[None, None, None]:
    """Context manager for database transactions with automatic rollback on errors.

    Usage:
        with db_transaction():
            # Database operations
            db.session.add(obj)
            # Transaction is automatically committed on success
            # or rolled back on exception

    Example:
        try:
            with db_transaction():
                user = User(email="test@example.com")
                db.session.add(user)
                # If any exception occurs, transaction is rolled back
        except Exception:
            # Transaction already rolled back
            pass
    """
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


__all__ = ["db_transaction"]
