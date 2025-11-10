"""Key management service for user and folder encryption keys."""

from __future__ import annotations

import hashlib
import secrets
from typing import Protocol

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class KeyDerivation(Protocol):
    """Protocol for key derivation functions."""

    def derive(self, master_key: bytes, info: bytes) -> bytes:
        """Derive a key from master key using info."""
        ...


class PBKDF2Derivation:
    """PBKDF2-based key derivation for user master keys."""

    def __init__(self, iterations: int = 600000):
        """Initialize PBKDF2 derivation.

        Args:
            iterations: Number of iterations (default: 600000)
        """
        self.iterations = iterations

    def derive(self, password: str, salt: bytes) -> bytes:
        """Derive master key from password using PBKDF2.

        Args:
            password: User password
            salt: Salt bytes

        Returns:
            Derived master key (32 bytes)
        """
        import hashlib

        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.iterations, dklen=32
        )


class HKDFDerivation:
    """HKDF-based key derivation for folder keys."""

    def __init__(self, hash_algorithm: str = "sha256", salt: bytes | None = None):
        """Initialize HKDF derivation.

        Args:
            hash_algorithm: Hash algorithm to use (default: sha256)
            salt: Optional salt bytes. If None, will be derived from master key.
        """
        self.hash_algorithm = hash_algorithm
        # Store static salt if provided, otherwise will be derived dynamically
        self._static_salt = salt

    def derive(
        self, master_key: bytes, info: bytes, user_salt: bytes | None = None
    ) -> bytes:
        """Derive a key from master key using HKDF.

        Args:
            master_key: Master key (32 bytes)
            info: Context information (folder path, etc.)
            user_salt: Optional user-specific salt (derived if not provided)

        Returns:
            Derived key (32 bytes)
        """
        # Derive a unique salt if not provided
        if user_salt is None:
            # Derive salt from master key and a fixed context
            # This ensures each user gets a unique salt while maintaining determinism
            salt_context = b"leyzen-vault-hkdf-salt-context-v2"
            user_salt = hashlib.sha256(master_key + salt_context).digest()
        elif self._static_salt:
            # Use static salt if provided during initialization
            user_salt = self._static_salt

        hash_algorithm = hashes.SHA256()
        if self.hash_algorithm == "sha512":
            hash_algorithm = hashes.SHA512()

        kdf = HKDF(
            algorithm=hash_algorithm,
            length=32,  # 32 bytes = 256 bits
            salt=user_salt,
            info=info,
            backend=default_backend(),
        )

        return kdf.derive(master_key)


class KeyManager:
    """Manages encryption keys for users and folders."""

    def __init__(self):
        """Initialize key manager."""
        self.pbkdf2 = PBKDF2Derivation()
        self.hkdf = HKDFDerivation()

    def derive_user_master_key(
        self, password: str, salt: bytes | None = None
    ) -> tuple[bytes, bytes]:
        """Derive user master key from password.

        Args:
            password: User password
            salt: Optional salt (generated if None)

        Returns:
            Tuple of (master_key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(32)

        master_key = self.pbkdf2.derive(password, salt)
        return master_key, salt

    def derive_folder_key(self, master_key: bytes, folder_path: list[str]) -> bytes:
        """Derive folder key from master key and folder path.

        Args:
            master_key: User master key
            folder_path: List of folder IDs from root to target folder

        Returns:
            Derived folder key
        """
        # Create info from folder path
        path_string = "/".join(folder_path)
        info = f"folder:{path_string}".encode("utf-8")
        # Pass None for user_salt, will be derived automatically
        return self.hkdf.derive(master_key, info, user_salt=None)

    def derive_file_key(self, folder_key: bytes, file_id: str) -> bytes:
        """Derive file encryption key from folder key.

        Args:
            folder_key: Folder encryption key
            file_id: File ID

        Returns:
            Derived file key
        """
        info = f"file:{file_id}".encode("utf-8")
        # Pass None for user_salt, will be derived automatically
        return self.hkdf.derive(folder_key, info, user_salt=None)

    def generate_salt(self) -> bytes:
        """Generate a random salt for key derivation.

        Returns:
            Random salt bytes (32 bytes)
        """
        return secrets.token_bytes(32)


# Global key manager instance
_key_manager: KeyManager | None = None


def get_key_manager() -> KeyManager:
    """Get the global key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


__all__ = ["KeyManager", "get_key_manager", "PBKDF2Derivation", "HKDFDerivation"]
