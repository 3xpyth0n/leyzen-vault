"""Migration to add session_key_salt column to users table."""

from __future__ import annotations

import base64
import logging
import secrets
import time

from sqlalchemy.exc import InternalError, ProgrammingError

from vault.database.migrations.base import Migration
from vault.database.schema import User, db

logger = logging.getLogger(__name__)


class SessionKeySaltMigration(Migration):
    """Migration to add session_key_salt column to users table.

    This migration adds the session_key_salt column for secure session key derivation.
    The salt is used instead of user_id to prevent predictable key derivation.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this migration."""
        return "users_session_key_salt_column"

    @property
    def version(self) -> str:
        """Version string for this migration."""
        return "1.0"

    def needs_application(self) -> bool:
        """Check if migration needs to be applied.

        Returns:
            True if session_key_salt column is missing or users need salts, False otherwise
        """
        if not self.table_exists("users"):
            return False

        # Check if column exists
        if not self.column_exists("users", "session_key_salt"):
            return True

        # Check if any users are missing session_key_salt
        try:
            users_without_salt = (
                db.session.query(User).filter(User.session_key_salt.is_(None)).count()
            )
            return users_without_salt > 0
        except Exception as e:
            logger.debug(f"Error checking users without salt: {e}")

            return True

    def apply(self) -> None:
        """Apply the migration.

        Adds the session_key_salt column and generates salts for all existing users.
        """
        if not self.table_exists("users"):
            raise RuntimeError("users table does not exist")

        # Add session_key_salt column if it doesn't exist
        if not self.column_exists("users", "session_key_salt"):
            logger.info(
                "Adding session_key_salt column to users table for secure session key derivation"
            )

            try:
                self.execute_sql("ALTER TABLE users ADD COLUMN session_key_salt TEXT")
                logger.info("session_key_salt column added successfully")
            except (ProgrammingError, InternalError) as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    logger.debug(
                        "session_key_salt column already exists (concurrent creation)"
                    )
                    # Verify it exists now
                    time.sleep(0.2)
                    if not self.column_exists("users", "session_key_salt"):
                        raise RuntimeError(
                            "Database reported session_key_salt column exists but verification failed"
                        )
                else:
                    raise

            # Verify column was created
            time.sleep(0.2)
            if not self.column_exists("users", "session_key_salt"):
                raise RuntimeError(
                    "Failed to verify session_key_salt column creation after adding it"
                )

        # Generate salts for all users without one
        try:
            users_without_salt = (
                db.session.query(User).filter(User.session_key_salt.is_(None)).all()
            )

            if users_without_salt:
                logger.info(
                    f"Generating session_key_salt for {len(users_without_salt)} users"
                )

                for user in users_without_salt:
                    # Generate 32 bytes of random salt
                    salt_bytes = secrets.token_bytes(32)
                    # Encode to base64
                    salt_base64 = base64.b64encode(salt_bytes).decode("utf-8")
                    user.session_key_salt = salt_base64

                db.session.commit()
                logger.info(
                    f"Successfully generated session_key_salt for {len(users_without_salt)} users"
                )
            else:
                logger.debug("All users already have session_key_salt")
        except Exception as e:
            logger.error(f"Failed to generate session_key_salt for users: {e}")
            db.session.rollback()
            raise

        logger.info("users session_key_salt migration completed successfully")
