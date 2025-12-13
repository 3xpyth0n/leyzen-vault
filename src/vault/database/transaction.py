"""Database transaction management utilities.

This module provides context managers for consistent database transaction handling
across services to ensure proper rollback on errors, with automatic retry for
transient errors like deadlocks and concurrent updates.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from vault.database.schema import db

logger = logging.getLogger(__name__)

# Maximum number of retry attempts for transient errors
MAX_RETRIES = 5

# Base delay in seconds for exponential backoff
BASE_RETRY_DELAY = 0.1


def _is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable (transient database error).

    Args:
        exception: Exception to check

    Returns:
        True if the error is retryable, False otherwise
    """
    error_str = str(exception).lower()
    error_type = type(exception).__name__

    # Check for PostgreSQL deadlock errors
    if "deadlock" in error_str or "deadlock_detected" in error_str:
        return True

    # Check for concurrent update errors
    if (
        "tuple concurrently updated" in error_str
        or "could not serialize access" in error_str
        or "serialization failure" in error_str
    ):
        return True

    # Check for transaction aborted errors (can be retried)
    if (
        "infailedsqltransaction" in error_type.lower()
        or "transaction is aborted" in error_str
    ):
        return True

    # Check for lock timeout errors (can be retried)
    if "lock_timeout" in error_str or "could not obtain lock" in error_str:
        return True

    # Check for connection errors (can be retried)
    if "connection" in error_str and ("lost" in error_str or "closed" in error_str):
        return True

    return False


@contextmanager
def db_transaction(max_retries: int = MAX_RETRIES) -> Generator[None, None, None]:
    """Context manager for database transactions with automatic rollback on errors
    and retry for transient errors.

    Automatically retries on transient database errors like deadlocks, concurrent
    updates, and serialization failures. Uses exponential backoff between retries.

    Args:
        max_retries: Maximum number of retry attempts (default: 5)

    Usage:
        with db_transaction():
            # Database operations
            db.session.add(obj)
            # Transaction is automatically committed on success
            # or rolled back on exception
            # Retries automatically on transient errors

    Example:
        try:
            with db_transaction():
                user = User(email="test@example.com")
                db.session.add(user)
                # If any exception occurs, transaction is rolled back
                # If it's a transient error, it will be retried automatically
        except Exception:
            # Transaction already rolled back after all retries exhausted
            pass
    """
    attempt = 0
    last_exception = None

    while attempt < max_retries:
        try:
            yield
            db.session.commit()
            # Success - exit retry loop
            if attempt > 0:
                logger.debug(f"Transaction succeeded after {attempt} retry attempt(s)")
            return
        except Exception as e:
            db.session.rollback()
            last_exception = e

            # Check if error is retryable
            if not _is_retryable_error(e):
                # Not retryable - raise immediately
                raise

            attempt += 1

            if attempt < max_retries:
                # Calculate exponential backoff delay
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"Transient database error (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                # All retries exhausted
                logger.error(
                    f"Transaction failed after {max_retries} attempts: {e}",
                    exc_info=True,
                )
                raise


__all__ = ["db_transaction"]
