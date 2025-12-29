"""Service for database backup and restore operations."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sqlalchemy import text as sql_text

from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import argon2

from vault.config import get_postgres_url
from vault.database.schema import DatabaseBackup
from vault.database import db
from common.env import load_env_with_override

logger = logging.getLogger(__name__)

# Magic header to identify encrypted backups
ENCRYPTION_MAGIC_HEADER = b"LVBKENC"
ENCRYPTION_MAGIC_HEADER_LEN = len(ENCRYPTION_MAGIC_HEADER)
# Size threshold for choosing encryption method (100MB)
ENCRYPTION_SIZE_THRESHOLD = 100 * 1024 * 1024


class BackupEncryption:
    """Encryption utility for database backups using hybrid method (Fernet/AES-GCM)."""

    # Fixed salt for key derivation
    SALT = b"leyzen-vault-database-backup"
    # Argon2id parameters
    ARGON2_TIME_COST = 3
    ARGON2_MEMORY_COST = 65536  # 64MB
    ARGON2_PARALLELISM = 4
    ARGON2_HASH_LEN = 32

    def __init__(self, secret_key: str):
        """Initialize backup encryption with secret key.

        Args:
            secret_key: SECRET_KEY for deriving encryption key
        """
        self.secret_key = secret_key
        self._encryption_key = None
        self._fernet = None

    def _derive_key(self) -> bytes:
        """Derive encryption key from SECRET_KEY using Argon2id.

        Returns:
            32-byte encryption key
        """
        if self._encryption_key is None:
            # Use Argon2id to derive key from SECRET_KEY
            # This provides better security than PBKDF2
            # hash_secret_raw returns the raw hash bytes directly
            self._encryption_key = argon2.low_level.hash_secret_raw(
                secret=self.secret_key.encode("utf-8"),
                salt=self.SALT,
                time_cost=self.ARGON2_TIME_COST,
                memory_cost=self.ARGON2_MEMORY_COST,
                parallelism=self.ARGON2_PARALLELISM,
                hash_len=self.ARGON2_HASH_LEN,
                type=argon2.low_level.Type.ID,
            )

        return self._encryption_key

    def _get_fernet(self) -> Fernet:
        """Get Fernet cipher instance.

        Returns:
            Fernet cipher instance
        """
        if self._fernet is None:
            key = self._derive_key()
            # Fernet requires a URL-safe base64-encoded 32-byte key
            import base64

            fernet_key = base64.urlsafe_b64encode(key)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def _get_aesgcm(self) -> AESGCM:
        """Get AES-GCM cipher instance.

        Returns:
            AESGCM cipher instance
        """
        key = self._derive_key()
        return AESGCM(key)

    def is_encrypted(self, file_path: Path) -> bool:
        """Check if a backup file is encrypted.

        Args:
            file_path: Path to backup file

        Returns:
            True if file is encrypted, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(ENCRYPTION_MAGIC_HEADER_LEN)
                return header == ENCRYPTION_MAGIC_HEADER
        except Exception:
            return False

    def encrypt_file(self, input_path: Path, output_path: Path) -> str:
        """Encrypt a backup file using hybrid method.

        Uses Fernet for small files (< 100MB) and AES-GCM for large files (>= 100MB).

        Args:
            input_path: Path to unencrypted backup file
            output_path: Path where encrypted file will be written

        Returns:
            Encryption method used ("fernet" or "aes-gcm")
        """
        file_size = input_path.stat().st_size

        if file_size < ENCRYPTION_SIZE_THRESHOLD:
            # Use Fernet for small files
            fernet = self._get_fernet()
            with open(input_path, "rb") as f_in:
                data = f_in.read()
            encrypted_data = fernet.encrypt(data)
            # Write magic header + encrypted data
            with open(output_path, "wb") as f_out:
                f_out.write(ENCRYPTION_MAGIC_HEADER)
                f_out.write(b"F")  # Method indicator: F for Fernet
                f_out.write(encrypted_data)
            return "fernet"
        else:
            # Use AES-GCM for large files

            # For simplicity, we'll encrypt the entire file with one nonce
            # For very large files, this may require significant memory
            aesgcm = self._get_aesgcm()
            import secrets

            nonce = secrets.token_bytes(12)
            with open(input_path, "rb") as f_in:
                data = f_in.read()
            encrypted_data = aesgcm.encrypt(nonce, data, None)
            with open(output_path, "wb") as f_out:
                # Write magic header
                f_out.write(ENCRYPTION_MAGIC_HEADER)
                f_out.write(b"A")  # Method indicator: A for AES-GCM
                f_out.write(nonce)  # Write nonce (12 bytes)
                f_out.write(encrypted_data)
            return "aes-gcm"

    def decrypt_file(self, input_path: Path, output_path: Path) -> str:
        """Decrypt a backup file.

        Automatically detects encryption method from file header.

        Args:
            input_path: Path to encrypted backup file
            output_path: Path where decrypted file will be written

        Returns:
            Encryption method that was used ("fernet" or "aes-gcm")

        Raises:
            RuntimeError: If decryption fails or file is not encrypted
        """
        with open(input_path, "rb") as f_in:
            # Read magic header
            header = f_in.read(ENCRYPTION_MAGIC_HEADER_LEN)
            if header != ENCRYPTION_MAGIC_HEADER:
                raise RuntimeError("File is not encrypted or has invalid header")

            # Read method indicator
            method_indicator = f_in.read(1)
            if method_indicator == b"F":
                # Fernet encryption
                fernet = self._get_fernet()
                encrypted_data = f_in.read()
                try:
                    decrypted_data = fernet.decrypt(encrypted_data)
                    with open(output_path, "wb") as f_out:
                        f_out.write(decrypted_data)
                    return "fernet"
                except Exception as e:
                    raise RuntimeError(f"Failed to decrypt with Fernet: {e}") from e
            elif method_indicator == b"A":
                # AES-GCM encryption
                aesgcm = self._get_aesgcm()
                # Read nonce (12 bytes)
                nonce = f_in.read(12)
                if len(nonce) != 12:
                    raise RuntimeError("Invalid nonce in encrypted file")
                # Read encrypted data
                encrypted_data = f_in.read()
                try:
                    decrypted_data = aesgcm.decrypt(nonce, encrypted_data, None)
                    with open(output_path, "wb") as f_out:
                        f_out.write(decrypted_data)
                    return "aes-gcm"
                except Exception as e:
                    raise RuntimeError(f"Failed to decrypt with AES-GCM: {e}") from e
            else:
                raise RuntimeError(f"Unknown encryption method: {method_indicator}")


