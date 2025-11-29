"""Base classes and utilities for database migrations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import inspect as sql_inspect
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.sql import text as sql_text

from vault.database.schema import db

logger = logging.getLogger(__name__)


class Migration(ABC):
    """Abstract base class for database migrations.

    All migrations should inherit from this class and implement:
    - name: A unique identifier for the migration
    - version: A version string (can be used for migrations that need updating)
    - apply(): The migration logic (must be idempotent)
    - needs_application(): Check if migration needs to be applied
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this migration."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string for this migration (used for version tracking)."""
        pass

    @abstractmethod
    def needs_application(self) -> bool:
        """Check if this migration needs to be applied.

        This method should check the current database state and return True
        if the migration needs to be applied. Must be idempotent.

        Returns:
            True if migration needs to be applied, False otherwise
        """
        pass

    @abstractmethod
    def apply(self) -> None:
        """Apply the migration.

        This method should contain the actual migration logic.
        It must be idempotent - safe to call multiple times.

        Raises:
            Exception: If migration fails
        """
        pass

    def revert(self) -> None:
        """Revert the migration (optional).

        Default implementation does nothing. Override if rollback is needed.

        Raises:
            NotImplementedError: If revert is not supported
        """
        raise NotImplementedError(f"Revert not supported for migration {self.name}")

    def execute_sql(self, sql: str, params: dict[str, Any] | None = None) -> None:
        """Execute a SQL statement safely.

        Args:
            sql: SQL statement to execute
            params: Optional parameters for the SQL statement

        Raises:
            Exception: If SQL execution fails
        """
        if params:
            db.session.execute(sql_text(sql), params)
        else:
            db.session.execute(sql_text(sql))
        db.session.commit()

    def execute_sql_safe(self, sql: str, params: dict[str, Any] | None = None) -> bool:
        """Execute a SQL statement safely, returning success status.

        Args:
            sql: SQL statement to execute
            params: Optional parameters for the SQL statement

        Returns:
            True if executed successfully, False otherwise
        """
        try:
            self.execute_sql(sql, params)
            return True
        except Exception as e:
            logger.debug(f"SQL execution failed (non-fatal): {e}")
            db.session.rollback()
            return False

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        try:
            inspector = sql_inspect(db.engine)
            return table_name in inspector.get_table_names()
        except Exception as e:
            logger.debug(f"Error checking table existence: {e}")
            return False

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table.

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            True if column exists, False otherwise
        """
        try:
            inspector = sql_inspect(db.engine)
            if not self.table_exists(table_name):
                return False
            columns = [col["name"] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except Exception as e:
            logger.debug(f"Error checking column existence: {e}")
            return False

    def get_column_type(self, table_name: str, column_name: str) -> Any:
        """Get the type information for a column.

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            Column type object, or None if column doesn't exist
        """
        try:
            inspector = sql_inspect(db.engine)
            if not self.table_exists(table_name):
                return None
            columns = inspector.get_columns(table_name)
            column = next((col for col in columns if col["name"] == column_name), None)
            return column["type"] if column else None
        except Exception as e:
            logger.debug(f"Error getting column type: {e}")
            return None

    def index_exists(self, table_name: str, index_name: str) -> bool:
        """Check if an index exists in the database.

        Args:
            table_name: Name of the table
            index_name: Name of the index to check

        Returns:
            True if index exists, False otherwise
        """
        try:
            inspector = sql_inspect(db.engine)
            if not self.table_exists(table_name):
                return False
            indexes = inspector.get_indexes(table_name)
            return any(idx["name"] == index_name for idx in indexes)
        except Exception as e:
            logger.debug(f"Error checking index existence: {e}")
            return False
