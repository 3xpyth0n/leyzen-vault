"""Migration to add display_order column to user_pinned_vaultspaces table."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class PinnedVaultSpacesDisplayOrderMigration(Migration):
    """Migration to add display_order column to user_pinned_vaultspaces table.

    This migration adds a display_order column to allow users to customize
    the order of pinned vaultspaces. Existing records are initialized with
    an order based on pinned_at (most recent = 0, then incrementing).
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "pinned_vaultspaces_display_order"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if column doesn't exist, False otherwise
        """
        if not self.table_exists("user_pinned_vaultspaces"):
            return False
        return not self.column_exists("user_pinned_vaultspaces", "display_order")

    def apply(self) -> None:
        """Apply the migration.

        Adds the display_order column and initializes existing records
        with an order based on pinned_at (most recent = 0).
        """
        if not self.table_exists("user_pinned_vaultspaces"):
            logger.debug(
                "user_pinned_vaultspaces table doesn't exist, skipping migration"
            )
            return

        if self.column_exists("user_pinned_vaultspaces", "display_order"):
            logger.debug("display_order column already exists")
            return

        try:
            # Add the column (idempotent - safe to run multiple times)
            logger.info("Adding display_order column to user_pinned_vaultspaces table")
            try:
                self.execute_sql(
                    """
                    ALTER TABLE user_pinned_vaultspaces
                    ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0
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
                    logger.info(
                        "display_order column already exists, skipping ADD COLUMN"
                    )
                else:
                    # Re-raise if it's a different error
                    raise

            # Initialize display_order for existing records based on pinned_at
            # Most recent pinned_at gets display_order = 0, then incrementing
            logger.info("Initializing display_order for existing records")
            self.execute_sql(
                """
                WITH ordered_pins AS (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY pinned_at DESC
                    ) - 1 AS new_order
                    FROM user_pinned_vaultspaces
                )
                UPDATE user_pinned_vaultspaces
                SET display_order = ordered_pins.new_order
                FROM ordered_pins
                WHERE user_pinned_vaultspaces.id = ordered_pins.id
                """
            )

            logger.info(
                "Successfully added display_order column and initialized values"
            )
        except Exception as e:
            # Check if error is "column already exists" - that's fine, migration is idempotent
            error_str = str(e).lower()
            if (
                "duplicatecolumn" in error_str
                or "already exists" in error_str
                or "column.*already exists" in error_str
            ):
                logger.info(
                    "display_order column already exists, migration already applied"
                )
                # Don't raise - migration is idempotent and column already exists
                return
            logger.error(f"Failed to add display_order column: {e}")
            raise
