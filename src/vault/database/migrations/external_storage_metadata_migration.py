"""Migration to create external_storage_metadata table."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration
from vault.database.schema import db

logger = logging.getLogger(__name__)


class ExternalStorageMetadataMigration(Migration):
    """Migration to create external_storage_metadata table.

    This migration creates the table for storing external storage S3 metadata
    for tracking file synchronization status.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "external_storage_metadata_table"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if table doesn't exist, False otherwise
        """
        return not self.table_exists("external_storage_metadata")

    def apply(self) -> None:
        """Apply the migration.

        Creates the external_storage_metadata table if it doesn't exist.
        This ensures the table exists even if db.create_all() didn't create it
        (e.g., on existing databases where the model was added later).
        """
        if self.table_exists("external_storage_metadata"):
            logger.debug("external_storage_metadata table already exists")
            return

        # Import the model to ensure it's registered with SQLAlchemy
        from vault.database.schema import ExternalStorageMetadata

        # Create the table using the model's table definition
        try:
            ExternalStorageMetadata.__table__.create(bind=db.engine, checkfirst=True)
            logger.info("external_storage_metadata table created successfully")
        except Exception as e:
            logger.error(f"Failed to create external_storage_metadata table: {e}")
            raise
