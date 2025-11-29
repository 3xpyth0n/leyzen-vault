"""Database migration system for Leyzen Vault.

This module provides a uniform, declarative migration system that works
identically on fresh and existing databases.
"""

from vault.database.migrations.base import Migration
from vault.database.migrations.registry import MigrationRegistry, run_migrations

__all__ = [
    "Migration",
    "MigrationRegistry",
    "run_migrations",
]
