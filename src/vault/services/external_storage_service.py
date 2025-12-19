"""External storage service for S3-compatible storage."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from vault.services.external_storage_config_service import (
    ExternalStorageConfigService,
)

logger = logging.getLogger(__name__)


class _RateLimitedLogger:
    """Helper class to limit repetitive error logs."""

    def __init__(self, max_logs_per_minute: int = 5):
        """Initialize rate-limited logger.

        Args:
            max_logs_per_minute: Maximum number of identical error messages to log per minute
        """
        self._max_logs_per_minute = max_logs_per_minute
        self._log_counts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def should_log(self, message: str) -> bool:
        """Check if a message should be logged based on rate limiting.

        Args:
            message: The error message to potentially log

        Returns:
            True if the message should be logged, False otherwise
        """
        current_time = time.time()
        one_minute_ago = current_time - 60

        with self._lock:
            # Clean old entries
            self._log_counts[message] = [
                t for t in self._log_counts[message] if t > one_minute_ago
            ]

            # Check if we've exceeded the limit
            if len(self._log_counts[message]) >= self._max_logs_per_minute:
                return False

            # Record this log attempt
            self._log_counts[message].append(current_time)
            return True

    def log_error(self, message: str) -> None:
        """Log an error message if rate limiting allows it.

        Args:
            message: The error message to log
        """
        if self.should_log(message):
            logger.error(message)


_rate_limited_logger = _RateLimitedLogger(max_logs_per_minute=5)


class ExternalStorageService:
    """Service for managing external storage S3 operations."""

    def __init__(self, secret_key: str, app: Any):
        """Initialize external storage service.

        Args:
            secret_key: SECRET_KEY for decrypting configuration
            app: Flask app instance
        """
        self.secret_key = secret_key
        self.app = app
        self._client = None
        self._bucket_name = None
        self._config = None

    def _get_config(self) -> dict[str, Any] | None:
        """Get S3 configuration from SystemSecrets.

        Returns:
            Configuration dictionary or None if not configured
        """
        if self._config is None:
            self._config = ExternalStorageConfigService.get_config(
                self.secret_key, self.app
            )
        return self._config

    def _get_client(self):
        """Get or create S3 client with automatic addressing style fallback.

        Tries virtual-hosted-style first (default for AWS, IDrive, etc.),
        then falls back to path-style if bucket detection fails (required for Cloudflare R2).

        Returns:
            boto3 S3 client instance
        """
        if self._client is not None:
            return self._client

        config = self._get_config()
        if not config or not config.get("enabled", False):
            raise RuntimeError("External storage S3 is not enabled")

        # Get configuration values
        endpoint_url = config.get("endpoint_url")
        access_key_id = config.get("access_key_id")
        secret_access_key = config.get("secret_access_key")
        region = config.get("region", "us-east-1")
        use_ssl = config.get("use_ssl", True)
        self._bucket_name = config.get("bucket_name")
        explicit_addressing_style = config.get(
            "addressing_style"
        )  # Optional: "path" or "virtual"

        if not access_key_id or not secret_access_key or not self._bucket_name:
            raise RuntimeError("S3 configuration is incomplete")

        # Create base S3 client configuration
        client_config = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "region_name": region,
        }

        if endpoint_url:
            client_config["endpoint_url"] = endpoint_url

        if not use_ssl:
            client_config["use_ssl"] = False

        # Determine addressing style to use
        # Check if addressing_style is already stored in config (persisted from previous runs)
        stored_addressing_style = config.get("addressing_style")
        addressing_style = None
        if explicit_addressing_style:
            # User explicitly configured addressing style
            addressing_style = explicit_addressing_style
            logger.info(
                f"Using explicit addressing style: {addressing_style} for bucket {self._bucket_name}"
            )
        elif stored_addressing_style:
            # Use stored addressing style from database (persisted from previous detection)
            addressing_style = stored_addressing_style
            logger.debug(
                f"Using stored addressing style: {addressing_style} for bucket {self._bucket_name}"
            )
        else:
            # Try virtual-hosted-style first (default for AWS, IDrive, etc.)
            addressing_style = "virtual"
            logger.debug(
                f"Trying default virtual-hosted-style for bucket {self._bucket_name}"
            )

        # Create client with appropriate addressing style
        if addressing_style == "path":
            boto_config = Config(s3={"addressing_style": "path"})
            self._client = boto3.client("s3", config=boto_config, **client_config)
        else:
            # Default: virtual-hosted-style (or explicit "virtual")
            self._client = boto3.client("s3", **client_config)

        # Test bucket access and fallback if needed
        if not explicit_addressing_style and not stored_addressing_style:
            try:
                # Test if bucket is accessible with current addressing style
                self._client.head_bucket(Bucket=self._bucket_name)
                # Success: persist the working style to database
                self._persist_addressing_style(addressing_style)
                logger.info(
                    f"Successfully connected to bucket {self._bucket_name} using {addressing_style}-style addressing"
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchBucket" and addressing_style == "virtual":
                    # Bucket not found with virtual-hosted-style, try path-style
                    logger.info(
                        f"Bucket {self._bucket_name} not found with virtual-hosted-style, trying path-style fallback"
                    )
                    boto_config = Config(s3={"addressing_style": "path"})
                    self._client = boto3.client(
                        "s3", config=boto_config, **client_config
                    )
                    try:
                        self._client.head_bucket(Bucket=self._bucket_name)
                        # Success with path-style: persist it to database
                        self._persist_addressing_style("path")
                        logger.info(
                            f"Successfully connected to bucket {self._bucket_name} using path-style addressing (fallback)"
                        )
                    except ClientError as fallback_error:
                        # Path-style also failed, raise original error
                        error_code = fallback_error.response.get("Error", {}).get(
                            "Code", "Unknown"
                        )
                        error_msg = fallback_error.response.get("Error", {}).get(
                            "Message", str(fallback_error)
                        )
                        logger.error(
                            f"Failed to connect to bucket {self._bucket_name} with both virtual-hosted-style and path-style: {error_code} - {error_msg}"
                        )
                        raise RuntimeError(
                            f"S3 bucket {self._bucket_name} not accessible: {error_code} - {error_msg}"
                        ) from fallback_error
                else:
                    # Other error (not NoSuchBucket), re-raise
                    raise

        return self._client

    def _persist_addressing_style(self, addressing_style: str) -> None:
        """Persist addressing style to database configuration.

        Args:
            addressing_style: The addressing style to persist ("virtual" or "path")
        """
        try:
            config = self._get_config()
            if not config:
                return

            # Update config with addressing style
            config["addressing_style"] = addressing_style

            # Persist to database
            ExternalStorageConfigService.store_config(self.secret_key, config, self.app)
            # Invalidate cache to ensure next _get_config() call reads fresh data from DB
            self._config = None
            logger.debug(
                f"Persisted addressing style '{addressing_style}' to database configuration"
            )
        except Exception as e:
            # Log error but don't fail - addressing style will be detected again on next run
            logger.warning(
                f"Failed to persist addressing style to database: {e}. "
                f"It will be detected again on next connection."
            )

    def test_connection(self) -> tuple[bool, str | None]:
        """Test S3 connection with automatic addressing style fallback.

        This method will automatically try virtual-hosted-style first,
        then fallback to path-style if bucket detection fails.

        Returns:
            Tuple of (success, error_message). If successful, error_message is None.
        """
        # Reset client to force fresh connection test with fallback
        old_client = self._client
        self._client = None
        # Invalidate cached config to force reload (so we get fresh addressing_style from DB)
        self._config = None

        try:
            # _get_client() will automatically test bucket access and fallback if needed
            client = self._get_client()
            # Additional verification: try head_bucket again to ensure it works
            client.head_bucket(Bucket=self._bucket_name)
            return True, None
        except ClientError as e:
            # Restore previous client state on error
            self._client = old_client
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            return False, f"S3 connection failed ({error_code}): {error_msg}"
        except BotoCoreError as e:
            # Restore previous client state on error
            self._client = old_client
            return False, f"S3 connection error: {str(e)}"
        except Exception as e:
            # Restore previous client state on error
            self._client = old_client
            return False, f"Unexpected error testing S3 connection: {str(e)}"

    def _get_s3_key(self, file_id: str, is_thumbnail: bool = False) -> str:
        """Get S3 key for a file.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            S3 key string
        """
        if is_thumbnail:
            return f"thumbnails/{file_id}"
        return f"files/{file_id}"

    def save_file(
        self, file_id: str, encrypted_data: bytes, is_thumbnail: bool = False
    ) -> str:
        """Save encrypted file data to S3.

        Args:
            file_id: File identifier
            encrypted_data: Encrypted file data to save
            is_thumbnail: Whether this is a thumbnail

        Returns:
            S3 key of the saved file

        Raises:
            IOError: If upload fails
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            # Compute hash for metadata
            file_hash = hashlib.sha256(encrypted_data).hexdigest()

            # Upload to S3
            client.put_object(
                Bucket=self._bucket_name,
                Key=s3_key,
                Body=encrypted_data,
                Metadata={
                    "file_id": file_id,
                    "file_hash": file_hash,
                    "file_size": str(len(encrypted_data)),
                },
            )

            logger.info(f"Successfully uploaded file {file_id} to S3 (key: {s3_key})")
            return s3_key
        except ClientError as e:
            error_msg = f"Failed to upload file {file_id} to S3: {e}"
            logger.error(error_msg)
            raise IOError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error uploading file {file_id} to S3: {e}"
            logger.error(error_msg)
            raise IOError(error_msg) from e

    def read_file(self, file_id: str, is_thumbnail: bool = False) -> bytes:
        """Read encrypted file data from S3.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            Encrypted file data

        Raises:
            FileNotFoundError: If file not found in S3
            IOError: If download fails
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            response = client.get_object(Bucket=self._bucket_name, Key=s3_key)
            data = response["Body"].read()
            logger.debug(f"Successfully downloaded file {file_id} from S3")
            return data
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise FileNotFoundError(f"File {file_id} not found in S3") from e
            error_msg = f"Failed to download file {file_id} from S3: {e}"
            logger.error(error_msg)
            raise IOError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error downloading file {file_id} from S3: {e}"
            _rate_limited_logger.log_error(error_msg)
            raise IOError(error_msg) from e

    def delete_file(self, file_id: str, is_thumbnail: bool = False) -> bool:
        """Delete a file from S3.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            True if deleted, False if not found
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            client.delete_object(Bucket=self._bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted file {file_id} from S3")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"File {file_id} not found in S3 for deletion")
                return False
            error_msg = f"Failed to delete file {file_id} from S3: {e}"
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error deleting file {file_id} from S3: {e}"
            _rate_limited_logger.log_error(error_msg)
            return False

    def file_exists(self, file_id: str, is_thumbnail: bool = False) -> bool:
        """Check if a file exists in S3.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            True if file exists, False otherwise
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            client.head_object(Bucket=self._bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404" or error_code == "NoSuchKey":
                return False
            # Other errors - log but return False
            logger.debug(f"Error checking file existence in S3: {e}")
            return False
        except Exception as e:
            logger.debug(f"Unexpected error checking file existence in S3: {e}")
            return False

    def get_file_metadata(
        self, file_id: str, is_thumbnail: bool = False
    ) -> dict[str, Any] | None:
        """Get file metadata from S3.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            Dictionary with metadata (LastModified, ContentLength, etc.) or None if file doesn't exist
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            response = client.head_object(Bucket=self._bucket_name, Key=s3_key)
            # boto3 head_object() returns a dict with LastModified as a datetime object
            # LastModified is a native S3 metadata field, not in the custom Metadata dict
            # Access it directly from the response
            last_modified = response.get("LastModified")

            if last_modified is None:
                response_keys = (
                    list(response.keys()) if hasattr(response, "keys") else "N/A"
                )
                # Also check Metadata (custom metadata) vs native response fields
                custom_metadata = response.get("Metadata", {})
                logger.debug(
                    f"get_file_metadata: LastModified not found in response for {s3_key}, "
                    f"response keys: {response_keys}, "
                    f"custom Metadata keys: {list(custom_metadata.keys()) if custom_metadata else 'None'}, "
                    f"response type: {type(response)}, "
                    f"response repr (first 500 chars): {str(response)[:500]}"
                )
                # Try direct access (boto3 response objects support both dict and attribute access)
                try:
                    last_modified = response["LastModified"]
                except (KeyError, TypeError):
                    try:
                        last_modified = getattr(response, "LastModified", None)
                    except Exception:
                        pass

            return {
                "LastModified": last_modified,
                "ContentLength": response.get("ContentLength"),
                "ETag": response.get("ETag"),
                "ContentType": response.get("ContentType"),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404" or error_code == "NoSuchKey":
                return None
            # Other errors - log and return None
            logger.debug(f"Error getting file metadata from S3: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error getting file metadata from S3: {e}")
            return None

    def list_files(self, prefix: str = "files/", max_keys: int = 1000) -> list[str]:
        """List files in S3 with given prefix.

        Args:
            prefix: S3 key prefix (default: "files/")
            max_keys: Maximum number of keys to return

        Returns:
            List of S3 keys
        """
        client = self._get_client()
        s3_keys = []

        try:
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self._bucket_name, Prefix=prefix, MaxKeys=max_keys
            )

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        s3_keys.append(obj["Key"])

            return s3_keys
        except Exception as e:
            logger.error(f"Error listing files in S3: {e}")
            return []

    def get_file_metadata(
        self, file_id: str, is_thumbnail: bool = False
    ) -> dict[str, Any] | None:
        """Get file metadata from S3.

        Args:
            file_id: File identifier
            is_thumbnail: Whether this is a thumbnail

        Returns:
            Dictionary with metadata or None if not found
        """
        client = self._get_client()
        s3_key = self._get_s3_key(file_id, is_thumbnail)

        try:
            response = client.head_object(Bucket=self._bucket_name, Key=s3_key)
            metadata = response.get("Metadata", {})
            return {
                "file_id": metadata.get("file_id", file_id),
                "file_hash": metadata.get("file_hash", ""),
                "file_size": int(
                    metadata.get("file_size", response.get("ContentLength", 0))
                ),
                "last_modified": response.get("LastModified"),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404" or error_code == "NoSuchKey":
                return None
            logger.debug(f"Error getting file metadata from S3: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error getting file metadata from S3: {e}")
            return None

    def compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of encrypted data.

        Args:
            data: Data to hash

        Returns:
            SHA-256 hash in hex format
        """
        return hashlib.sha256(data).hexdigest()

    def verify_file_integrity(
        self, file_id: str, expected_hash: str, is_thumbnail: bool = False
    ) -> tuple[bool, str | None]:
        """Verify file integrity by comparing current hash with expected hash.

        Args:
            file_id: The file ID to verify
            expected_hash: The expected SHA-256 hash of the encrypted file
            is_thumbnail: Whether this is a thumbnail

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
            If invalid or file not found, error_message contains the reason.
        """
        try:
            encrypted_data = self.read_file(file_id, is_thumbnail)
            current_hash = self.compute_hash(encrypted_data)

            if current_hash != expected_hash:
                return (
                    False,
                    f"Hash mismatch: expected {expected_hash[:16]}..., got {current_hash[:16]}...",
                )

            return True, None
        except FileNotFoundError:
            return False, "File not found"
        except Exception as exc:
            return False, f"Error during integrity check: {exc}"


__all__ = ["ExternalStorageService"]
