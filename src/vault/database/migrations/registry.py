"""Migration registry and execution system."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from vault.database.migrations.base import Migration
from vault.database.schema import SchemaMigration, db

logger = logging.getLogger(__name__)


class MigrationRegistry:
    """Registry for database migrations."""

    def __init__(self) -> None:
        """Initialize the migration registry."""
        self._migrations: list[type[Migration]] = []

    def register(self, migration_class: type[Migration]) -> None:
        """Register a migration class.

        Args:
            migration_class: Migration class to register
        """
        self._migrations.append(migration_class)

    def get_all_migrations(self) -> list[Migration]:
        """Get all registered migration instances.

        Returns:
            List of migration instances
        """
        return [migration_class() for migration_class in self._migrations]

    def is_migration_applied(self, migration_name: str, version: str) -> bool:
        """Check if a migration has been applied.

        Args:
            migration_name: Name of the migration
            version: Version of the migration

        Returns:
            True if migration is applied with this or a newer version, False otherwise
        """
        try:
            migration = (
                db.session.query(SchemaMigration)
                .filter_by(migration_name=migration_name)
                .first()
            )
            if migration:
                # Migration exists - check if version matches or is newer
                # For simplicity, if migration exists, consider it applied
                return True
            return False
        except Exception as e:
            logger.debug(f"Error checking if migration is applied: {e}")
            return False

    def mark_migration_applied(self, migration_name: str, version: str) -> None:
        """Mark a migration as applied.

        Args:
            migration_name: Name of the migration
            version: Version of the migration
        """
        try:
            existing = (
                db.session.query(SchemaMigration)
                .filter_by(migration_name=migration_name)
                .first()
            )
            if existing:
                # Update version if it changed
                if existing.version != version:
                    existing.version = version
                    existing.applied_at = datetime.now(timezone.utc)
                    db.session.commit()
            else:
                migration_record = SchemaMigration(
                    migration_name=migration_name, version=version
                )
                db.session.add(migration_record)
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to mark migration as applied: {e}")
            db.session.rollback()
            raise

    def should_apply_migration(self, migration: Migration) -> bool:
        """Determine if a migration should be applied.

        Checks both the migration's internal state check and the registry.

        Args:
            migration: Migration instance to check

        Returns:
            True if migration should be applied, False otherwise
        """
        # First check if migration is already recorded as applied
        if self.is_migration_applied(migration.name, migration.version):
            return False

        # Then check migration's internal state
        return migration.needs_application()


def run_migrations(app_logger: Any | None = None) -> None:
    """Run all registered migrations.

    This function will:
    1. Get all registered migrations
    2. Check if each needs to be applied
    3. Apply migrations that need it
    4. Record applied migrations

    Args:
        app_logger: Optional application logger to use for logging
    """
    # Import migrations here to avoid circular dependencies
    from vault.database.migrations.api_keys_prefix_migration import (
        ApiKeysPrefixMigration,
    )
    from vault.database.migrations.audit_logs_enrichment_migration import (
        AuditLogsEnrichmentMigration,
    )
    from vault.database.migrations.jwt_jti_migration import JwtJtiMigration
    from vault.database.migrations.pinned_vaultspaces_migration import (
        PinnedVaultSpacesMigration,
    )
    from vault.database.migrations.session_key_salt_migration import (
        SessionKeySaltMigration,
    )

    registry = MigrationRegistry()

    # Register all migrations in order
    registry.register(ApiKeysPrefixMigration)
    registry.register(JwtJtiMigration)
    registry.register(PinnedVaultSpacesMigration)
    registry.register(AuditLogsEnrichmentMigration)
    registry.register(SessionKeySaltMigration)

    migrations = registry.get_all_migrations()

    log_msg = f"[MIGRATIONS] Found {len(migrations)} registered migrations"
    if app_logger:
        app_logger.log(log_msg)
    else:
        logger.info(log_msg)

    for migration in migrations:
        try:
            if registry.should_apply_migration(migration):
                log_msg = f"[MIGRATIONS] Applying migration: {migration.name} (v{migration.version})"
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.info(log_msg)

                migration.apply()

                registry.mark_migration_applied(migration.name, migration.version)

                log_msg = (
                    f"[MIGRATIONS] Successfully applied migration: {migration.name}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.info(log_msg)
            else:
                log_msg = f"[MIGRATIONS] Migration {migration.name} (v{migration.version}) already applied or not needed"
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.debug(log_msg)
        except Exception as e:
            log_msg = (
                f"[MIGRATIONS] ERROR: Failed to apply migration {migration.name}: {e}"
            )
            if app_logger:
                app_logger.log(log_msg)
            else:
                logger.error(log_msg)
            raise
