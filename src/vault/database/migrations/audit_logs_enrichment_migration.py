"""Migration to add ipv4, ip_location, and user_id columns to audit_logs table."""

from __future__ import annotations

import logging
import time

from sqlalchemy.exc import InternalError, ProgrammingError

from vault.database.migrations.base import Migration

logger = logging.getLogger(__name__)


class AuditLogsEnrichmentMigration(Migration):
    """Migration to add enrichment columns to audit_logs table.

    This migration adds:
    - ipv4: IPv4 address extracted from request headers or converted from IPv6
    - ip_location: JSON string with geolocation data (country, city, etc.)
    - user_id: Foreign key to users table for authentication-related logs
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "audit_logs_enrichment"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if any of the new columns are missing, False otherwise
        """
        if not self.table_exists("audit_logs"):
            return False

        if not self.column_exists("audit_logs", "ipv4"):
            return True

        if not self.column_exists("audit_logs", "ip_location"):
            return True

        if not self.column_exists("audit_logs", "user_id"):
            return True

        # Check if index exists
        if not self.index_exists("audit_logs", "ix_audit_logs_user_id"):
            return True

        return False

    def apply(self) -> None:
        """Apply the migration.

        Adds the ipv4, ip_location, and user_id columns and creates the index if missing.
        """
        if not self.table_exists("audit_logs"):
            raise RuntimeError("audit_logs table does not exist")

        # Add ipv4 column if it doesn't exist
        if not self.column_exists("audit_logs", "ipv4"):
            logger.info("Adding ipv4 column to audit_logs table")
            try:
                self.execute_sql("ALTER TABLE audit_logs ADD COLUMN ipv4 VARCHAR(15)")
                logger.info("ipv4 column added successfully")
            except (ProgrammingError, InternalError) as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug("ipv4 column already exists (concurrent creation)")
                    time.sleep(0.2)
                    if not self.column_exists("audit_logs", "ipv4"):
                        raise RuntimeError(
                            "Database reported ipv4 column exists but verification failed"
                        )
                else:
                    raise
            time.sleep(0.2)

        # Add ip_location column if it doesn't exist
        if not self.column_exists("audit_logs", "ip_location"):
            logger.info("Adding ip_location column to audit_logs table")
            try:
                self.execute_sql("ALTER TABLE audit_logs ADD COLUMN ip_location TEXT")
                logger.info("ip_location column added successfully")
            except (ProgrammingError, InternalError) as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug(
                        "ip_location column already exists (concurrent creation)"
                    )
                    time.sleep(0.2)
                    if not self.column_exists("audit_logs", "ip_location"):
                        raise RuntimeError(
                            "Database reported ip_location column exists but verification failed"
                        )
                else:
                    raise
            time.sleep(0.2)

        # Add user_id column if it doesn't exist
        if not self.column_exists("audit_logs", "user_id"):
            logger.info("Adding user_id column to audit_logs table")
            try:
                self.execute_sql("ALTER TABLE audit_logs ADD COLUMN user_id UUID")
                logger.info("user_id column added successfully")
            except (ProgrammingError, InternalError) as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug("user_id column already exists (concurrent creation)")
                    time.sleep(0.2)
                    if not self.column_exists("audit_logs", "user_id"):
                        raise RuntimeError(
                            "Database reported user_id column exists but verification failed"
                        )
                else:
                    raise
            time.sleep(0.2)

        # Add foreign key constraint if it doesn't exist
        try:
            # Check if foreign key exists by querying constraints
            inspector = self._get_inspector()
            if inspector:
                fk_constraints = inspector.get_foreign_keys("audit_logs")
                fk_exists = any(
                    fk["constrained_columns"] == ["user_id"]
                    and fk["referred_table"] == "users"
                    for fk in fk_constraints
                )
                if not fk_exists:
                    logger.info("Adding foreign key constraint on user_id column")
                    self.execute_sql_safe(
                        "ALTER TABLE audit_logs "
                        "ADD CONSTRAINT fk_audit_logs_user_id "
                        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"
                    )
        except Exception as e:
            logger.debug(f"Foreign key constraint may already exist: {e}")

        # Create index if it doesn't exist
        if not self.index_exists("audit_logs", "ix_audit_logs_user_id"):
            logger.info("Creating index on user_id column")
            self.execute_sql_safe(
                "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)"
            )

        logger.info("audit_logs enrichment migration completed successfully")

    def _get_inspector(self):
        """Get SQLAlchemy inspector for database inspection."""
        try:
            from sqlalchemy import inspect as sql_inspect
            from vault.database.schema import db

            return sql_inspect(db.engine)
        except Exception:
            return None