class DatabaseBackupService:
    """Service for managing database backups."""

    def __init__(self, secret_key: str, app: Any):
        """Initialize database backup service.

        Args:
            secret_key: SECRET_KEY for decrypting configuration
            app: Flask app instance
        """
        self.secret_key = secret_key
        self.app = app
        # Use /data-source/backups/database for persistent storage if it exists
        # Otherwise fall back to /data/backups/database
        # This directory is mounted as a volume and has proper permissions
        data_source_backup_dir = Path("/data-source/backups/database")
        data_backup_dir = Path("/data/backups/database")

        # Prefer /data-source if it exists, otherwise use /data
        if data_source_backup_dir.exists() or Path("/data-source").exists():
            self.backup_dir = data_source_backup_dir
        else:
            self.backup_dir = data_backup_dir

        # Create backup directory with proper permissions
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialize encryption utility
        self.encryption = BackupEncryption(secret_key)

    def _get_postgres_url(self) -> str:
        """Get PostgreSQL connection URL.

        Returns:
            PostgreSQL connection URL string
        """
        env_values = load_env_with_override()
        env_values.update(dict(os.environ))

        # Always use local database from environment
        return get_postgres_url(
            env_values, self.app, self.secret_key, use_app_role=False
        )

    def _parse_postgres_url(self, url: str) -> dict[str, str]:
        """Parse PostgreSQL URL into components.

        Args:
            url: PostgreSQL connection URL

        Returns:
            Dictionary with host, port, database, username, password
        """
        # Remove postgresql:// prefix
        url = url.replace("postgresql://", "")
        # Split at @
        auth_part, host_part = url.split("@")
        username, password = auth_part.split(":")
        host_port, database = host_part.split("/")
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host = host_port
            port = "5432"

        return {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
        }

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 checksum hex string
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _calculate_s3_checksum(
        self, s3_client: Any, bucket_name: str, s3_key: str
    ) -> str:
        """Calculate SHA256 checksum of an S3 object by streaming.

        Args:
            s3_client: Boto3 S3 client
            bucket_name: S3 bucket name
            s3_key: S3 object key

        Returns:
            SHA256 checksum hex string
        """
        hash_sha256 = hashlib.sha256()

        # Download file in streaming mode to calculate checksum
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)

            # Stream the file content in chunks
            for chunk in response["Body"].iter_chunks(chunk_size=4096):
                hash_sha256.update(chunk)

            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"[BACKUP] Error calculating S3 checksum for {s3_key}: {e}")
            raise

    def _refresh_backup_metadata_from_storage(
        self, backup_record: DatabaseBackup
    ) -> dict[str, Any] | None:
        """Refresh backup metadata from storage (S3 or local).

        Args:
            backup_record: DatabaseBackup record to refresh

        Returns:
            Dictionary with refreshed metadata (size_bytes, checksum) or None if failed
        """
        try:
            metadata = {}
            if backup_record.backup_metadata:
                try:
                    metadata = json.loads(backup_record.backup_metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            storage_type = metadata.get("storage_type", "local")
            storage_location = backup_record.storage_location
            s3_location = metadata.get("s3_location", "")

            size_bytes = None
            checksum = None

            # Check if backup is on S3
            is_s3 = (
                storage_type in ["s3", "both"]
                or storage_location.startswith("s3://")
                or s3_location.startswith("s3://")
            )

            if is_s3:
                # Get metadata from S3
                try:
                    from vault.services.external_storage_service import (
                        ExternalStorageService,
                    )

                    storage_service = ExternalStorageService(self.secret_key, self.app)
                    client = storage_service._get_client()
                    config = storage_service._get_config()

                    if client and config:
                        bucket_name = config.get("bucket_name")
                        if bucket_name:
                            # Determine S3 key
                            s3_key = None
                            if s3_location and s3_location.startswith("s3://"):
                                # Extract key from s3://bucket/key
                                path_without_scheme = s3_location[5:]
                                if "/" in path_without_scheme:
                                    parts = path_without_scheme.split("/", 1)
                                    if len(parts) > 1:
                                        s3_key = parts[
                                            1
                                        ]  # Get key part (skip bucket name)
                                    else:
                                        s3_key = path_without_scheme
                                else:
                                    s3_key = path_without_scheme
                            elif storage_location.startswith("s3://"):
                                path_without_scheme = storage_location[5:]
                                if "/" in path_without_scheme:
                                    parts = path_without_scheme.split("/", 1)
                                    if len(parts) > 1:
                                        s3_key = parts[
                                            1
                                        ]  # Get key part (skip bucket name)
                                    else:
                                        s3_key = path_without_scheme
                                else:
                                    s3_key = path_without_scheme
                            else:
                                # Construct from backup ID - try to extract from storage_location first
                                if (
                                    storage_location
                                    and "database-backups" in storage_location
                                ):
                                    # Extract key from storage_location if it contains the path
                                    if "/" in storage_location:
                                        s3_key = (
                                            storage_location.split(
                                                "database-backups/", 1
                                            )[-1]
                                            if "database-backups/" in storage_location
                                            else None
                                        )
                                if not s3_key:
                                    # Fallback: construct from backup ID
                                    filename = f"backup_{backup_record.created_at.strftime('%Y%m%d_%H%M%S')}_{backup_record.id}.dump"
                                    s3_key = f"database-backups/{filename}"

                            if s3_key:
                                # Get object metadata from S3
                                try:
                                    response = client.head_object(
                                        Bucket=bucket_name, Key=s3_key
                                    )
                                    size_bytes = response.get("ContentLength", 0)
                                    # Only calculate checksum if size is reasonable (not too large)
                                    if (
                                        size_bytes > 0
                                        and size_bytes < 10 * 1024 * 1024 * 1024
                                    ):  # 10GB limit
                                        checksum = self._calculate_s3_checksum(
                                            client, bucket_name, s3_key
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"[BACKUP] Failed to get S3 metadata for {s3_key}: {e}"
                                    )
                except Exception as e:
                    logger.warning(f"[BACKUP] Failed to refresh S3 metadata: {e}")

            # Check if backup is on local storage
            is_local = storage_type in ["local", "both"] or (
                not is_s3
                and storage_location
                and not storage_location.startswith("s3://")
            )

            if is_local and (size_bytes is None or checksum is None):
                # Get metadata from local file
                local_path = None
                if storage_location and not storage_location.startswith("s3://"):
                    local_path = Path(storage_location)
                else:

                    filename = f"backup_{backup_record.created_at.strftime('%Y%m%d_%H%M%S')}_{backup_record.id}.dump"
                    local_path = self.backup_dir / filename

                if local_path and local_path.exists():
                    if size_bytes is None:
                        size_bytes = local_path.stat().st_size
                    if checksum is None:
                        checksum = self._calculate_checksum(local_path)

            if size_bytes is not None:
                return {
                    "size_bytes": size_bytes,
                    "checksum": checksum,
                }

            return None
        except Exception as e:
            logger.warning(f"[BACKUP] Error refreshing metadata from storage: {e}")
            return None

    def validate_backup(
        self, backup_path: Path, metadata_path: Path | None = None
    ) -> dict[str, Any]:
        """Validate a backup file using pg_restore --list and optional metadata.json.

        Storage-first approach: if metadata.json is provided, validates checksum and size
        before running pg_restore validation.

        Args:
            backup_path: Path to backup file
            metadata_path: Optional path to metadata.json file

        Returns:
            Dictionary with validation result (valid, error)
        """
        try:

            if metadata_path and metadata_path.exists():
                metadata = self._read_backup_metadata(metadata_path)
                if metadata:
                    file_info = metadata.get("file", {})
                    expected_checksum = file_info.get("checksum")
                    expected_size = file_info.get("size_bytes")

                    # Verify file size
                    actual_size = backup_path.stat().st_size
                    if expected_size and actual_size != expected_size:
                        return {
                            "valid": False,
                            "error": f"File size mismatch: expected {expected_size}, got {actual_size}",
                        }

                    # Verify checksum
                    if expected_checksum:
                        actual_checksum = self._calculate_checksum(backup_path)
                        if actual_checksum != expected_checksum:
                            return {
                                "valid": False,
                                "error": "Checksum mismatch: file may be corrupted",
                            }

            # pg_restore -l lists the contents of the archive
            # This verifies the file format is valid
            cmd = ["pg_restore", "-l", str(backup_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            validation_result = {"valid": result.returncode == 0}
            if result.returncode != 0:
                validation_result["error"] = f"pg_restore check failed: {result.stderr}"

            # Update metadata.json with validation result if it exists
            if metadata_path and metadata_path.exists():
                try:
                    metadata = self._read_backup_metadata(metadata_path)
                    if metadata:
                        metadata["validation"] = {
                            "valid": validation_result["valid"],
                            "validated_at": datetime.now(timezone.utc).isoformat(),
                            "method": "pg_restore_list",
                        }
                        if "error" in validation_result:
                            metadata["validation"]["error"] = validation_result["error"]

                        with open(metadata_path, "w", encoding="utf-8") as f:
                            json.dump(metadata, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(
                        f"[BACKUP] Failed to update metadata.json with validation result: {e}"
                    )

            return validation_result
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _get_postgres_version(self) -> str | None:
        """Get PostgreSQL version from database.

        Returns:
            PostgreSQL version string or None if unavailable
        """
        try:
            result = db.session.execute(sql_text("SELECT version()"))
            version_str = result.scalar()
            if version_str:
                # Extract version number (e.g., "PostgreSQL 15.3" -> "15.3")
                parts = version_str.split()
                if len(parts) >= 2:
                    return parts[1]
                return version_str
            return None
        except Exception as e:
            logger.debug(f"[BACKUP] Failed to get PostgreSQL version: {e}")
            return None

    def _write_backup_metadata(
        self,
        backup_path: Path,
        backup_id: str,
        backup_type: str,
        db_params: dict[str, str],
        size_bytes: int,
        checksum: str,
        validation_result: dict[str, Any],
        storage_type: str,
        created_at: datetime,
        s3_location: str | None = None,
        encryption_method: str | None = None,
    ) -> Path:
        """Write backup metadata.json file to storage.

        Args:
            backup_path: Path to backup dump file
            backup_id: Backup ID (UUID)
            backup_type: Type of backup ("manual" or "scheduled")
            db_params: Database connection parameters
            size_bytes: Size of backup file in bytes
            checksum: SHA256 checksum of backup file
            validation_result: Result from validate_backup()
            storage_type: Storage type ("local", "s3", or "both")
            created_at: Backup creation timestamp
            s3_location: Optional S3 location if stored on S3

        Returns:
            Path to metadata.json file

        Raises:
            RuntimeError: If metadata write fails
        """
        # Get PostgreSQL version
        postgres_version = self._get_postgres_version()

        # Build metadata dictionary according to schema
        metadata = {
            "backup_id": backup_id,
            "created_at": created_at.isoformat(),
            "backup_type": backup_type,
            "database": {
                "host": db_params["host"],
                "database": db_params["database"],
                "engine": "postgresql",
                "version": postgres_version or "unknown",
            },
            "file": {
                "size_bytes": size_bytes,
                "checksum": checksum,
                "checksum_algorithm": "sha256",
                "format": "custom",
                "compression": True,
            },
            "storage": {
                "type": storage_type,
                "local_path": (
                    str(backup_path) if storage_type in ["local", "both"] else None
                ),
                "s3_location": s3_location,
            },
            "validation": {
                "valid": validation_result.get("valid", False),
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "method": "pg_restore_list",
            },
        }

        # Add encryption information if backup is encrypted
        if encryption_method:
            metadata["encryption"] = {
                "encrypted": True,
                "method": encryption_method,
            }
        else:
            metadata["encryption"] = {
                "encrypted": False,
            }

        # Write metadata.json alongside dump file
        metadata_path = backup_path.with_suffix(".metadata.json")
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"[BACKUP] Wrote metadata to {metadata_path}")
        except Exception as e:
            logger.error(f"[BACKUP] Failed to write metadata.json: {e}")
            raise RuntimeError(f"Failed to write metadata.json: {e}") from e

        # Upload metadata to S3 if S3 storage is configured
        if storage_type in ["s3", "both"] and s3_location:
            try:
                from vault.services.external_storage_service import (
                    ExternalStorageService,
                )

                storage_service = ExternalStorageService(self.secret_key, self.app)
                client = storage_service._get_client()
                config = storage_service._get_config()

                if client and config:
                    bucket_name = config.get("bucket_name")
                    if bucket_name:
                        # Extract S3 key from s3_location
                        # Format: s3://bucket/key or s3://key
                        if s3_location.startswith("s3://"):
                            path_without_scheme = s3_location[5:]
                            if path_without_scheme.startswith(f"{bucket_name}/"):
                                s3_key_base = path_without_scheme[
                                    len(bucket_name) + 1 :
                                ]
                            else:
                                s3_key_base = path_without_scheme
                        else:
                            s3_key_base = s3_location

                        # Remove .dump extension and add .metadata.json
                        if s3_key_base.endswith(".dump"):
                            s3_key_metadata = s3_key_base[:-5] + ".metadata.json"
                        else:
                            s3_key_metadata = s3_key_base + ".metadata.json"

                        # Upload metadata file
                        with open(metadata_path, "rb") as f:
                            client.put_object(
                                Bucket=bucket_name,
                                Key=s3_key_metadata,
                                Body=f,
                                ContentType="application/json",
                            )
                        logger.info(
                            f"[BACKUP] Uploaded metadata to s3://{bucket_name}/{s3_key_metadata}"
                        )
            except Exception as e:
                logger.warning(
                    f"[BACKUP] Failed to upload metadata to S3 (non-critical): {e}"
                )
                # Don't fail if S3 upload fails - local metadata is sufficient

        return metadata_path

    def _upload_file_to_s3(self, file_path: Path, s3_key: str) -> None:
        """Upload any file to S3 storage.

        Args:
            file_path: Path to local file
            s3_key: S3 key (path) where file should be stored

        Raises:
            RuntimeError: If upload fails
        """
        from vault.services.external_storage_service import ExternalStorageService

        try:
            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if not client or not config:
                raise RuntimeError("External storage (S3) is not configured")

            bucket_name = config.get("bucket_name")
            if not bucket_name:
                raise RuntimeError("S3 bucket name not configured")

            logger.info(
                f"[BACKUP] Uploading {file_path} to s3://{bucket_name}/{s3_key}"
            )

            content_type = "application/json" if file_path.suffix == ".json" else None
            with open(file_path, "rb") as f:
                put_kwargs = {
                    "Bucket": bucket_name,
                    "Key": s3_key,
                    "Body": f,
                }
                if content_type:
                    put_kwargs["ContentType"] = content_type
                client.put_object(**put_kwargs)

            logger.info(f"[BACKUP] Successfully uploaded to S3: {s3_key}")

        except Exception as e:
            logger.error(f"[BACKUP] S3 upload failed: {e}")
            raise RuntimeError(f"Failed to upload file to S3: {e}") from e

    def _upload_to_s3_forced(
        self, file_path: Path, backup_record: DatabaseBackup | None
    ) -> None:
        """Upload backup file to S3 storage.

        Args:
            file_path: Path to local backup file
            backup_record: Optional database backup record (for backward compatibility)

        Raises:
            RuntimeError: If upload fails
        """
        s3_key = f"database-backups/{file_path.name}"
        self._upload_file_to_s3(file_path, s3_key)

    def _download_from_s3_if_configured(
        self, local_path: Path, backup_record: DatabaseBackup
    ) -> None:
        """Download backup file from S3 if it's stored there and local file doesn't exist.

        Args:
            local_path: Path where the file should be downloaded
            backup_record: Database backup record

        Raises:
            RuntimeError: If download fails or S3 is not configured
        """
        from vault.services.external_storage_service import ExternalStorageService

        # Check if backup is stored on S3
        metadata = {}
        if backup_record.backup_metadata:
            try:
                metadata = json.loads(backup_record.backup_metadata)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(
                    f"[BACKUP] Failed to parse backup_metadata for {backup_record.id}: {e}"
                )
                metadata = {}

        storage_type = metadata.get("storage_type", "local")
        s3_location = metadata.get("s3_location")
        is_s3_url = backup_record.storage_location.startswith("s3://")

        # Only download if backup is stored on S3 (not just local)
        if storage_type not in ["s3", "both"] and not s3_location and not is_s3_url:
            logger.debug(
                f"[BACKUP] Backup {backup_record.id} is not stored on S3, skipping download"
            )
            return

        try:
            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if not client or not config:
                raise RuntimeError("External storage (S3) is not configured")

            bucket_name = config.get("bucket_name")
            if not bucket_name:
                raise RuntimeError("S3 bucket name not configured")

            # Determine S3 key - prioritize s3_location from metadata (now always present for S3 backups)
            s3_key = None

            # Priority 1: Use s3_location from metadata (most reliable)
            if s3_location and s3_location.startswith("s3://"):
                # Extract key from s3://bucket/key/path or s3://key/path
                path_without_scheme = s3_location[5:]  # Remove "s3://"

                if path_without_scheme.startswith(f"{bucket_name}/"):
                    s3_key = path_without_scheme[len(bucket_name) + 1 :]
                else:
                    # Assume full path after s3:// is the key (format: s3://key)
                    s3_key = path_without_scheme
                logger.debug(
                    f"[BACKUP] Using S3 key from metadata s3_location: {s3_key}"
                )

            # Priority 2: Fallback to storage_location if it's an S3 URL
            if not s3_key and is_s3_url:
                path_without_scheme = backup_record.storage_location[
                    5:
                ]  # Remove "s3://"

                if path_without_scheme.startswith(f"{bucket_name}/"):
                    s3_key = path_without_scheme[len(bucket_name) + 1 :]
                else:
                    # Assume full path is the key
                    s3_key = path_without_scheme
                logger.debug(f"[BACKUP] Using S3 key from storage_location: {s3_key}")

            # Priority 3: Construct from backup record metadata (fallback)
            if not s3_key:
                if backup_record.created_at:
                    timestamp_str = backup_record.created_at.strftime("%Y%m%d_%H%M%S")
                    filename = f"backup_{timestamp_str}_{backup_record.id}.dump"
                    s3_key = f"database-backups/{filename}"
                    logger.debug(
                        f"[BACKUP] Constructed S3 key from timestamp and ID: {s3_key}"
                    )
                else:
                    # Last resort: use filename from local_path
                    filename = local_path.name
                    s3_key = f"database-backups/{filename}"
                    logger.debug(
                        f"[BACKUP] Using S3 key from local_path filename: {s3_key}"
                    )

            if not s3_key:
                raise RuntimeError(
                    f"Could not determine S3 key for backup {backup_record.id}. "
                    f"s3_location: {s3_location}, storage_location: {backup_record.storage_location}"
                )

            logger.debug(
                f"[BACKUP] Downloading from S3: s3://{bucket_name}/{s3_key} to {local_path}"
            )

            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download file from S3
            try:
                response = client.get_object(Bucket=bucket_name, Key=s3_key)
                with open(local_path, "wb") as f:
                    f.write(response["Body"].read())

                logger.debug(
                    f"[BACKUP] Successfully downloaded from S3: s3://{bucket_name}/{s3_key}"
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                if error_code == "NoSuchKey" or error_code == "404":
                    error_msg = (
                        f"Backup file not found in S3: s3://{bucket_name}/{s3_key}. "
                        f"Backup ID: {backup_record.id}, "
                        f"Metadata s3_location: {s3_location}, "
                        f"storage_location: {backup_record.storage_location}"
                    )
                else:
                    error_msg = (
                        f"S3 download failed: {error_code} - {error_message}. "
                        f"Attempted to download: s3://{bucket_name}/{s3_key}. "
                        f"Backup ID: {backup_record.id}"
                    )
                logger.error(f"[BACKUP] {error_msg}")
                raise RuntimeError(error_msg) from e

        except RuntimeError:
            # Re-raise RuntimeError as-is (already has detailed message)
            raise
        except Exception as e:
            error_msg = (
                f"Unexpected error downloading backup from S3: {e}. "
                f"Backup ID: {backup_record.id}, "
                f"S3 key attempted: {s3_key if 's3_key' in locals() else 'unknown'}"
            )
            logger.error(f"[BACKUP] {error_msg}", exc_info=True)
            raise RuntimeError(error_msg) from e

    def _download_from_s3_by_id(self, local_path: Path, backup_id: str) -> bool:
        """Download backup file from S3 using only backup_id (no database record needed).

        This method tries multiple S3 key formats to find the backup file.

        Args:
            local_path: Path where the file should be downloaded
            backup_id: Backup ID (UUID)

        Returns:
            True if file was successfully downloaded, False otherwise
        """
        from vault.services.external_storage_service import ExternalStorageService

        try:
            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if not client or not config:
                logger.debug("[BACKUP] External storage (S3) is not configured")
                return False

            bucket_name = config.get("bucket_name")
            if not bucket_name:
                logger.debug("[BACKUP] S3 bucket name not configured")
                return False

            # First, try to list files in database-backups/ and find one matching backup_id
            try:
                logger.debug(
                    f"[BACKUP] Listing S3 objects in database-backups/ to find backup {backup_id}"
                )
                response = client.list_objects_v2(
                    Bucket=bucket_name, Prefix="database-backups/backup_"
                )

                if "Contents" in response:
                    for obj in response["Contents"]:
                        s3_key = obj["Key"]
                        # Check if this key contains the backup_id
                        if backup_id in s3_key and s3_key.endswith(".dump"):
                            logger.debug(f"[BACKUP] Found matching S3 key: {s3_key}")
                            # Download this file
                            try:
                                file_response = client.get_object(
                                    Bucket=bucket_name, Key=s3_key
                                )
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(local_path, "wb") as f:
                                    f.write(file_response["Body"].read())
                                logger.debug(
                                    f"[BACKUP] Successfully downloaded from S3: s3://{bucket_name}/{s3_key}"
                                )
                                return True
                            except ClientError as e:
                                error_code = e.response.get("Error", {}).get(
                                    "Code", "Unknown"
                                )
                                logger.debug(
                                    f"[BACKUP] Failed to download {s3_key}: {error_code}"
                                )
                                continue

                logger.debug(
                    f"[BACKUP] No matching backup file found in S3 for backup_id {backup_id}"
                )
                return False

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                logger.debug(f"[BACKUP] Failed to list S3 objects: {error_code}")
                return False
            except Exception as e:
                logger.debug(f"[BACKUP] Unexpected error listing S3 objects: {e}")
                return False

        except Exception as e:
            logger.debug(f"[BACKUP] Error in _download_from_s3_by_id: {e}")
            return False

    def _check_file_matches_backup_id(self, file_path: Path, backup_id: str) -> bool:
        """Check if a backup file matches the given backup_id.

        Args:
            file_path: Path to the backup file
            backup_id: Backup ID (UUID) to check

        Returns:
            True if the file matches the backup_id, False otherwise
        """
        try:
            if not file_path.exists():
                return False

            filename = file_path.name
            # Parse filename: backup_{timestamp}_{uuid}.dump
            parts = Path(filename).stem.split("_")
            if len(parts) < 3:
                return False

            file_backup_id = parts[-1]

            # Validate UUID format and check if it matches
            try:
                uuid.UUID(file_backup_id)
                return file_backup_id == backup_id
            except ValueError:
                return False
        except Exception:
            return False

    def _find_local_backup_by_id(self, backup_id: str) -> Path | None:
        """Find local backup file by backup_id (no database record needed).

        This method searches the local backup directory for files matching the backup_id.

        Args:
            backup_id: Backup ID (UUID)

        Returns:
            Path to the backup file if found, None otherwise
        """
        logger.debug(f"[BACKUP] Searching local storage for backup {backup_id}")

        try:
            if not self.backup_dir.exists():
                logger.debug(
                    f"[BACKUP] Backup directory does not exist: {self.backup_dir}"
                )
                return None

            # Find all local backup files
            backup_files = list(self.backup_dir.glob("backup_*.dump"))

            logger.debug(
                f"[BACKUP] Searching {len(backup_files)} local backup files for backup_id {backup_id}"
            )

            for backup_file in backup_files:
                try:
                    filename = backup_file.name

                    # Parse filename: backup_{timestamp}_{uuid}.dump
                    parts = Path(filename).stem.split("_")
                    if len(parts) < 3:
                        continue

                    file_backup_id = parts[-1]

                    # Validate UUID format and check if it matches
                    try:
                        uuid.UUID(file_backup_id)
                        if file_backup_id == backup_id:
                            logger.debug(
                                f"[BACKUP] Found matching local backup file: {backup_file}"
                            )
                            return backup_file
                    except ValueError:
                        continue

                except Exception as e:
                    logger.debug(
                        f"[BACKUP] Error processing local backup file {backup_file}: {e}"
                    )
                    continue

            logger.debug(
                f"[BACKUP] No local backup file found matching backup_id {backup_id}"
            )
            return None

        except Exception as e:
            logger.debug(f"[BACKUP] Error in _find_local_backup_by_id: {e}")
            return None

    def _find_backup_by_id_in_storage(
        self, backup_id: str
    ) -> tuple[Path | None, Path | None]:
        """Find backup file and metadata by backup_id in storage (no database access).

        Searches local storage first, then S3 if not found locally.

        Args:
            backup_id: Backup ID (UUID)

        Returns:
            Tuple of (backup_path, metadata_path) or (None, None) if not found
        """

        backup_path = self._find_local_backup_by_id(backup_id)
        if backup_path and backup_path.exists():
            metadata_path = backup_path.with_suffix(".metadata.json")
            logger.debug(
                f"[BACKUP] Found backup {backup_id} in local storage: {backup_path}"
            )
            return backup_path, metadata_path if metadata_path.exists() else None

        try:
            from vault.services.external_storage_service import ExternalStorageService

            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if client and config:
                bucket_name = config.get("bucket_name")
                if bucket_name:
                    # List S3 objects to find matching backup
                    prefix = "database-backups/backup_"
                    try:
                        response = client.list_objects_v2(
                            Bucket=bucket_name, Prefix=prefix
                        )

                        if "Contents" in response:
                            for obj in response["Contents"]:
                                s3_key = obj["Key"]
                                filename = s3_key.split("/")[-1]

                                # Check if this file contains the backup_id
                                if backup_id in filename and filename.endswith(".dump"):
                                    logger.debug(
                                        f"[BACKUP] Found backup {backup_id} in S3: {s3_key}"
                                    )
                                    # Download to local temp location for restore
                                    temp_backup_path = (
                                        self.backup_dir
                                        / f"restore_temp_{backup_id}.dump"
                                    )
                                    temp_backup_path.parent.mkdir(
                                        parents=True, exist_ok=True
                                    )

                                    file_response = client.get_object(
                                        Bucket=bucket_name, Key=s3_key
                                    )
                                    with open(temp_backup_path, "wb") as f:
                                        f.write(file_response["Body"].read())

                                    metadata_key = s3_key[:-5] + ".metadata.json"
                                    temp_metadata_path = None
                                    try:
                                        metadata_response = client.get_object(
                                            Bucket=bucket_name, Key=metadata_key
                                        )
                                        temp_metadata_path = (
                                            self.backup_dir
                                            / f"restore_temp_{backup_id}.metadata.json"
                                        )
                                        with open(temp_metadata_path, "wb") as f:
                                            f.write(metadata_response["Body"].read())
                                    except ClientError:
                                        # Metadata not found, that's OK - expected for older backups
                                        logger.debug(
                                            "S3 metadata not found for backup, skipping metadata download"
                                        )

                                    return temp_backup_path, temp_metadata_path

                    except Exception as e:
                        logger.debug(
                            f"[BACKUP] Error searching S3 for backup {backup_id}: {e}"
                        )

        except Exception as e:
            logger.debug(
                f"[BACKUP] Error accessing S3 storage for backup {backup_id}: {e}"
            )

        logger.debug(f"[BACKUP] Backup {backup_id} not found in storage")
        return None, None

    def validate_database(self, db_params: dict[str, str]) -> dict[str, Any]:
        """Validate database state after restore.

        Args:
            db_params: Database connection parameters

        Returns:
            Validation result dictionary
        """
        row_counts = {}
        errors = []

        try:
            # Check critical tables exist and have data
            critical_tables = ["users", "vaultspaces", "files"]

            # Use the current session which should be reset and valid
            for table in critical_tables:
                try:
                    # Check if table exists
                    result = db.session.execute(
                        sql_text(
                            f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'"
                        )
                    )
                    if result.scalar() == 0:
                        errors.append(f"Table '{table}' is missing")
                        continue

                    # Check row count
                    result = db.session.execute(
                        sql_text(f"SELECT COUNT(*) FROM {table}")
                    )
                    count = result.scalar()
                    row_counts[table] = count

                except Exception as e:
                    errors.append(f"Error checking table {table}: {e}")

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "row_counts": row_counts,
            }

        except Exception as e:
            logger.error(f"[RESTORE] Database validation error: {e}")
            return {
                "valid": False,
                "errors": [f"Validation exception: {e}"],
                "row_counts": {},
            }

    def create_backup(
        self, backup_type: str = "manual", storage_type: str = "local"
    ) -> DatabaseBackup:
        """Create a database backup using pg_dump.

        Storage-first approach: creates dump file and metadata.json before database record.
        Database record is created only as a cache and backup is valid even if DB write fails.

        Args:
            backup_type: Type of backup ("manual" or "scheduled")
            storage_type: Storage type ("local", "s3", or "both")

        Returns:
            DatabaseBackup object

        Raises:
            RuntimeError: If backup fails
        """
        postgres_url = self._get_postgres_url()
        db_params = self._parse_postgres_url(postgres_url)

        # Generate backup filename
        created_at = datetime.now(timezone.utc)
        timestamp = created_at.strftime("%Y%m%d_%H%M%S")
        backup_id = str(uuid.uuid4())
        backup_filename = f"backup_{timestamp}_{backup_id}.dump"
        backup_path = self.backup_dir / backup_filename

        # Determine S3 location if needed
        s3_location = None
        if storage_type in ["s3", "both"]:
            s3_key = f"database-backups/{backup_filename}"
            s3_location = f"s3://{s3_key}"

        # Storage-first: create dump file first, then metadata, then DB record
        try:
            # Execute pg_dump
            env = os.environ.copy()
            env["PGPASSWORD"] = db_params["password"]

            cmd = [
                "pg_dump",
                "-Fc",  # Custom format (compressed)
                "-v",  # Verbose for logging
                "-h",
                db_params["host"],
                "-p",
                db_params["port"],
                "-U",
                db_params["username"],
                "-d",
                db_params["database"],
                "-f",
                str(backup_path),
            ]

            logger.info(
                f"[BACKUP] Starting backup {backup_id} (storage: {storage_type}) to {backup_path}"
            )
            subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            # Encrypt the backup file
            encrypted_backup_path = backup_path.with_suffix(".dump.enc")
            encryption_method = self.encryption.encrypt_file(
                backup_path, encrypted_backup_path
            )
            logger.info(
                f"[BACKUP] Encrypted backup {backup_id} using {encryption_method}"
            )

            # Replace original with encrypted file
            backup_path.unlink()
            encrypted_backup_path.rename(backup_path)

            # Calculate file size and checksum of encrypted file
            size_bytes = backup_path.stat().st_size
            checksum = self._calculate_checksum(backup_path)

            # Validate backup (need to decrypt temporarily for validation)
            # Create temporary decrypted file for validation
            import tempfile

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".dump"
            ) as temp_decrypted:
                temp_decrypted_path = Path(temp_decrypted.name)
                try:
                    self.encryption.decrypt_file(backup_path, temp_decrypted_path)
                    validation_result = self.validate_backup(temp_decrypted_path)
                finally:
                    # Clean up temporary file
                    if temp_decrypted_path.exists():
                        temp_decrypted_path.unlink()

            if not validation_result["valid"]:
                # Clean up failed backup file
                if backup_path.exists():
                    backup_path.unlink()
                raise RuntimeError(
                    f"Backup validation failed: {validation_result.get('error')}"
                )

            # Write metadata.json to storage (storage-first)
            metadata_path = self._write_backup_metadata(
                backup_path=backup_path,
                backup_id=backup_id,
                backup_type=backup_type,
                db_params=db_params,
                size_bytes=size_bytes,
                checksum=checksum,
                validation_result=validation_result,
                storage_type=storage_type,
                created_at=created_at,
                s3_location=s3_location,
                encryption_method=encryption_method,
            )

            # Handle storage based on storage_type
            if storage_type == "s3":
                # Upload dump and metadata to S3, then delete local files
                self._upload_to_s3_forced(backup_path, None)
                # Upload metadata
                if metadata_path.exists():
                    self._upload_file_to_s3(
                        metadata_path, f"database-backups/{metadata_path.name}"
                    )
                # Delete local files after successful upload
                if backup_path.exists():
                    backup_path.unlink()
                    logger.info(f"[BACKUP] Deleted temporary local file: {backup_path}")
                if metadata_path.exists():
                    metadata_path.unlink()
                    logger.info(
                        f"[BACKUP] Deleted temporary local metadata: {metadata_path}"
                    )
            elif storage_type == "both":
                # Upload dump and metadata to S3, keep local files
                self._upload_to_s3_forced(backup_path, None)
                if metadata_path.exists():
                    self._upload_file_to_s3(
                        metadata_path, f"database-backups/{metadata_path.name}"
                    )

            # Create database record as cache (non-blocking)
            # Backup is valid even if DB write fails
            backup_record = None
            try:
                storage_location = (
                    s3_location if storage_type == "s3" else str(backup_path)
                )

                # Read metadata.json to store in DB
                metadata_dict = {}
                if metadata_path.exists():
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata_dict = json.load(f)

                backup_record = DatabaseBackup(
                    id=backup_id,
                    backup_type=backup_type,
                    status="completed",
                    storage_location=storage_location,
                    size_bytes=size_bytes,
                    checksum=checksum,
                    backup_metadata=json.dumps(metadata_dict),
                )
                db.session.add(backup_record)
                db.session.commit()
                logger.info(f"[BACKUP] Created database record for backup {backup_id}")
            except Exception as db_error:
                # Log but don't fail - backup is valid in storage
                logger.warning(
                    f"[BACKUP] Failed to create database record for {backup_id} (non-critical): {db_error}"
                )
                # Create a minimal record for return value
                if backup_record is None:
                    backup_record = DatabaseBackup(
                        id=backup_id,
                        backup_type=backup_type,
                        status="completed",
                        storage_location=(
                            s3_location if storage_type == "s3" else str(backup_path)
                        ),
                        size_bytes=size_bytes,
                        checksum=checksum,
                        backup_metadata=None,
                    )
                try:
                    db.session.rollback()
                except Exception:
                    # Rollback may fail if session is already closed - expected in some error scenarios
                    logger.debug("Database rollback failed (session may be closed)")

            logger.info(
                f"[BACKUP] Backup {backup_id} completed successfully ({size_bytes} bytes, storage: {storage_type})"
            )

            return backup_record

        except subprocess.CalledProcessError as e:
            # Clean up failed backup file
            if backup_path.exists():
                backup_path.unlink()
            # Clean up metadata if it exists
            metadata_path = backup_path.with_suffix(".metadata.json")
            if metadata_path.exists():
                metadata_path.unlink()
            logger.error(f"[BACKUP] Backup {backup_id} failed: {e}")
            raise RuntimeError(f"Backup failed: {e.stderr}") from e
        except Exception as e:
            # Clean up failed backup file
            if backup_path.exists():
                backup_path.unlink()
            # Clean up metadata if it exists
            metadata_path = backup_path.with_suffix(".metadata.json")
            if metadata_path.exists():
                metadata_path.unlink()
            logger.error(f"[BACKUP] Backup {backup_id} failed: {e}", exc_info=True)
            raise

    def restore_backup_radical(
        self, backup_path: Path, backup_id: str
    ) -> dict[str, Any]:
        """Restore database from a backup using radical approach (DROP SCHEMA CASCADE).

        Storage-first approach: validates backup using metadata.json if available,
        then performs restore. No database queries required to find or validate backup.

        Args:
            backup_path: Path to backup file
            backup_id: Backup ID for logging

        Returns:
            Dictionary with restoration result

        Raises:
            RuntimeError: If restore fails
        """
        # Initialize variables for cleanup
        decrypted_backup_path = backup_path
        is_encrypted = False
        encryption_method = None

        try:
            # Main restore logic
            if not backup_path.exists():
                raise RuntimeError(f"Backup file not found: {backup_path}")

            # Read metadata.json if available (storage-first validation)
            metadata_path = backup_path.with_suffix(".metadata.json")
            metadata = self._read_backup_metadata(metadata_path)

            # Validate backup using metadata if available
            if metadata:
                file_info = metadata.get("file", {})
                expected_checksum = file_info.get("checksum")
                expected_size = file_info.get("size_bytes")

                # Verify file size matches
                actual_size = backup_path.stat().st_size
                if expected_size and actual_size != expected_size:
                    raise RuntimeError(
                        f"Backup file size mismatch: expected {expected_size}, got {actual_size}"
                    )

                # Verify checksum matches
                if expected_checksum:
                    actual_checksum = self._calculate_checksum(backup_path)
                    if actual_checksum != expected_checksum:
                        raise RuntimeError(
                            "Backup checksum mismatch: file may be corrupted"
                        )

                validation_info = metadata.get("validation", {})
                if not validation_info.get("valid", False):
                    logger.warning(
                        f"[RESTORE] Backup {backup_id} metadata indicates invalid backup, proceeding anyway"
                    )
            else:
                # No metadata.json - check if encrypted and decrypt for validation
                is_encrypted_no_metadata = self.encryption.is_encrypted(backup_path)
                if is_encrypted_no_metadata:
                    # Create temporary decrypted file for validation
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".dump"
                    ) as temp_decrypted:
                        temp_decrypted_path = Path(temp_decrypted.name)
                    try:
                        self.encryption.decrypt_file(backup_path, temp_decrypted_path)
                        validation_result = self.validate_backup(temp_decrypted_path)
                    finally:
                        if temp_decrypted_path.exists():
                            temp_decrypted_path.unlink()
                else:
                    # Not encrypted, validate directly
                    validation_result = self.validate_backup(backup_path)
                if not validation_result.get("valid", False):
                    raise RuntimeError(
                        f"Backup validation failed: {validation_result.get('error')}"
                    )

            # Use POSTGRES_USER (superuser) for restore operations
            from common.env import load_env_with_override
            import time

            env_values = load_env_with_override()
            env_values.update(dict(os.environ))

            postgres_host = env_values.get("POSTGRES_HOST", "postgres")
            postgres_port = env_values.get("POSTGRES_PORT", "5432")
            postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
            postgres_user = env_values.get("POSTGRES_USER", "leyzen")
            postgres_password = env_values.get("POSTGRES_PASSWORD", "")

            if not postgres_password:
                raise RuntimeError("POSTGRES_PASSWORD is required for restore")

            env = os.environ.copy()
            env["PGPASSWORD"] = postgres_password

            # Step 1: Terminate all active connections from 'postgres' database
            terminate_cmd = [
                "psql",
                "-h",
                postgres_host,
                "-p",
                postgres_port,
                "-U",
                postgres_user,
                "-d",
                "postgres",  # Connect to 'postgres' database to terminate connections
                "-c",
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{postgres_db}' AND pid <> pg_backend_pid();",
            ]

            result = subprocess.run(
                terminate_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            # Ignore errors - some connections may not exist

            # Step 2: Wait a moment for connections to close
            time.sleep(1)

            # Step 3: Drop schema completely (this removes ALL objects)
            drop_schema_cmd = [
                "psql",
                "-h",
                postgres_host,
                "-p",
                postgres_port,
                "-U",
                postgres_user,
                "-d",
                postgres_db,  # Connect to target database
                "-c",
                "DROP SCHEMA IF EXISTS public CASCADE;",
            ]

            result = subprocess.run(
                drop_schema_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                # Filter out expected "does not exist" messages
                if (
                    "does not exist" not in error_msg.lower()
                    and "schema" not in error_msg.lower()
                ):
                    logger.warning(f"[RESTORE] Schema drop warnings: {error_msg}")

            # Step 4: Recreate schema
            create_schema_cmd = [
                "psql",
                "-h",
                postgres_host,
                "-p",
                postgres_port,
                "-U",
                postgres_user,
                "-d",
                postgres_db,
                "-c",
                f"CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO {postgres_user}; GRANT ALL ON SCHEMA public TO PUBLIC;",
            ]

            result = subprocess.run(
                create_schema_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"

                if "already exists" not in error_msg.lower():
                    raise RuntimeError(f"Failed to create schema 'public': {error_msg}")

            # Verify schema is empty before restore
            verify_empty_cmd = [
                "psql",
                "-h",
                postgres_host,
                "-p",
                postgres_port,
                "-U",
                postgres_user,
                "-d",
                postgres_db,
                "-t",  # Tuples only (no headers)
                "-c",
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';",
            ]
            result = subprocess.run(
                verify_empty_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                table_count = int(result.stdout.strip() or "0")
                if table_count > 0:
                    logger.error(
                        f"[RESTORE] Schema is not empty! Found {table_count} tables. "
                        "This should not happen after DROP SCHEMA CASCADE."
                    )
                    raise RuntimeError(
                        f"Database schema is not empty ({table_count} tables found). "
                        "Cannot restore to non-empty database."
                    )

            # Check if backup is encrypted and decrypt if necessary

            # Check encryption status from metadata or file header
            if metadata:
                encryption_info = metadata.get("encryption", {})
                is_encrypted = encryption_info.get("encrypted", False)
                encryption_method = encryption_info.get("method")
            else:
                # Fallback: check file header
                is_encrypted = self.encryption.is_encrypted(backup_path)

            if is_encrypted:
                # Create temporary decrypted file
                import tempfile

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".dump"
                ) as temp_decrypted:
                    decrypted_backup_path = Path(temp_decrypted.name)
                try:
                    actual_method = self.encryption.decrypt_file(
                        backup_path, decrypted_backup_path
                    )
                    if encryption_method and actual_method != encryption_method:
                        logger.warning(
                            f"[RESTORE] Encryption method mismatch: metadata says {encryption_method}, file uses {actual_method}"
                        )
                    logger.info(
                        f"[RESTORE] Decrypted backup {backup_id} using {actual_method}"
                    )
                except Exception as e:
                    # Clean up temporary file on error
                    if decrypted_backup_path.exists():
                        decrypted_backup_path.unlink()
                    raise RuntimeError(f"Failed to decrypt backup: {e}") from e

            # Restore backup using superuser

            # SET commands (like SET transaction_timeout = 0;) that cause pg_restore to fail
            # Instead, we rely on the fact that the database is completely empty (DROP SCHEMA CASCADE)
            # and pg_restore will restore in the correct order automatically
            # Don't use --clean here since we already cleaned with DROP SCHEMA CASCADE
            # Don't use --exit-on-error: we want to continue even with non-critical errors
            # and validate the restore afterwards
            restore_cmd = [
                "pg_restore",
                "-h",
                postgres_host,
                "-p",
                postgres_port,
                "-U",
                postgres_user,
                "-d",
                postgres_db,
                "--no-owner",  # Don't restore ownership
                "--no-acl",  # Don't restore access privileges
                "--verbose",  # Verbose output
                # Don't use --single-transaction: it fails on invalid SET commands in backups
                # The database is empty, so restore order is handled correctly by pg_restore
                str(decrypted_backup_path),
            ]

            logger.info(f"[RESTORE] Starting restore from backup {backup_id}")
            result = subprocess.run(
                restore_cmd,
                env=env,
                capture_output=True,
                text=True,
                check=False,  # Don't fail immediately, check errors manually
            )

            error_output = result.stderr or result.stdout or ""

            # Check for critical errors (ignore warnings about existing objects)
            # Filter out expected/non-critical errors:
            # - "already exists" : objects already exist (expected after cleanup)
            # - "does not exist, skipping" : object doesn't exist (expected)
            # - "multiple primary keys" : constraint already exists (expected)
            # - "already been registered" : SQLAlchemy warning (expected)
            # - "unrecognized configuration parameter" : backup contains invalid SET commands (non-critical, can be ignored)
            #   This happens when backups are created with different PostgreSQL versions or tools
            # - "transaction_timeout" : specific case of unrecognized configuration parameter
            critical_errors = [
                line
                for line in error_output.split("\n")
                if "ERROR:" in line
                and "already exists" not in line.lower()
                and "does not exist, skipping" not in line.lower()
                and "multiple primary keys" not in line.lower()
                and "already been registered" not in line.lower()
                and "unrecognized configuration parameter" not in line.lower()
                and "transaction_timeout" not in line.lower()
            ]

            # Check for foreign key violations (data order issues)
            fk_violations = [
                line
                for line in error_output.split("\n")
                if "violates foreign key constraint" in line.lower()
            ]

            if fk_violations:
                # Foreign key violations indicate data order issues
                # This is critical - data is not being restored correctly
                error_msg = f"Foreign key violations during restore (data order issue):\n{chr(10).join(fk_violations[:5])}"
                logger.error(f"[RESTORE] {error_msg}")
                raise RuntimeError(error_msg)

            if critical_errors:
                # Only raise if there are critical errors
                error_msg = f"Critical errors during restore:\n{chr(10).join(critical_errors[:10])}"
                logger.error(f"[RESTORE] {error_msg}")
                raise RuntimeError(error_msg)

            # This handles cases where pg_restore returns non-zero for non-critical errors
            # (like transaction_timeout) but the restore actually completed
            if result.returncode != 0:
                logger.warning(
                    f"[RESTORE] pg_restore returned non-zero exit code {result.returncode} but no critical errors detected. "
                    f"This may be due to non-critical errors like 'transaction_timeout'. "
                    f"Will verify restore completion through database validation."
                )
                logger.info("[RESTORE] Continuing after pg_restore warning...")

            try:
                logger.info(
                    "[RESTORE] pg_restore completed, proceeding to wait for connections..."
                )

                # This prevents "server closed the connection unexpectedly" errors

                logger.info(
                    "[RESTORE] Waiting for database connections to be released..."
                )

                time.sleep(2)

                # CRITICAL: Reset SQLAlchemy session after DROP SCHEMA CASCADE

                # The session is invalidated because all tables were dropped and recreated

                # We must close and remove the old session before using db.session again

                logger.info(
                    "[RESTORE] Resetting SQLAlchemy session after database restore"
                )

                try:
                    # Rollback any pending transactions first
                    db.session.rollback()

                except Exception:
                    # Rollback may fail if session is already closed - expected in some error scenarios
                    logger.debug(
                        "Database rollback failed during cleanup (session may be closed)"
                    )
                    pass

                try:
                    db.session.close()

                except Exception as e:
                    logger.warning(f"[RESTORE] Error closing session: {e}")

                try:
                    db.session.remove()

                except Exception as e:
                    logger.warning(f"[RESTORE] Error removing session: {e}")

                # Verify database connection is valid

                try:
                    # Test connection with a simple query
                    db.session.execute(sql_text("SELECT 1"))

                    db.session.commit()

                    logger.info(
                        "[RESTORE] Database connection verified after session reset"
                    )

                except Exception as e:
                    logger.error(
                        f"[RESTORE] Database connection test failed: {e}", exc_info=True
                    )

                    # Don't fail the restore, but log the error
                    db.session.rollback()

                    # Validate restore (AFTER session reset)

                    logger.info(
                        "[RESTORE] Starting database validation after session reset..."
                    )

                    postgres_url = self._get_postgres_url()

                    db_params = self._parse_postgres_url(postgres_url)

                    validation_result = self.validate_database(db_params)

                    logger.info(
                        f"[RESTORE] Validation result: valid={validation_result.get('valid', False)}, errors={validation_result.get('errors', [])}"
                    )

                    logger.info(
                        f"[RESTORE] Database validation completed. Valid: {validation_result.get('valid', False)}"
                    )

                    # Check for validation errors - this is CRITICAL

                    if not validation_result.get("valid", False):
                        errors = validation_result.get("errors", [])
                        if errors:
                            error_msg = (
                                f"Restore validation failed: {', '.join(errors)}"
                            )
                            logger.error(f"[RESTORE] {error_msg}")
                            raise RuntimeError(error_msg)

                    # Check if critical tables are empty (restore may have failed silently)

                    row_counts = validation_result.get("row_counts", {})

                    critical_tables = ["users", "vaultspaces", "files"]

                    empty_critical = [
                        table
                        for table in critical_tables
                        if row_counts.get(table, 0) == 0
                    ]

                    if empty_critical:
                        error_msg = f"Critical tables are empty after restore: {', '.join(empty_critical)}. Restore may have failed."
                        logger.error(f"[RESTORE] {error_msg}")
                        raise RuntimeError(error_msg)

                logger.info(
                    f"[RESTORE] Restore from backup {backup_id} completed successfully"
                )

                # Optionally sync backups from storage to database (non-blocking)
                # This ensures database cache is updated, but restore is valid even if this fails
                try:
                    logger.info(
                        "[RESTORE] Synchronizing backup records from storage (optional cache update)..."
                    )
                    sync_result = self.sync_backups_from_storage()
                    logger.info(
                        f"[RESTORE] Backup synchronization completed: "
                        f"added {sync_result['added']}, processed {sync_result['processed']}"
                    )
                except Exception as e:
                    # Log but don't fail - storage is source of truth
                    logger.warning(
                        f"[RESTORE] Failed to sync backups after restore (non-critical): {e}"
                    )

            except Exception as e:
                logger.error(
                    f"[RESTORE] Error during post-restore operations: {e}",
                    exc_info=True,
                )

                # Re-raise to be caught by the global except block

                raise

        except Exception as e:
            logger.error(
                f"[RESTORE] Unexpected error in restore_backup_radical: {e}",
                exc_info=True,
            )
            raise
        finally:
            # Clean up temporary decrypted file if it was created
            if is_encrypted and decrypted_backup_path != backup_path:
                try:
                    if decrypted_backup_path.exists():
                        decrypted_backup_path.unlink()
                        logger.debug(
                            f"[RESTORE] Cleaned up temporary decrypted file: {decrypted_backup_path}"
                        )
                except Exception as e:
                    logger.warning(
                        f"[RESTORE] Failed to clean up temporary decrypted file: {e}"
                    )

    def sync_backups_from_storage(self) -> dict[str, int]:
        """Synchronize database cache with backups from storage.

        Storage-first approach: discovers backups from storage and updates database
        cache. Database is optional - sync fails gracefully if DB is unavailable.

        Returns:
            Dictionary with counts of added and processed backups.
        """
        added_count = 0
        processed_count = 0

        try:
            # Discover backups from storage (source of truth)
            local_backups = self._discover_backups_from_storage()
            s3_backups = self._list_backups_from_s3()
            all_backups = local_backups + s3_backups

            processed_count = len(all_backups)

            # Get existing backup IDs from database (if available)
            existing_ids = set()
            try:
                existing_ids_result = db.session.query(DatabaseBackup.id).all()
                existing_ids = {str(b[0]) for b in existing_ids_result}
            except Exception as e:
                logger.debug(
                    f"[BACKUP SYNC] Database unavailable, skipping sync (non-critical): {e}"
                )
                return {"added": 0, "processed": processed_count}

            # Sync each backup to database cache
            for backup_dict in all_backups:
                backup_id = backup_dict.get("id")
                if not backup_id:
                    continue

                try:
                    if backup_id in existing_ids:
                        # Update existing record
                        backup_record = (
                            db.session.query(DatabaseBackup)
                            .filter_by(id=backup_id)
                            .first()
                        )
                        if backup_record:
                            metadata_dict = backup_dict.get("metadata", {})
                            backup_record.status = backup_dict.get(
                                "status", "completed"
                            )
                            backup_record.size_bytes = backup_dict.get("size_bytes", 0)
                            backup_record.checksum = backup_dict.get("checksum")
                            backup_record.backup_metadata = json.dumps(metadata_dict)
                    else:
                        # Create new record
                        created_at_str = backup_dict.get("created_at")
                        if created_at_str:
                            try:
                                created_at = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                            except (ValueError, AttributeError):
                                created_at = datetime.now(timezone.utc)
                        else:
                            created_at = datetime.now(timezone.utc)

                        new_record = DatabaseBackup(
                            id=backup_id,
                            created_at=created_at,
                            backup_type=backup_dict.get("backup_type", "manual"),
                            status=backup_dict.get("status", "completed"),
                            storage_location=backup_dict.get("storage_location", ""),
                            size_bytes=backup_dict.get("size_bytes", 0),
                            checksum=backup_dict.get("checksum"),
                            backup_metadata=json.dumps(backup_dict.get("metadata", {})),
                        )
                        db.session.add(new_record)
                        added_count += 1
                        existing_ids.add(backup_id)
                except Exception as e:
                    logger.debug(
                        f"[BACKUP SYNC] Failed to sync backup {backup_id} to database: {e}"
                    )
                    continue

            if added_count > 0:
                try:
                    db.session.commit()
                    logger.info(
                        f"[BACKUP SYNC] Successfully synchronized {added_count} backups to database cache"
                    )
                except Exception as e:
                    logger.warning(
                        f"[BACKUP SYNC] Failed to commit sync (non-critical): {e}"
                    )
                    try:
                        db.session.rollback()
                    except Exception:
                        pass

            return {"added": added_count, "processed": processed_count}

        except Exception as e:
            logger.warning(
                f"[BACKUP SYNC] Error synchronizing backups (non-critical): {e}"
            )
            # Don't raise - storage is source of truth
            return {"added": added_count, "processed": processed_count}

    def list_backups(self) -> list[dict[str, Any]]:
        """List all database backups from storage (storage-first approach).

        This method scans storage (local and S3) to discover backups by reading
        metadata.json files. Database is used only as optional cache.

        Returns:
            List of backup dictionaries with backup information
        """
        try:
            # Storage-first: discover backups from storage
            local_backups = self._discover_backups_from_storage()
            s3_backups = self._list_backups_from_s3()

            # Create a map of backup IDs from storage (source of truth)
            backup_map: dict[str, dict[str, Any]] = {}

            # Add local backups
            for backup in local_backups:
                backup_id = backup.get("id")
                if backup_id:
                    backup_map[backup_id] = backup

            # Merge S3 backups
            {b.get("id") for b in s3_backups if b.get("id")}
            for s3_backup in s3_backups:
                backup_id = s3_backup.get("id")
                if not backup_id:
                    continue

                if backup_id in backup_map:
                    # Backup exists in both local and S3
                    existing = backup_map[backup_id]
                    existing_metadata = existing.get("metadata", {})
                    storage_info = existing_metadata.get("storage", {})
                    storage_info["type"] = "both"
                    storage_info["s3_location"] = s3_backup.get("storage_location")
                    existing_metadata["storage"] = storage_info
                    existing["metadata"] = existing_metadata
                else:
                    # S3-only backup
                    backup_map[backup_id] = s3_backup

            # Optionally sync to database for caching (non-blocking)
            try:

                for backup_id, backup_dict in backup_map.items():
                    try:
                        backup_record = (
                            db.session.query(DatabaseBackup)
                            .filter_by(id=backup_id)
                            .first()
                        )
                        if backup_record:
                            # Update existing record with storage info
                            metadata_dict = backup_dict.get("metadata", {})
                            backup_record.status = backup_dict.get(
                                "status", "completed"
                            )
                            backup_record.size_bytes = backup_dict.get("size_bytes", 0)
                            backup_record.checksum = backup_dict.get("checksum")
                            backup_record.backup_metadata = json.dumps(metadata_dict)
                        else:
                            # Create new record from storage
                            created_at_str = backup_dict.get("created_at")
                            if created_at_str:
                                try:
                                    created_at = datetime.fromisoformat(
                                        created_at_str.replace("Z", "+00:00")
                                    )
                                except (ValueError, AttributeError):
                                    created_at = datetime.now(timezone.utc)
                            else:
                                created_at = datetime.now(timezone.utc)

                            new_record = DatabaseBackup(
                                id=backup_id,
                                created_at=created_at,
                                backup_type=backup_dict.get("backup_type", "manual"),
                                status=backup_dict.get("status", "completed"),
                                storage_location=backup_dict.get(
                                    "storage_location", ""
                                ),
                                size_bytes=backup_dict.get("size_bytes", 0),
                                checksum=backup_dict.get("checksum"),
                                backup_metadata=json.dumps(
                                    backup_dict.get("metadata", {})
                                ),
                            )
                            db.session.add(new_record)
                    except Exception as e:
                        logger.debug(
                            f"[BACKUP] Failed to sync backup {backup_id} to database (non-critical): {e}"
                        )
                        continue

                db.session.commit()
            except Exception as e:
                # Database sync failed, but that's OK - storage is source of truth
                logger.debug(f"[BACKUP] Database sync failed (non-critical): {e}")
                try:
                    db.session.rollback()
                except Exception:
                    # Rollback may fail if session is already closed - expected in some error scenarios
                    logger.debug("Database rollback failed (session may be closed)")

            # Convert map to sorted list
            result = list(backup_map.values())
            result.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return result
        except Exception as e:
            logger.error(f"[BACKUP] Error listing backups: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list backups: {str(e)}") from e

    def _read_s3_metadata(
        self, client: Any, bucket_name: str, s3_key: str
    ) -> dict[str, Any] | None:
        """Read backup metadata.json from S3.

        Args:
            client: S3 client
            bucket_name: S3 bucket name
            s3_key: S3 key for the dump file

        Returns:
            Metadata dictionary or None if not found or invalid
        """
        try:
            # Construct metadata key (replace .dump with .metadata.json)
            if s3_key.endswith(".dump"):
                metadata_key = s3_key[:-5] + ".metadata.json"
            else:
                metadata_key = s3_key + ".metadata.json"

            try:
                response = client.get_object(Bucket=bucket_name, Key=metadata_key)
                metadata_json = response["Body"].read().decode("utf-8")
                metadata = json.loads(metadata_json)
                return metadata
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code in ["NoSuchKey", "404"]:
                    # Metadata file doesn't exist, that's OK
                    return None
                raise

        except Exception as e:
            logger.debug(f"[BACKUP] Failed to read S3 metadata for {s3_key}: {e}")
            return None

    def _list_backups_from_s3(self) -> list[dict[str, Any]]:
        """List all database backups from S3 storage.

        Storage-first approach: reads metadata.json files from S3 when available.

        Returns:
            List of backup dictionaries from S3
        """
        backups = []
        try:
            from vault.services.external_storage_config_service import (
                ExternalStorageConfigService,
            )

            # Check if S3 is enabled first
            if not ExternalStorageConfigService.is_enabled(self.secret_key, self.app):
                return []

            from vault.services.external_storage_service import ExternalStorageService

            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if not client or not config:
                # S3 not configured, return empty list
                return []

            bucket_name = config.get("bucket_name")
            if not bucket_name:
                return []

            # List all files in database-backups/ prefix
            prefix = "database-backups/"
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    s3_key = obj["Key"]
                    filename = s3_key.split("/")[-1]

                    # Only process backup files
                    if not filename.startswith("backup_") or not filename.endswith(
                        ".dump"
                    ):
                        continue

                    try:

                        metadata = self._read_s3_metadata(client, bucket_name, s3_key)

                        if metadata:
                            # Use metadata.json as source of truth
                            backup_id = metadata.get("backup_id")
                            if not backup_id:
                                # Fallback: parse from filename
                                parts = Path(filename).stem.split("_")
                                if len(parts) >= 3:
                                    backup_id = parts[-1]
                                else:
                                    continue

                            # Validate UUID format
                            try:
                                uuid.UUID(backup_id)
                            except ValueError:
                                continue

                            file_info = metadata.get("file", {})
                            storage_info = metadata.get("storage", {})
                            validation_info = metadata.get("validation", {})

                            # Use storage_location from metadata (storage-first)
                            storage_location = storage_info.get("s3_location")
                            if not storage_location:
                                # Fallback: construct from bucket/key if metadata incomplete
                                storage_location = f"s3://{bucket_name}/{s3_key}"

                            backups.append(
                                {
                                    "id": backup_id,
                                    "created_at": metadata.get("created_at"),
                                    "backup_type": metadata.get(
                                        "backup_type", "manual"
                                    ),
                                    "status": (
                                        "completed"
                                        if validation_info.get("valid")
                                        else "failed"
                                    ),
                                    "storage_location": storage_location,
                                    "size_bytes": file_info.get("size_bytes"),
                                    "checksum": file_info.get("checksum"),
                                    "metadata": metadata,
                                }
                            )
                        else:
                            # Metadata.json missing - fallback to filename parsing
                            parts = Path(filename).stem.split("_")
                            if len(parts) < 3:
                                continue

                            backup_id = parts[-1]

                            # Validate UUID format
                            try:
                                uuid.UUID(backup_id)
                            except ValueError:
                                continue

                            # Extract timestamp
                            timestamp_str = f"{parts[1]}_{parts[2]}"
                            try:
                                created_at = datetime.strptime(
                                    timestamp_str, "%Y%m%d_%H%M%S"
                                )
                                created_at = created_at.replace(tzinfo=timezone.utc)
                            except ValueError:
                                # Fallback to S3 object last modified time
                                created_at = obj["LastModified"].replace(
                                    tzinfo=timezone.utc
                                )

                            size_bytes = obj.get("Size", 0)
                            s3_location = f"s3://{bucket_name}/{s3_key}"

                            # Calculate checksum by downloading file in streaming mode
                            checksum = None
                            try:
                                checksum = self._calculate_s3_checksum(
                                    client, bucket_name, s3_key
                                )
                            except Exception as e:
                                logger.warning(
                                    f"[BACKUP] Failed to calculate checksum for S3 backup {s3_key}: {e}"
                                )

                            backups.append(
                                {
                                    "id": backup_id,
                                    "created_at": created_at.isoformat(),
                                    "backup_type": "manual",
                                    "status": "completed",
                                    "storage_location": s3_location,
                                    "size_bytes": size_bytes,
                                    "checksum": checksum,
                                    "metadata": {
                                        "storage_type": "s3",
                                        "s3_location": s3_location,
                                        "metadata_missing": True,
                                    },
                                }
                            )
                    except Exception as e:
                        logger.warning(
                            f"[BACKUP] Failed to process S3 backup {s3_key}: {e}"
                        )
                        continue

        except Exception as e:
            logger.warning(f"[BACKUP] Error listing backups from S3: {e}")
            # Don't raise, just return what we have

        return backups

    def _read_backup_metadata(self, metadata_path: Path) -> dict[str, Any] | None:
        """Read backup metadata from metadata.json file.

        Args:
            metadata_path: Path to metadata.json file

        Returns:
            Metadata dictionary or None if file doesn't exist or is invalid
        """
        try:
            if not metadata_path.exists():
                return None

            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            logger.warning(
                f"[BACKUP] Failed to read metadata from {metadata_path}: {e}"
            )
            return None

    def _generate_metadata_for_existing_backup(
        self, backup_path: Path
    ) -> dict[str, Any] | None:
        """Generate metadata.json for an existing backup file that lacks metadata.

        This method is used for backward compatibility with backups created before
        the storage-first architecture was implemented.

        Args:
            backup_path: Path to backup dump file

        Returns:
            Metadata dictionary or None if generation fails
        """
        try:
            if not backup_path.exists():
                return None

            filename = backup_path.name
            # Parse filename: backup_{timestamp}_{uuid}.dump
            parts = Path(filename).stem.split("_")
            if len(parts) < 3:
                return None

            backup_id = parts[-1]

            # Validate UUID format
            try:
                uuid.UUID(backup_id)
            except ValueError:
                return None

            # Extract timestamp
            timestamp_str = f"{parts[1]}_{parts[2]}"
            try:
                created_at = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                created_at = created_at.replace(tzinfo=timezone.utc)
            except ValueError:
                # Fallback to file modification time
                created_at = datetime.fromtimestamp(
                    backup_path.stat().st_mtime, tz=timezone.utc
                )

            # Check if backup is encrypted
            is_encrypted = self.encryption.is_encrypted(backup_path)
            encryption_method = None

            # Calculate size and checksum (of encrypted file if encrypted)
            size_bytes = backup_path.stat().st_size
            checksum = self._calculate_checksum(backup_path)

            # Validate backup (need to decrypt if encrypted)
            if is_encrypted:
                # Create temporary decrypted file for validation
                import tempfile

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".dump"
                ) as temp_decrypted:
                    temp_decrypted_path = Path(temp_decrypted.name)
                try:
                    encryption_method = self.encryption.decrypt_file(
                        backup_path, temp_decrypted_path
                    )
                    validation_result = self.validate_backup(temp_decrypted_path)
                finally:
                    if temp_decrypted_path.exists():
                        temp_decrypted_path.unlink()
            else:
                validation_result = self.validate_backup(backup_path)

            # Get database info (may fail if DB unavailable, that's OK)
            db_params = {}
            try:
                postgres_url = self._get_postgres_url()
                db_params = self._parse_postgres_url(postgres_url)
            except Exception as e:
                logger.debug(
                    f"[BACKUP] Could not get DB params for metadata generation: {e}"
                )
                # Use defaults
                db_params = {
                    "host": "unknown",
                    "database": "unknown",
                }

            # Get PostgreSQL version (may fail, that's OK)
            postgres_version = self._get_postgres_version()

            # Build metadata dictionary
            metadata = {
                "backup_id": backup_id,
                "created_at": created_at.isoformat(),
                "backup_type": "manual",  # Assume manual for existing backups
                "database": {
                    "host": db_params.get("host", "unknown"),
                    "database": db_params.get("database", "unknown"),
                    "engine": "postgresql",
                    "version": postgres_version or "unknown",
                },
                "file": {
                    "size_bytes": size_bytes,
                    "checksum": checksum,
                    "checksum_algorithm": "sha256",
                    "format": "custom",
                    "compression": True,
                },
                "storage": {
                    "type": "local",
                    "local_path": str(backup_path),
                    "s3_location": None,
                },
                "validation": {
                    "valid": validation_result.get("valid", False),
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                    "method": "pg_restore_list",
                },
                "generated_on_demand": True,  # Flag to indicate this was generated
            }

            # Add encryption information if backup is encrypted
            if is_encrypted and encryption_method:
                metadata["encryption"] = {
                    "encrypted": True,
                    "method": encryption_method,
                }
            else:
                metadata["encryption"] = {
                    "encrypted": False,
                }

            # Write metadata.json file
            metadata_path = backup_path.with_suffix(".metadata.json")
            try:
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"[BACKUP] Generated metadata.json for existing backup {backup_id}"
                )
            except Exception as e:
                logger.warning(f"[BACKUP] Failed to write generated metadata.json: {e}")
                # Return metadata anyway, even if write failed

            return metadata

        except Exception as e:
            logger.warning(
                f"[BACKUP] Failed to generate metadata for {backup_path}: {e}"
            )
            return None

    def _discover_backups_from_storage(self) -> list[dict[str, Any]]:
        """Discover backups from local storage by scanning for dump files and reading metadata.json.

        Storage-first approach: reads metadata.json files to get complete backup information.
        If metadata.json is missing, generates it on-demand for backward compatibility.

        Returns:
            List of backup dictionaries from storage
        """
        backups = []
        try:
            # Check both possible backup directories
            backup_dirs = [self.backup_dir]
            data_backup_dir = Path("/data/backups/database")
            data_source_backup_dir = Path("/data-source/backups/database")

            # Add alternative directory if it exists and is different
            if self.backup_dir == data_source_backup_dir and data_backup_dir.exists():
                backup_dirs.append(data_backup_dir)
            elif self.backup_dir == data_backup_dir and data_source_backup_dir.exists():
                backup_dirs.append(data_source_backup_dir)

            # Find all local backup files from all directories
            backup_files = []
            for backup_dir in backup_dirs:
                if backup_dir.exists():
                    backup_files.extend(backup_dir.glob("backup_*.dump"))
                    # Also check for backup_restore_*.dump files
                    backup_files.extend(backup_dir.glob("backup_restore_*.dump"))

            for backup_file in backup_files:
                try:
                    # Look for companion metadata.json file
                    metadata_path = backup_file.with_suffix(".metadata.json")
                    metadata = self._read_backup_metadata(metadata_path)

                    if metadata:
                        # Use metadata.json as source of truth
                        backup_id = metadata.get("backup_id")
                        if not backup_id:
                            # Fallback: parse from filename
                            parts = Path(backup_file.name).stem.split("_")
                            if len(parts) >= 3:
                                backup_id = parts[-1]
                            else:
                                continue

                        # Validate UUID format
                        try:
                            uuid.UUID(backup_id)
                        except ValueError:
                            continue

                        # Build backup dict from metadata (storage-first: all data from metadata.json)
                        file_info = metadata.get("file", {})
                        storage_info = metadata.get("storage", {})
                        validation_info = metadata.get("validation", {})

                        # Determine storage_location from metadata
                        storage_location = None
                        if storage_info.get("s3_location"):
                            storage_location = storage_info.get("s3_location")
                        elif storage_info.get("local_path"):
                            storage_location = storage_info.get("local_path")
                        else:
                            # Fallback only if metadata is incomplete (shouldn't happen)
                            storage_location = str(backup_file)

                        backups.append(
                            {
                                "id": backup_id,
                                "created_at": metadata.get("created_at"),
                                "backup_type": metadata.get("backup_type", "manual"),
                                "status": (
                                    "completed"
                                    if validation_info.get("valid")
                                    else "failed"
                                ),
                                "storage_location": storage_location,
                                "size_bytes": file_info.get("size_bytes"),
                                "checksum": file_info.get("checksum"),
                                "metadata": metadata,
                            }
                        )
                    else:
                        # Metadata.json missing - generate on-demand for backward compatibility
                        logger.info(
                            f"[BACKUP] Metadata missing for {backup_file.name}, generating on-demand"
                        )
                        try:
                            generated_metadata = (
                                self._generate_metadata_for_existing_backup(backup_file)
                            )
                            if generated_metadata:
                                backup_id = generated_metadata.get("backup_id")
                                if backup_id:
                                    file_info = generated_metadata.get("file", {})
                                    storage_info = generated_metadata.get("storage", {})
                                    validation_info = generated_metadata.get(
                                        "validation", {}
                                    )

                                    # Use storage_location from generated metadata
                                    storage_location = storage_info.get("local_path")
                                    if not storage_location:
                                        storage_location = str(backup_file)

                                    backups.append(
                                        {
                                            "id": backup_id,
                                            "created_at": generated_metadata.get(
                                                "created_at"
                                            ),
                                            "backup_type": generated_metadata.get(
                                                "backup_type", "manual"
                                            ),
                                            "status": (
                                                "completed"
                                                if validation_info.get("valid")
                                                else "failed"
                                            ),
                                            "storage_location": storage_location,
                                            "size_bytes": file_info.get("size_bytes"),
                                            "checksum": file_info.get("checksum"),
                                            "metadata": generated_metadata,
                                        }
                                    )
                        except Exception as e:
                            logger.warning(
                                f"[BACKUP] Failed to generate metadata for {backup_file.name}: {e}"
                            )
                            # Fallback to basic info from filename
                            parts = Path(backup_file.name).stem.split("_")
                            if len(parts) >= 3:
                                backup_id = parts[-1]
                                try:
                                    uuid.UUID(backup_id)
                                    stat = backup_file.stat()
                                    timestamp_str = f"{parts[1]}_{parts[2]}"
                                    try:
                                        created_at = datetime.strptime(
                                            timestamp_str, "%Y%m%d_%H%M%S"
                                        )
                                        created_at = created_at.replace(
                                            tzinfo=timezone.utc
                                        )
                                    except ValueError:
                                        created_at = datetime.fromtimestamp(
                                            stat.st_mtime, tz=timezone.utc
                                        )

                                    backups.append(
                                        {
                                            "id": backup_id,
                                            "created_at": created_at.isoformat(),
                                            "backup_type": "manual",
                                            "status": "unknown",
                                            "storage_location": str(backup_file),
                                            "size_bytes": stat.st_size,
                                            "checksum": None,
                                            "metadata": {
                                                "storage_type": "local",
                                                "metadata_missing": True,
                                            },
                                        }
                                    )
                                except ValueError:
                                    continue

                except Exception as e:
                    logger.warning(
                        f"[BACKUP] Failed to process local backup {backup_file}: {e}"
                    )
                    continue

        except Exception as e:
            logger.warning(f"[BACKUP] Error discovering backups from storage: {e}")
            # Don't raise, just return what we have

        return backups

    def _list_backups_from_local(self) -> list[dict[str, Any]]:
        """List all database backups from local storage.

        Returns:
            List of backup dictionaries from local storage
        """
        backups = []
        try:
            if not self.backup_dir.exists():
                return []

            # Find all local backup files
            backup_files = list(self.backup_dir.glob("backup_*.dump"))

            for backup_file in backup_files:
                try:
                    stat = backup_file.stat()
                    filename = backup_file.name

                    # Parse filename: backup_{timestamp}_{uuid}.dump
                    parts = Path(filename).stem.split("_")
                    if len(parts) < 3:
                        continue

                    backup_id = parts[-1]

                    # Validate UUID format
                    try:
                        uuid.UUID(backup_id)
                    except ValueError:
                        continue

                    # Extract timestamp
                    timestamp_str = f"{parts[1]}_{parts[2]}"
                    try:
                        created_at = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    except ValueError:
                        # Fallback to file modification time
                        created_at = datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        )

                    size_bytes = stat.st_size

                    backups.append(
                        {
                            "id": backup_id,
                            "created_at": created_at.isoformat(),
                            "backup_type": "manual",
                            "status": "completed",
                            "storage_location": str(backup_file),
                            "size_bytes": size_bytes,
                            "checksum": None,  # Would need to calculate
                            "metadata": {
                                "storage_type": "local",
                                "synced_from_storage": True,
                                "sync_date": datetime.now(timezone.utc).isoformat(),
                            },
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"[BACKUP] Failed to process local backup {backup_file}: {e}"
                    )
                    continue

        except Exception as e:
            logger.warning(f"[BACKUP] Error listing backups from local storage: {e}")
            # Don't raise, just return what we have

        return backups

    def _delete_backup_from_storage(self, backup_id: str) -> bool:
        """Delete backup files from storage (dump and metadata.json).

        Storage-first approach: deletes from storage without database access.

        Args:
            backup_id: Backup ID to delete

        Returns:
            True if files were found and deleted, False otherwise
        """
        deleted_any = False

        # Find backup in storage
        backup_path, metadata_path = self._find_backup_by_id_in_storage(backup_id)

        # Delete local files
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
                logger.info(f"[BACKUP] Deleted local backup file: {backup_path}")
                deleted_any = True
            except Exception as e:
                logger.warning(f"[BACKUP] Failed to delete local backup file: {e}")

        if metadata_path and metadata_path.exists():
            try:
                metadata_path.unlink()
                logger.info(f"[BACKUP] Deleted local metadata file: {metadata_path}")
            except Exception as e:
                logger.warning(f"[BACKUP] Failed to delete local metadata file: {e}")

        # Delete from S3
        try:
            from vault.services.external_storage_service import ExternalStorageService

            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if client and config:
                bucket_name = config.get("bucket_name")
                if bucket_name:
                    # List S3 objects to find matching backup
                    prefix = "database-backups/backup_"
                    try:
                        response = client.list_objects_v2(
                            Bucket=bucket_name, Prefix=prefix
                        )

                        if "Contents" in response:
                            for obj in response["Contents"]:
                                s3_key = obj["Key"]
                                filename = s3_key.split("/")[-1]

                                # Check if this file contains the backup_id
                                if backup_id in filename:
                                    try:
                                        # Delete dump file
                                        if filename.endswith(".dump"):
                                            client.delete_object(
                                                Bucket=bucket_name, Key=s3_key
                                            )
                                            logger.info(
                                                f"[BACKUP] Deleted S3 backup file: {s3_key}"
                                            )
                                            deleted_any = True
                                        # Delete metadata file
                                        elif filename.endswith(".metadata.json"):
                                            client.delete_object(
                                                Bucket=bucket_name, Key=s3_key
                                            )
                                            logger.info(
                                                f"[BACKUP] Deleted S3 metadata file: {s3_key}"
                                            )
                                    except Exception as e:
                                        logger.warning(
                                            f"[BACKUP] Failed to delete S3 file {s3_key}: {e}"
                                        )
                    except Exception as e:
                        logger.debug(
                            f"[BACKUP] Error searching S3 for backup {backup_id}: {e}"
                        )
        except Exception as e:
            logger.debug(f"[BACKUP] Error accessing S3 for deletion: {e}")

        return deleted_any

    def delete_backup(self, backup_id: str) -> None:
        """Delete a backup from storage and optionally from database.

        Storage-first approach: deletes from storage first, then optionally from database cache.

        Args:
            backup_id: Backup ID to delete

        Raises:
            RuntimeError: If deletion fails
        """
        # Storage-first: delete from storage
        deleted_from_storage = self._delete_backup_from_storage(backup_id)

        if not deleted_from_storage:
            raise RuntimeError(f"Backup {backup_id} not found in storage (local or S3)")

        # Optionally delete from database cache (non-blocking)
        try:
            backup = db.session.query(DatabaseBackup).filter_by(id=backup_id).first()
            if backup:
                db.session.delete(backup)
                db.session.commit()
                logger.info(f"[BACKUP] Deleted backup record {backup_id} from database")
        except Exception as e:
            # Log but don't fail - storage deletion succeeded
            logger.warning(
                f"[BACKUP] Failed to delete backup record from database (non-critical): {e}"
            )
            try:
                db.session.rollback()
            except Exception:
                pass

    def _delete_from_s3(self, backup: DatabaseBackup) -> None:
        """Delete backup file from S3.

        Args:
            backup: DatabaseBackup object
        """
        try:
            from vault.services.external_storage_config_service import (
                ExternalStorageConfigService,
            )

            # Check if S3 is enabled first
            if not ExternalStorageConfigService.is_enabled(self.secret_key, self.app):
                return

            from vault.services.external_storage_service import ExternalStorageService

            storage_service = ExternalStorageService(self.secret_key, self.app)
            client = storage_service._get_client()
            config = storage_service._get_config()

            if not client or not config:
                logger.warning("[BACKUP] S3 configured but not available for deletion")
                return

            bucket_name = config.get("bucket_name")
            if not bucket_name:
                return

            # Determine S3 key
            s3_key = None

            metadata = {}
            if backup.backup_metadata:
                try:
                    metadata = json.loads(backup.backup_metadata)
                    s3_location = metadata.get("s3_location")
                    if s3_location and s3_location.startswith("s3://"):
                        # Extract key from s3://bucket/key/path
                        # Remove s3://
                        path_without_scheme = s3_location[5:]
                        # Remove bucket (if present in URL, though usually we construct it)
                        # Our format is s3://database-backups/filename usually (which is NOT s3://bucket/key)
                        # Wait, in create_backup: s3_key = f"database-backups/{backup_filename}"
                        # initial_storage_location = f"s3://{s3_key}"

                        s3_key = path_without_scheme
                except Exception:
                    # Error parsing S3 key from storage_location - expected for some formats
                    logger.debug("Failed to extract S3 key from storage_location")
                    pass

            # Fallback: check storage_location if it's an S3 URL
            if not s3_key and backup.storage_location.startswith("s3://"):
                s3_key = backup.storage_location[5:]

            # Fallback: construct from filename if we can assume standard naming
            if not s3_key:

                logger.warning(
                    f"Could not determine S3 key for backup {backup.id}, skipping S3 deletion"
                )
                return

            if s3_key:
                logger.info(f"[BACKUP] Deleting from S3: {s3_key}")
                client.delete_object(Bucket=bucket_name, Key=s3_key)

        except Exception as e:
            logger.warning(f"[BACKUP] Failed to delete from S3: {e}")
