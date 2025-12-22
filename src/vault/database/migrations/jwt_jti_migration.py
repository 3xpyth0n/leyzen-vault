"""Migration to add jti column to jwt_blacklist table."""

from __future__ import annotations

import logging
import time

from sqlalchemy.exc import InternalError, ProgrammingError

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class JwtJtiMigration(Migration):
    """Migration to add jti column to jwt_blacklist table.

    This migration ensures the jwt_blacklist table has a jti (JWT ID) column
    for replay protection. The column is nullable for backward compatibility
    but has a unique index where jti IS NOT NULL.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "jwt_blacklist_jti_column"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if jti column is missing, False otherwise
        """
        if not self.table_exists("jwt_blacklist"):
            return False

        if not self.column_exists("jwt_blacklist", "jti"):
            return True

        # Check if index exists
        if not self.index_exists("jwt_blacklist", "ix_jwt_blacklist_jti"):
            return True

        return False

    def apply(self) -> None:
        """Apply the migration.

        Adds the jti column and creates the unique index if missing.
        """
        if not self.table_exists("jwt_blacklist"):
            raise RuntimeError("jwt_blacklist table does not exist")

        # Add jti column if it doesn't exist
        if not self.column_exists("jwt_blacklist", "jti"):
            logger.info(
                "Adding jti column to jwt_blacklist table for JWT replay protection"
            )

            try:
                self.execute_sql(
                    "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                )
                logger.info("jti column added successfully")
            except (ProgrammingError, InternalError) as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug("jti column already exists (concurrent creation)")
                    # Verify it exists now
                    time.sleep(0.2)
                    if not self.column_exists("jwt_blacklist", "jti"):
                        raise RuntimeError(
                            "Database reported jti column exists but verification failed"
                        )
                else:
                    raise

            # Verify column was created
            time.sleep(0.2)
            if not self.column_exists("jwt_blacklist", "jti"):
                raise RuntimeError(
                    "Failed to verify jti column creation after adding it"
                )

        # Create unique index if it doesn't exist
        if not self.index_exists("jwt_blacklist", "ix_jwt_blacklist_jti"):
            logger.info("Creating unique index on jti column")
            self.execute_sql_safe(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti "
                "ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
            )

        # Clear cache in auth_service if available
        self._reset_jti_column_cache()

        logger.info("jwt_blacklist jti migration completed successfully")

    def _reset_jti_column_cache(self) -> None:
        """Reset the jti column cache in auth_service if available."""
        try:
            from vault.services.auth_service import reset_jti_column_cache

            reset_jti_column_cache()
        except Exception:
            # Cache reset is optional, don't fail migration if it fails
            pass
