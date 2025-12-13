"""Migration to create database_backups table."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration
from vault.database import db

logger = logging.getLogger(__name__)


class DatabaseBackupMigration(Migration):
    """Migration to create database_backups table.

    This migration creates the table for storing database backup records
    with metadata about each backup operation.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "database_backups_table"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if table doesn't exist, False otherwise
        """
        return not self.table_exists("database_backups")

    def apply(self) -> None:
        """Apply the migration.

        Creates the database_backups table if it doesn't exist.
        This ensures the table exists even if db.create_all() didn't create it
        (e.g., on existing databases where the model was added later).
        """
        if self.table_exists("database_backups"):
            logger.debug("database_backups table already exists")
            return

        # Import the model to ensure it's registered with SQLAlchemy
        from vault.database.schema import DatabaseBackup

        # Create the table using the model's table definition
        try:
            DatabaseBackup.__table__.create(bind=db.engine, checkfirst=True)
            logger.info("database_backups table created successfully")
        except Exception as e:
            logger.error(f"Failed to create database_backups table: {e}")
            raise
