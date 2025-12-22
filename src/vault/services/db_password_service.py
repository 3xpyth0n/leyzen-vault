"""Service for managing PostgreSQL role passwords with encryption and rotation."""

from __future__ import annotations

import secrets
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from vault.database.schema import SystemSecrets, db


class DBPasswordService:
    """Service for managing PostgreSQL role passwords."""

    # Role names (hardcoded)
    ROLE_APP = "leyzen_app"
    ROLE_MIGRATOR = "leyzen_migrator"
    ROLE_SECRETS = "leyzen_secrets"
    ROLE_ORCHESTRATOR = "leyzen_orchestrator"

    # Secret keys in SystemSecrets
    SECRET_KEY_APP = "postgres_app_password"
    SECRET_KEY_MIGRATOR = "postgres_migrator_password"
    SECRET_KEY_SECRETS = "postgres_secrets_password"
    SECRET_KEY_ORCHESTRATOR = "postgres_orchestrator_password"

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
            salt=b"leyzen-vault-db-password-v1",
            iterations=100000,
            backend=default_backend(),
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return Fernet(fernet_key)

    @staticmethod
    def generate_password() -> str:
        """Generate a random secure password for a PostgreSQL role.

        Returns:
            Random password string (URL-safe base64, 32 bytes = 256 bits)
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def store_password(
        secret_key: str,
        password_key: str,
        password: str,
        app: Any,
        use_admin_connection: bool = False,
    ) -> None:
        """Store an encrypted password in SystemSecrets.

        Args:
            secret_key: SECRET_KEY for encryption
            password_key: Key name in SystemSecrets (e.g., "postgres_app_password")
            password: Password to encrypt and store
            app: Flask app instance for database access
            use_admin_connection: If True, use admin connection instead of db.session
        """
        cipher = DBPasswordService._get_fernet_cipher(secret_key)
        encrypted_password = cipher.encrypt(password.encode()).decode()

        if use_admin_connection:
            # Use admin connection directly (for init_db_roles)
            from sqlalchemy import create_engine, text
            from common.env import load_env_with_override
            import os

            env_values = load_env_with_override()
            env_values.update(dict(os.environ))

            postgres_host = env_values.get("POSTGRES_HOST", "postgres")
            postgres_port = env_values.get("POSTGRES_PORT", "5432")
            postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
            postgres_user = env_values.get("POSTGRES_USER", "leyzen")
            postgres_password = env_values.get("POSTGRES_PASSWORD", "")

            if not postgres_password:
                raise RuntimeError("POSTGRES_PASSWORD is required")

            postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
            engine = create_engine(postgres_url, pool_pre_ping=True)

            try:
                # Use engine.begin() for automatic transaction management
                # This ensures the operation is committed correctly in SQLAlchemy 2.0
                with engine.begin() as conn:
                    # Check if key already exists
                    result = conn.execute(
                        text("SELECT id FROM system_secrets WHERE key = :key"),
                        {"key": password_key},
                    )
                    existing = result.fetchone()

                    if existing:
                        # Update existing record
                        conn.execute(
                            text(
                                """
                                UPDATE system_secrets
                                SET encrypted_value = :encrypted_value, updated_at = NOW()
                                WHERE key = :key
                                """
                            ),
                            {
                                "key": password_key,
                                "encrypted_value": encrypted_password,
                            },
                        )
                    else:
                        # Insert new record
                        conn.execute(
                            text(
                                """
                                INSERT INTO system_secrets (key, encrypted_value)
                                VALUES (:key, :encrypted_value)
                                """
                            ),
                            {
                                "key": password_key,
                                "encrypted_value": encrypted_password,
                            },
                        )
            finally:
                engine.dispose()
        else:
            # Use db.session (for normal operations with leyzen_secrets role)
            with app.app_context():
                # Check if secret already exists
                existing = (
                    db.session.query(SystemSecrets).filter_by(key=password_key).first()
                )

                if existing:
                    # Update existing secret
                    existing.encrypted_value = encrypted_password
                else:
                    # Create new secret
                    new_secret = SystemSecrets(
                        key=password_key, encrypted_value=encrypted_password
                    )
                    db.session.add(new_secret)

                db.session.commit()

    @staticmethod
    def get_password(
        secret_key: str, password_key: str, app: Any, use_admin_connection: bool = False
    ) -> str | None:
        """Retrieve and decrypt a password from SystemSecrets.

        Args:
            secret_key: SECRET_KEY for decryption
            password_key: Key name in SystemSecrets (e.g., "postgres_app_password")
            app: Flask app instance for database access
            use_admin_connection: If True, use admin connection instead of db.session

        Returns:
            Decrypted password string, or None if not found
        """
        cipher = DBPasswordService._get_fernet_cipher(secret_key)

        if use_admin_connection:
            # Use admin connection directly (for init_db_roles)
            from sqlalchemy import create_engine, text
            from common.env import load_env_with_override
            import os

            env_values = load_env_with_override()
            env_values.update(dict(os.environ))

            postgres_host = env_values.get("POSTGRES_HOST", "postgres")
            postgres_port = env_values.get("POSTGRES_PORT", "5432")
            postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
            postgres_user = env_values.get("POSTGRES_USER", "leyzen")
            postgres_password = env_values.get("POSTGRES_PASSWORD", "")

            if not postgres_password:
                return None

            postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
            engine = create_engine(postgres_url, pool_pre_ping=True)

            try:
                with engine.connect() as conn:
                    result = conn.execute(
                        text(
                            "SELECT encrypted_value FROM system_secrets WHERE key = :key"
                        ),
                        {"key": password_key},
                    )
                    row = result.fetchone()
                    if not row:
                        return None

                    try:
                        decrypted_password = cipher.decrypt(row[0].encode()).decode()
                        return decrypted_password
                    except Exception:
                        # Decryption failed - password may be corrupted
                        return None
            finally:
                engine.dispose()
        else:
            # Use db.session (for normal operations)
            with app.app_context():
                secret_record = (
                    db.session.query(SystemSecrets).filter_by(key=password_key).first()
                )

                if not secret_record:
                    return None

                try:
                    decrypted_password = cipher.decrypt(
                        secret_record.encrypted_value.encode()
                    ).decode()
                    return decrypted_password
                except Exception:
                    # Decryption failed - password may be corrupted
                    return None

    @staticmethod
    def rotate_all_passwords(secret_key: str, app: Any) -> dict[str, str]:
        """Generate new passwords for all roles and update them in PostgreSQL and SystemSecrets.

        Args:
            secret_key: SECRET_KEY for encryption
            app: Flask app instance for database access

        Returns:
            Dictionary mapping role names to new passwords
        """
        from sqlalchemy import create_engine, text
        from common.env import load_env_with_override

        # Generate new passwords
        new_passwords = {
            DBPasswordService.ROLE_APP: DBPasswordService.generate_password(),
            DBPasswordService.ROLE_MIGRATOR: DBPasswordService.generate_password(),
            DBPasswordService.ROLE_SECRETS: DBPasswordService.generate_password(),
            DBPasswordService.ROLE_ORCHESTRATOR: DBPasswordService.generate_password(),
        }

        # Get PostgreSQL connection info
        env_values = load_env_with_override()
        env_values.update(dict(__import__("os").environ))

        postgres_host = env_values.get("POSTGRES_HOST", "postgres")
        postgres_port = env_values.get("POSTGRES_PORT", "5432")
        postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
        postgres_user = env_values.get("POSTGRES_USER", "leyzen")
        postgres_password = env_values.get("POSTGRES_PASSWORD", "")

        if not postgres_password:
            raise RuntimeError("POSTGRES_PASSWORD is required for password rotation")

        # Connect to PostgreSQL as the main user to update role passwords
        postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        engine = create_engine(postgres_url, pool_pre_ping=True)

        try:
            # Use engine.begin() for automatic transaction management
            # This ensures all operations are committed correctly in SQLAlchemy 2.0
            with engine.begin() as conn:
                # Update passwords in PostgreSQL
                for role_name, new_password in new_passwords.items():
                    # Escape password for SQL (use parameterized query)
                    conn.execute(
                        text(f'ALTER ROLE "{role_name}" WITH PASSWORD :password'),
                        {"password": new_password},
                    )

                # Update passwords in SystemSecrets
                # Use main user role to update SystemSecrets during rotation
                # (This is an administrative operation, so using main user is acceptable)
                for password_key, new_password in [
                    (
                        DBPasswordService.SECRET_KEY_APP,
                        new_passwords[DBPasswordService.ROLE_APP],
                    ),
                    (
                        DBPasswordService.SECRET_KEY_MIGRATOR,
                        new_passwords[DBPasswordService.ROLE_MIGRATOR],
                    ),
                    (
                        DBPasswordService.SECRET_KEY_SECRETS,
                        new_passwords[DBPasswordService.ROLE_SECRETS],
                    ),
                    (
                        DBPasswordService.SECRET_KEY_ORCHESTRATOR,
                        new_passwords[DBPasswordService.ROLE_ORCHESTRATOR],
                    ),
                ]:
                    cipher = DBPasswordService._get_fernet_cipher(secret_key)
                    encrypted_password = cipher.encrypt(new_password.encode()).decode()

                    # Check if key already exists
                    result = conn.execute(
                        text("SELECT id FROM system_secrets WHERE key = :key"),
                        {"key": password_key},
                    )
                    existing = result.fetchone()

                    if existing:
                        # Update existing record
                        conn.execute(
                            text(
                                """
                                UPDATE system_secrets
                                SET encrypted_value = :encrypted_value, updated_at = NOW()
                                WHERE key = :key
                                """
                            ),
                            {
                                "key": password_key,
                                "encrypted_value": encrypted_password,
                            },
                        )
                    else:
                        # Insert new record
                        conn.execute(
                            text(
                                """
                                INSERT INTO system_secrets (key, encrypted_value)
                                VALUES (:key, :encrypted_value)
                                """
                            ),
                            {
                                "key": password_key,
                                "encrypted_value": encrypted_password,
                            },
                        )

        finally:
            engine.dispose()

        return new_passwords
