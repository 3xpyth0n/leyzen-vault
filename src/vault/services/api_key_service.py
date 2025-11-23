"""API key service for Leyzen Vault."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from vault.database.schema import ApiKey, User, db


class ApiKeyService:
    """Service for API key management."""

    def __init__(self, secret_key: str | None = None):
        """Initialize API key service.

        The key prefix is derived deterministically from SECRET_KEY using HMAC.
        This ensures all instances using the same SECRET_KEY generate the same prefix,
        allowing API keys to work across instances without requiring prefix sharing.

        Args:
            secret_key: The SECRET_KEY to derive the prefix from. If None, tries to get from Flask config.
        """
        import os
        import hmac
        import hashlib

        self.hasher = PasswordHasher()

        # Get SECRET_KEY from parameter or Flask config
        if not secret_key:
            try:
                from flask import current_app

                secret_key = current_app.config.get("SECRET_KEY", "")
            except RuntimeError:
                # Not in Flask context, try environment variable
                secret_key = os.environ.get("SECRET_KEY", "")

        if secret_key:
            # SECURITY: Derive deterministic prefix from SECRET_KEY using HMAC
            # This ensures all instances with the same SECRET_KEY use the same prefix
            context = b"api-key-prefix-v1"
            prefix_hash = hmac.new(
                secret_key.encode(), context, hashlib.sha256
            ).hexdigest()[:8]
            self.key_prefix = f"leyz_{prefix_hash}_"
        else:
            # Fallback: use environment variable if set
            prefix_env = os.environ.get("API_KEY_PREFIX", "")
            if prefix_env:
                self.key_prefix = prefix_env
            else:
                # Last resort: generate random prefix (not recommended)
                import warnings

                warnings.warn(
                    "SECURITY WARNING: SECRET_KEY not available for API key prefix derivation. "
                    "Using random prefix. API keys may not work across instances. "
                    "Set SECRET_KEY in environment or Flask config.",
                    UserWarning,
                )
                random_prefix = (
                    secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
                )
                self.key_prefix = f"leyz_{random_prefix}_"

    def generate_api_key(self, user_id: str, name: str) -> tuple[ApiKey, str]:
        """Generate a new API key for a user.

        Args:
            user_id: User ID to generate key for
            name: Name/description for the API key

        Returns:
            Tuple of (ApiKey object, plaintext key string)
            The plaintext key should be shown to the user once and never stored

        Raises:
            ValueError: If user doesn't exist or name is invalid
        """
        # Validate user exists
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError("User not found")

        # Validate name
        if not name or not name.strip():
            raise ValueError("API key name is required")
        name = name.strip()

        # Generate a secure random key
        # Format: leyz_<random_base64>
        random_bytes = secrets.token_bytes(32)  # 32 bytes = 256 bits
        # Use URL-safe base64 encoding for the key
        import base64

        key_suffix = base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")
        plaintext_key = f"{self.key_prefix}{key_suffix}"

        # Hash the key before storing (using Argon2 like passwords)
        key_hash = self.hasher.hash(plaintext_key)

        # Extract prefix for display (first 8 chars of suffix)
        key_prefix_display = f"{self.key_prefix}{key_suffix[:8]}..."

        # Create API key record
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix_display,
        )
        db.session.add(api_key)
        db.session.commit()

        return api_key, plaintext_key

    def revoke_api_key(self, api_key_id: str) -> None:
        """Revoke (delete) an API key.

        Args:
            api_key_id: API key ID to revoke

        Raises:
            ValueError: If API key doesn't exist
        """
        api_key = db.session.query(ApiKey).filter_by(id=api_key_id).first()
        if not api_key:
            raise ValueError("API key not found")

        # Delete the key (hard delete, no soft delete)
        db.session.delete(api_key)
        db.session.commit()

    def verify_api_key(self, key: str) -> User | None:
        """Verify an API key and return the associated user.

        Args:
            key: Plaintext API key to verify

        Returns:
            User object if key is valid, None otherwise
        """
        if not key or not key.startswith(self.key_prefix):
            return None

        # Extract prefix for filtering (prefix + first 8 chars of suffix)
        # This allows us to filter database queries before expensive Argon2 verification
        if len(key) < len(self.key_prefix) + 8:
            return None

        prefix_to_match = key[: len(self.key_prefix) + 8] + "..."

        # Filter API keys by prefix first to reduce the number of Argon2 verifications
        # This significantly improves performance when there are many API keys
        api_keys = (
            db.session.query(ApiKey)
            .filter(ApiKey.key_prefix.like(prefix_to_match))
            .all()
        )

        # Verify each candidate key with Argon2
        # Argon2 verification is intentionally slow to prevent brute force attacks
        for api_key in api_keys:
            try:
                # Verify the key against the hash
                self.hasher.verify(api_key.key_hash, key)
                # Key is valid, update last_used_at
                api_key.last_used_at = datetime.now(timezone.utc)
                db.session.commit()

                # Get the user
                user = db.session.query(User).filter_by(id=api_key.user_id).first()
                return user
            except VerifyMismatchError:
                # Key doesn't match this hash, continue to next
                continue

        # No matching key found
        return None

    def list_user_api_keys(self, user_id: str) -> list[ApiKey]:
        """List all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of ApiKey objects for the user
        """
        return (
            db.session.query(ApiKey)
            .filter_by(user_id=user_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    def list_all_api_keys(self) -> list[ApiKey]:
        """List all API keys in the system.

        Returns:
            List of all ApiKey objects
        """
        return db.session.query(ApiKey).order_by(ApiKey.created_at.desc()).all()

    def update_last_used(self, api_key_id: str) -> None:
        """Update the last_used_at timestamp for an API key.

        Args:
            api_key_id: API key ID
        """
        api_key = db.session.query(ApiKey).filter_by(id=api_key_id).first()
        if api_key:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.session.commit()
