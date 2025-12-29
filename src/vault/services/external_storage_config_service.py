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
        """Retrieve S3 configuration, prioritizing environment variables.

        Args:
            secret_key: SECRET_KEY for decryption of DB-stored values
            app: Flask app instance for database access

        Returns:
            Configuration dictionary, or None if not found
        """
        # 1. Start with environment variables if available
        vault_settings = app.config.get("VAULT_SETTINGS")
        s3_env = vault_settings.s3_config if vault_settings else None

        config = {
            "storage_mode": "local",
            "endpoint_url": None,
            "access_key_id": "",
            "secret_access_key": "",
            "bucket_name": "",
            "region": "us-east-1",
            "use_ssl": True,
        }

        if s3_env:
            config.update(
                {
                    "endpoint_url": s3_env.endpoint_url,
                    "access_key_id": s3_env.access_key_id,
                    "secret_access_key": s3_env.secret_access_key,
                    "bucket_name": s3_env.bucket_name,
                    "region": s3_env.region,
                    "use_ssl": s3_env.use_ssl,
                }
            )

        # 2. Retrieve from database for storage_mode and enabled flag
        cipher = ExternalStorageConfigService._get_fernet_cipher(secret_key)

        with app.app_context():
            try:
                secret = (
                    db.session.query(SystemSecrets)
                    .filter_by(key=ExternalStorageConfigService.SECRET_KEY)
                    .first()
                )
            except Exception:
                # Table or column doesn't exist yet - this is OK during init
                return config if s3_env else None

            if secret:
                try:
                    decrypted_json = cipher.decrypt(
                        secret.encrypted_value.encode()
                    ).decode()
                    db_config = json.loads(decrypted_json)
                    config["storage_mode"] = db_config.get("storage_mode", "local")
                except Exception:
                    # Log error but keep environment values
                    import logging

                    logging.getLogger(__name__).error("Failed to decrypt DB S3 config")

        if not s3_env and not secret:
            return None

        return config

    @staticmethod
    def store_config(secret_key: str, config: dict[str, Any], app: Any) -> None:
        """Store only storage_mode in SystemSecrets.

        S3 credentials and bucket info are managed via environment variables.

        Args:
            secret_key: SECRET_KEY for encryption
            config: Configuration dictionary (only storage_mode will be stored)
            app: Flask app instance for database access
        """
        # Filter config to only store storage_mode
        db_config = {
            "storage_mode": config.get("storage_mode", "local"),
        }

        cipher = ExternalStorageConfigService._get_fernet_cipher(secret_key)
        config_json = json.dumps(db_config)
        encrypted_config = cipher.encrypt(config_json.encode()).decode()

        with app.app_context():
            # Check if secret already exists
            try:
                existing = (
                    db.session.query(SystemSecrets)
                    .filter_by(key=ExternalStorageConfigService.SECRET_KEY)
                    .first()
                )
            except Exception as db_error:
                # Handle case where table doesn't exist or has wrong structure
                import logging

                logging.getLogger(__name__)
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
    def sync_on_startup(secret_key: str, app: Any) -> None:
        """Synchronize S3 configuration on startup.

        Ensures that if S3 environment variables are provided, they take precedence
        and only non-sensitive flags are kept in the database.
        """
        vault_settings = app.config.get("VAULT_SETTINGS")
        s3_env = vault_settings.s3_config if vault_settings else None

        if not s3_env:
            return

        # (only contains enabled and storage_mode)
        current_config = ExternalStorageConfigService.get_config(secret_key, app)
        if current_config:
            # Re-store it to ensure only allowed fields are in DB
            ExternalStorageConfigService.store_config(secret_key, current_config, app)

    @staticmethod
    def is_enabled(secret_key: str, app: Any) -> bool:
        """Check if external storage S3 is enabled based on storage mode.

        Args:
            secret_key: SECRET_KEY for decryption
            app: Flask app instance for database access

        Returns:
            True if storage mode is 's3' or 'hybrid', False otherwise
        """
        config = ExternalStorageConfigService.get_config(secret_key, app)
        if not config:
            return False
        return config.get("storage_mode") in ["s3", "hybrid"]

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
