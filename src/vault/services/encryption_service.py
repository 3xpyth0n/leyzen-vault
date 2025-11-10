"""Encryption service for managing hierarchical key encryption.

This service manages the encryption key hierarchy:
- user_master_key (derived from password, client-side only)
- vaultspace_key (random key, encrypted with user_master_key, stored encrypted)
- file_key (random key per file, encrypted with vaultspace_key, stored encrypted)

IMPORTANT: This service NEVER sees plaintext keys. All encryption/decryption
happens client-side. This service only manages encrypted key storage and metadata.
"""

from __future__ import annotations

import secrets
from typing import Any

from vault.database.schema import (
    File,
    FileKey,
    VaultSpace,
    VaultSpaceKey,
    db,
)


class EncryptionService:
    """Service for managing encrypted keys in the key hierarchy."""

    def create_vaultspace_key_entry(
        self,
        vaultspace_id: str,
        user_id: str,
        encrypted_key: str,
    ) -> VaultSpaceKey:
        """Create a VaultSpaceKey entry with encrypted key.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID who has access
            encrypted_key: Encrypted VaultSpace key (encrypted with user's master key)

        Returns:
            Created VaultSpaceKey object

        Raises:
            ValueError: If vaultspace or user not found, or if key already exists, or if key format is invalid
        """
        # Validate encrypted key format before storing
        if not self.validate_encrypted_key_format(encrypted_key):
            raise ValueError("Invalid encrypted key format")

        vaultspace = db.session.query(VaultSpace).filter_by(id=vaultspace_id).first()
        if not vaultspace:
            raise ValueError(f"VaultSpace {vaultspace_id} not found")

        # Check if key already exists
        existing = (
            db.session.query(VaultSpaceKey)
            .filter_by(vaultspace_id=vaultspace_id, user_id=user_id)
            .first()
        )
        if existing:
            raise ValueError(
                f"VaultSpaceKey already exists for user {user_id} and vaultspace {vaultspace_id}"
            )

        vaultspace_key = VaultSpaceKey(
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            encrypted_key=encrypted_key,
        )
        db.session.add(vaultspace_key)
        db.session.commit()
        return vaultspace_key

    def get_vaultspace_key(
        self, vaultspace_id: str, user_id: str
    ) -> VaultSpaceKey | None:
        """Get encrypted VaultSpace key for a user.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID

        Returns:
            VaultSpaceKey object if found, None otherwise
        """
        return (
            db.session.query(VaultSpaceKey)
            .filter_by(vaultspace_id=vaultspace_id, user_id=user_id)
            .first()
        )

    def get_all_vaultspace_keys(self, vaultspace_id: str) -> list[VaultSpaceKey]:
        """Get all encrypted VaultSpace keys for a VaultSpace.

        Args:
            vaultspace_id: VaultSpace ID

        Returns:
            List of VaultSpaceKey objects
        """
        return (
            db.session.query(VaultSpaceKey).filter_by(vaultspace_id=vaultspace_id).all()
        )

    def delete_vaultspace_key(self, vaultspace_id: str, user_id: str) -> bool:
        """Delete a VaultSpaceKey entry.

        Args:
            vaultspace_id: VaultSpace ID
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        vaultspace_key = (
            db.session.query(VaultSpaceKey)
            .filter_by(vaultspace_id=vaultspace_id, user_id=user_id)
            .first()
        )
        if not vaultspace_key:
            return False

        db.session.delete(vaultspace_key)
        db.session.commit()
        return True

    def create_file_key_entry(
        self,
        file_id: str,
        vaultspace_id: str,
        encrypted_key: str,
    ) -> FileKey:
        """Create a FileKey entry with encrypted key.

        Args:
            file_id: File ID
            vaultspace_id: VaultSpace ID (for validation)
            encrypted_key: Encrypted file key (encrypted with VaultSpace key)

        Returns:
            Created FileKey object

        Raises:
            ValueError: If file or vaultspace not found, or if key already exists, or if key format is invalid
        """
        # Validate encrypted key format before storing
        if not self.validate_encrypted_key_format(encrypted_key):
            raise ValueError("Invalid encrypted key format")

        file = db.session.query(File).filter_by(id=file_id).first()
        if not file:
            raise ValueError(f"File {file_id} not found")

        if file.vaultspace_id != vaultspace_id:
            raise ValueError(
                f"File {file_id} does not belong to VaultSpace {vaultspace_id}"
            )

        # Check if key already exists
        existing = (
            db.session.query(FileKey)
            .filter_by(file_id=file_id, vaultspace_id=vaultspace_id)
            .first()
        )
        if existing:
            raise ValueError(
                f"FileKey already exists for file {file_id} and vaultspace {vaultspace_id}"
            )

        file_key = FileKey(
            file_id=file_id,
            vaultspace_id=vaultspace_id,
            encrypted_key=encrypted_key,
        )
        db.session.add(file_key)
        db.session.commit()
        return file_key

    def get_file_key(self, file_id: str, vaultspace_id: str) -> FileKey | None:
        """Get encrypted FileKey for a file.

        Args:
            file_id: File ID
            vaultspace_id: VaultSpace ID

        Returns:
            FileKey object if found, None otherwise
        """
        return (
            db.session.query(FileKey)
            .filter_by(file_id=file_id, vaultspace_id=vaultspace_id)
            .first()
        )

    def get_all_file_keys(self, file_id: str) -> list[FileKey]:
        """Get all encrypted FileKeys for a file.

        Args:
            file_id: File ID

        Returns:
            List of FileKey objects
        """
        return db.session.query(FileKey).filter_by(file_id=file_id).all()

    def delete_file_key(self, file_id: str, vaultspace_id: str) -> bool:
        """Delete a FileKey entry.

        Args:
            file_id: File ID
            vaultspace_id: VaultSpace ID

        Returns:
            True if deleted, False if not found
        """
        file_key = (
            db.session.query(FileKey)
            .filter_by(file_id=file_id, vaultspace_id=vaultspace_id)
            .first()
        )
        if not file_key:
            return False

        db.session.delete(file_key)
        db.session.commit()
        return True

    def validate_encrypted_key_format(self, encrypted_key: str) -> bool:
        """Validate that encrypted key has a reasonable format.

        Validates AES-GCM encrypted key structure:
        - Must be valid base64
        - Must have minimum size for IV (12 bytes) + encrypted key (32 bytes) + tag (16 bytes) = 60 bytes
        - Must have maximum reasonable size (10KB)
        - Structure: IV (12 bytes) + ciphertext (variable) + tag (16 bytes)

        Args:
            encrypted_key: Encrypted key string (base64 encoded)

        Returns:
            True if format looks valid, False otherwise
        """
        if not encrypted_key:
            return False

        # Maximum size check (10KB base64 = ~7.5KB binary)
        if len(encrypted_key) > 10 * 1024:
            return False

        # Minimum size check: For a 32-byte key encrypted with AES-GCM
        # IV (12 bytes) + encrypted key (32 bytes) + tag (16 bytes) = 60 bytes minimum
        # Base64 encoding: 60 bytes * 4/3 = 80 characters minimum
        # We use 44 as absolute minimum (32 bytes = 44 base64 chars) but prefer 60+ bytes
        if len(encrypted_key) < 44:
            return False

        try:
            import base64

            # Decode base64 and validate structure
            decoded = base64.b64decode(encrypted_key, validate=True)

            # Minimum size: IV (12) + key (32) + tag (16) = 60 bytes
            if len(decoded) < 60:
                return False

            # Maximum reasonable size: IV (12) + key (512) + tag (16) = 540 bytes
            # This allows for larger keys but prevents DoS
            if len(decoded) > 10 * 1024:
                return False

            # Verify structure: first 12 bytes should be IV (non-zero check)
            # Last 16 bytes should be authentication tag
            if len(decoded) < 28:  # At least IV (12) + tag (16)
                return False

            # Check that we have at least some ciphertext between IV and tag
            # Minimum: IV (12) + 1 byte ciphertext + tag (16) = 29 bytes
            # But for a 32-byte key, we expect: IV (12) + 32 bytes + tag (16) = 60 bytes
            ciphertext_length = len(decoded) - 12 - 16
            if ciphertext_length < 1:
                return False

            # Verify IV is not all zeros (weak IV detection)
            iv = decoded[:12]
            if all(b == 0 for b in iv):
                return False

            # Verify IV has sufficient entropy (not all same byte)
            unique_bytes = len(set(iv))
            if unique_bytes < 4:  # Require at least 4 unique bytes in IV
                return False

            # Verify IV is not all ones or other predictable patterns
            if all(b == 0xFF for b in iv) or all(b == iv[0] for b in iv):
                return False

            # Extract authentication tag (last 16 bytes)
            tag = decoded[-16:]
            # Verify tag is not all zeros (weak tag detection)
            if all(b == 0 for b in tag):
                return False

            # Verify tag has sufficient entropy
            tag_unique_bytes = len(set(tag))
            if tag_unique_bytes < 8:  # Require at least 8 unique bytes in tag
                return False

            # Verify ciphertext (middle part) has reasonable entropy
            ciphertext = decoded[12:-16]
            if len(ciphertext) > 0:
                # Check that ciphertext is not all zeros or all same byte
                ciphertext_unique_bytes = len(set(ciphertext))
                # For a 32-byte key, we expect at least 16 unique bytes
                # But be lenient for smaller keys
                min_unique_bytes = max(8, min(len(ciphertext) // 4, 16))
                if ciphertext_unique_bytes < min_unique_bytes:
                    return False

                # Verify ciphertext is not all zeros
                if all(b == 0 for b in ciphertext):
                    return False

            # Additional validation: check for common weak patterns
            # Reject if IV starts with predictable patterns (like timestamps)
            # First 4 bytes should not be a common pattern
            if len(iv) >= 4:
                first_four = iv[:4]
                # Reject if first 4 bytes are all same
                if all(b == first_four[0] for b in first_four):
                    return False

            return True
        except Exception:
            return False
