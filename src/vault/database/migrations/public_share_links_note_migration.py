"""Migration to add note column to public_share_links table."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class PublicShareLinksNoteMigration(Migration):
    """Migration to add note column to public_share_links table.

    This migration adds a note column to allow users to add notes
    to share links for better organization and differentiation.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "public_share_links_note"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if column doesn't exist, False otherwise
        """
        if not self.table_exists("public_share_links"):
            return False
        return not self.column_exists("public_share_links", "note")

    def apply(self) -> None:
        """Apply the migration.

        Adds the note column to public_share_links table.
        """
        if not self.table_exists("public_share_links"):
            logger.debug("public_share_links table doesn't exist, skipping migration")
            return

        if self.column_exists("public_share_links", "note"):
            logger.debug("note column already exists")
            return

        try:
            # Add the column (idempotent - safe to run multiple times)
            logger.info("Adding note column to public_share_links table")
            try:
                self.execute_sql(
                    """
                    ALTER TABLE public_share_links
                    ADD COLUMN note VARCHAR(500) NULL
                    """
                )
            except Exception as add_col_error:
                # Check if error is "column already exists" - that's fine, migration is idempotent
                error_str = str(add_col_error).lower()
                if (
                    "duplicatecolumn" in error_str
                    or "already exists" in error_str
                    or "column.*already exists" in error_str
                ):
                    logger.info("note column already exists, skipping ADD COLUMN")
                else:
                    # Re-raise if it's a different error
                    raise

            logger.info("Successfully added note column to public_share_links table")
        except Exception as e:
            # Check if error is "column already exists" - that's fine, migration is idempotent
            error_str = str(e).lower()
            if (
                "duplicatecolumn" in error_str
                or "already exists" in error_str
                or "column.*already exists" in error_str
            ):
                logger.info("note column already exists, migration already applied")
                # Don't raise - migration is idempotent and column already exists
                return
            logger.error(f"Failed to add note column: {e}")
            raise
