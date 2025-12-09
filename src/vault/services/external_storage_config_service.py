"""Service for managing external storage S3 configuration with encryption."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from vault.database.schema import SystemSecrets, db


class ExternalStorageConfigService:
    """Service for managing external storage S3 configuration."""

    # Secret key in SystemSecrets
    SECRET_KEY = "external_storage_s3_config"

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
            salt=b"leyzen-vault-external-storage-v1",
            iterations=100000,
            backend=default_backend(),
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return Fernet(fernet_key)

    @staticmethod
    def get_config(secret_key: str, app: Any) -> dict[str, Any] | None:
        """Retrieve and decrypt S3 configuration from SystemSecrets.

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            Configuration dictionary, or None if not found
        """
        cipher = ExternalStorageConfigService._get_fernet_cipher(secret_key)

        with app.app_context():
            secret = (
                db.session.query(SystemSecrets)
                .filter_by(key=ExternalStorageConfigService.SECRET_KEY)
                .first()
            )

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
                logger.error(f"Failed to decrypt S3 configuration: {e}")
                return None

    @staticmethod
    def store_config(secret_key: str, config: dict[str, Any], app: Any) -> None:
        """Store encrypted S3 configuration in SystemSecrets.

        Args:
            secret_key: SECRET_KEY for encryption
            config: Configuration dictionary to encrypt and store
            app: Flask app instance for database access
        """
        cipher = ExternalStorageConfigService._get_fernet_cipher(secret_key)
        config_json = json.dumps(config)
        encrypted_config = cipher.encrypt(config_json.encode()).decode()

        with app.app_context():
            # Check if secret already exists
            existing = (
                db.session.query(SystemSecrets)
                .filter_by(key=ExternalStorageConfigService.SECRET_KEY)
                .first()
            )

            if existing:
                # Update existing secret
                existing.encrypted_value = encrypted_config
            else:
                # Create new secret
                new_secret = SystemSecrets(
                    key=ExternalStorageConfigService.SECRET_KEY,
                    encrypted_value=encrypted_config,
                )
                db.session.add(new_secret)

            db.session.commit()

    @staticmethod
    def delete_config(app: Any) -> None:
        """Delete S3 configuration from SystemSecrets.

        Args:
            app: Flask app instance for database access
        """
        with app.app_context():
            secret = (
                db.session.query(SystemSecrets)
                .filter_by(key=ExternalStorageConfigService.SECRET_KEY)
                .first()
            )

            if secret:
                db.session.delete(secret)
                db.session.commit()

    @staticmethod
    def is_enabled(secret_key: str, app: Any) -> bool:
        """Check if external storage S3 is enabled.

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            True if enabled, False otherwise
        """
        config = ExternalStorageConfigService.get_config(secret_key, app)
        if not config:
            return False
        return config.get("enabled", False)

    @staticmethod
    def get_storage_mode(secret_key: str, app: Any) -> str:
        """Get storage mode (local, s3, or hybrid).

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            Storage mode string, defaults to "local" if not configured
        """
        config = ExternalStorageConfigService.get_config(secret_key, app)
        if not config:
            return "local"
        return config.get("storage_mode", "local")


__all__ = ["ExternalStorageConfigService"]
