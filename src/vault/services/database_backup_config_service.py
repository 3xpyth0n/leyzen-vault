"""Service for managing database backup configuration with encryption."""

from __future__ import annotations

import json
from typing import Any

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from vault.database.schema import SystemSecrets
from vault.database import db


class DatabaseBackupConfigService:
    """Service for managing database backup configuration."""

    # Secret key in SystemSecrets
    SECRET_KEY = "database_backup_config"

    @staticmethod
    def _get_fernet_cipher(secret_key: str) -> Fernet:
        """Get Fernet cipher for encryption/decryption.

        Args:
            secret_key: SECRET_KEY for deriving the Fernet key

        Returns:
            Fernet cipher instance
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"leyzen-vault-database-backup-v1",
            iterations=100000,
            backend=default_backend(),
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return Fernet(fernet_key)

    @staticmethod
    def get_config(secret_key: str, app: Any) -> dict[str, Any] | None:
        """Retrieve and decrypt database backup configuration from SystemSecrets.

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            Configuration dictionary, or None if not found
        """
        cipher = DatabaseBackupConfigService._get_fernet_cipher(secret_key)

        with app.app_context():
            try:
                secret = (
                    db.session.query(SystemSecrets)
                    .filter_by(key=DatabaseBackupConfigService.SECRET_KEY)
                    .first()
                )
            except Exception as db_error:
                # Handle case where table doesn't exist or has wrong structure
                # This can happen during initial database setup
                import logging

                logger = logging.getLogger(__name__)
                error_str = str(db_error)
                if "does not exist" in error_str or "UndefinedColumn" in error_str:
                    # Table or column doesn't exist yet - this is OK during init
                    logger.debug(f"system_secrets table not ready yet: {db_error}")
                else:
                    logger.warning(f"Error querying system_secrets: {db_error}")
                return None

            if not secret:
                return None

            try:
                decrypted_json = cipher.decrypt(
                    secret.encrypted_value.encode()
                ).decode()
                return json.loads(decrypted_json)
            except Exception as e:
                # Log error but return None
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to decrypt database backup configuration: {e}")
                return None

    @staticmethod
    def store_config(secret_key: str, config: dict[str, Any], app: Any) -> None:
        """Store encrypted database backup configuration in SystemSecrets.

        Args:
            secret_key: SECRET_KEY for encryption
            config: Configuration dictionary to encrypt and store
            app: Flask app instance for database access
        """
        cipher = DatabaseBackupConfigService._get_fernet_cipher(secret_key)
        config_json = json.dumps(config)
        encrypted_config = cipher.encrypt(config_json.encode()).decode()

        with app.app_context():
            # Check if secret already exists
            try:
                existing = (
                    db.session.query(SystemSecrets)
                    .filter_by(key=DatabaseBackupConfigService.SECRET_KEY)
                    .first()
                )
            except Exception as db_error:
                # Handle case where table doesn't exist or has wrong structure
                import logging

                logger = logging.getLogger(__name__)
                error_str = str(db_error)
                if "does not exist" in error_str or "UndefinedColumn" in error_str:
                    # Table or column doesn't exist yet - raise error as this should not happen during normal operation
                    raise RuntimeError(
                        "system_secrets table not ready. Database must be initialized first."
                    ) from db_error
                else:
                    raise

            if existing:
                # Update existing secret
                existing.encrypted_value = encrypted_config
            else:
                # Create new secret
                new_secret = SystemSecrets(
                    key=DatabaseBackupConfigService.SECRET_KEY,
                    encrypted_value=encrypted_config,
                )
                db.session.add(new_secret)

            db.session.commit()

    @staticmethod
    def delete_config(app: Any) -> None:
        """Delete database backup configuration from SystemSecrets.

        Args:
            app: Flask app instance for database access
        """
        with app.app_context():
            secret = (
                db.session.query(SystemSecrets)
                .filter_by(key=DatabaseBackupConfigService.SECRET_KEY)
                .first()
            )

            if secret:
                db.session.delete(secret)
                db.session.commit()

    @staticmethod
    def is_enabled(secret_key: str, app: Any) -> bool:
        """Check if database backup is enabled.

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            True if enabled, False otherwise
        """
        config = DatabaseBackupConfigService.get_config(secret_key, app)
        if not config:
            return False
        return config.get("enabled", False)


__all__ = ["DatabaseBackupConfigService"]
