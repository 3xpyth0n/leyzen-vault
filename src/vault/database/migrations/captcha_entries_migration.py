"""Migration to create captcha_entries table."""

from __future__ import annotations

import logging
import time

from sqlalchemy.exc import InternalError, ProgrammingError

from vault.database.migrations.base import Migration
from vault.database.schema import db

logger = logging.getLogger(__name__)


class CaptchaEntriesMigration(Migration):
    """Migration to create captcha_entries table.

    This migration creates the table for storing CAPTCHA entries in the database
    to support multi-worker synchronization and ensure each user session has
    a unique CAPTCHA.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "captcha_entries_table"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if table doesn't exist, False otherwise
        """
        return not self.table_exists("captcha_entries")

    def apply(self) -> None:
        """Apply the migration.

        Creates the captcha_entries table if it doesn't exist.
        This ensures the table exists even if db.create_all() didn't create it
        (e.g., on existing databases where the model was added later).
        """
        if self.table_exists("captcha_entries"):
            logger.debug("captcha_entries table already exists")
            return

        # Import the model to ensure it's registered with SQLAlchemy
        from vault.database.schema import CaptchaEntry

        # Create the table using the model's table definition
        try:
            CaptchaEntry.__table__.create(bind=db.engine, checkfirst=True)
            logger.info("captcha_entries table created successfully")
        except (ProgrammingError, InternalError) as e:
            error_msg = str(e).lower()
            # Handle concurrent creation attempts
            if (
                "already exists" in error_msg
                or "duplicate" in error_msg
                or "pg_type_typname_nsp_index" in error_msg
            ):
                logger.debug(
                    "captcha_entries table already exists (concurrent creation)"
                )
                # Verify it exists now
                time.sleep(0.2)
                if not self.table_exists("captcha_entries"):
                    raise RuntimeError(
                        "Database reported captcha_entries table exists but verification failed"
                    )
                logger.info("captcha_entries table verified after concurrent creation")
            else:
                logger.error(f"Failed to create captcha_entries table: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to create captcha_entries table: {e}")
            raise
