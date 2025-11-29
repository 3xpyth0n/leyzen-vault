"""Migration to create user_pinned_vaultspaces table."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class PinnedVaultSpacesMigration(Migration):
    """Migration to create user_pinned_vaultspaces table.

    This migration creates the table for storing user pinned VaultSpaces
    for quick access in the sidebar.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "pinned_vaultspaces_table"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if table doesn't exist, False otherwise
        """
        return not self.table_exists("user_pinned_vaultspaces")

    def apply(self) -> None:
        """Apply the migration.

        Creates the user_pinned_vaultspaces table if it doesn't exist.
        This ensures the table exists even if db.create_all() didn't create it
        (e.g., on existing databases where the model was added later).
        """
        if self.table_exists("user_pinned_vaultspaces"):
            logger.debug("user_pinned_vaultspaces table already exists")
            return

        # Import the model to ensure it's registered with SQLAlchemy
        from vault.database.schema import UserPinnedVaultSpace

        # Create the table using the model's table definition
        try:
            UserPinnedVaultSpace.__table__.create(bind=db.engine, checkfirst=True)
            logger.info("user_pinned_vaultspaces table created successfully")
        except Exception as e:
            logger.error(f"Failed to create user_pinned_vaultspaces table: {e}")
            raise
