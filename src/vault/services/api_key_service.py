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

    def __init__(self):
        """Initialize API key service."""
        self.hasher = PasswordHasher()
        self.key_prefix = "leyz_"

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
        user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
        if not user:
            raise ValueError("User not found or inactive")

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

        # Get all API keys and try to verify
        # Note: This is not the most efficient approach, but Argon2 verification
        # is designed to be slow to prevent brute force attacks
        api_keys = db.session.query(ApiKey).all()

        for api_key in api_keys:
            try:
                # Verify the key against the hash
                self.hasher.verify(api_key.key_hash, key)
                # Key is valid, update last_used_at
                api_key.last_used_at = datetime.now(timezone.utc)
                db.session.commit()

                # Get the user
                user = (
                    db.session.query(User)
                    .filter_by(id=api_key.user_id, is_active=True)
                    .first()
                )
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
