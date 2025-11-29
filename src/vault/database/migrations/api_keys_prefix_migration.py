"""Migration to ensure api_keys.key_prefix column has sufficient length."""

from __future__ import annotations

import logging

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class ApiKeysPrefixMigration(Migration):
    """Migration to ensure api_keys.key_prefix column can store full prefixes.

    This migration ensures the key_prefix column has a length of at least 64
    characters to accommodate full API key prefixes (e.g., "leyz_<base64>").
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "api_keys_prefix_length"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if key_prefix column needs to be resized, False otherwise
        """
        if not self.table_exists("api_keys"):
            return False

        if not self.column_exists("api_keys", "key_prefix"):
            return False

        column_type = self.get_column_type("api_keys", "key_prefix")
        if not column_type:
            return False

        current_length = column_type.length if hasattr(column_type, "length") else None

        desired_length = 64

        if current_length is not None and current_length < desired_length:
            return True

        return False

    def apply(self) -> None:
        """Apply the migration.

        Resizes the key_prefix column to 64 characters if it's currently smaller.
        """
        desired_length = 64

        column_type = self.get_column_type("api_keys", "key_prefix")
        if not column_type:
            raise RuntimeError("key_prefix column not found in api_keys table")

        current_length = column_type.length if hasattr(column_type, "length") else None

        if current_length is None:
            raise RuntimeError("Cannot determine current length of key_prefix column")

        if current_length >= desired_length:
            logger.debug(
                f"key_prefix column already has sufficient length ({current_length})"
            )
            return

        sql = f"ALTER TABLE api_keys ALTER COLUMN key_prefix TYPE VARCHAR({desired_length})"
        self.execute_sql(sql)

        logger.info(
            f"api_keys.key_prefix length increased from {current_length} to {desired_length}"
        )
