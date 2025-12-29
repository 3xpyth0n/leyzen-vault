"""Two-Factor Authentication (TOTP) service for Leyzen Vault."""

from __future__ import annotations

import base64
import io
import json
import secrets

import pyotp
import qrcode
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from vault.utils.safe_json import safe_json_loads


class TOTPService:
    """Service for managing Two-Factor Authentication (TOTP).

    This service implements RFC 6238 (TOTP: Time-Based One-Time Password Algorithm)
    for optional two-factor authentication. Key features:

    - Generate TOTP secrets (base32 encoded)
    - Generate QR codes for easy setup with authenticator apps
    - Verify TOTP tokens with configurable time window
    - Generate and verify backup recovery codes
    - Encrypt/decrypt TOTP secrets for secure storage

    Security notes:
    - TOTP secrets are encrypted before storage in the database
    - Backup codes are hashed before storage (one-time use)
    - Time window allows for clock drift (default: 1 period = 30s tolerance)
    """

    def __init__(self, encryption_key: bytes):
        """Initialize TOTP service.

        Args:
            encryption_key: Secret key for encrypting TOTP secrets (32 bytes)
        """
        if len(encryption_key) != 32:
            raise ValueError("Encryption key must be 32 bytes")

        # Derive Fernet key from encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"leyzen-vault-totp-service-v1",
            iterations=100000,
            backend=default_backend(),
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(encryption_key))
        self.cipher = Fernet(fernet_key)
        # Cache for used TOTP tokens to prevent reuse (token -> timestamp)
        # Tokens expire after 3 minutes (6 time periods)
        self._used_tokens: dict[str, float] = {}
        import time

        self._time = time

    def generate_secret(self) -> str:
        """Generate a new TOTP secret.

        Returns:
            Base32-encoded secret (32 characters)
        """
        return pyotp.random_base32()

    def generate_provisioning_uri(
        self, secret: str, email: str, issuer: str = "Leyzen Vault"
    ) -> str:
        """Generate provisioning URI for QR code.

        Args:
            secret: TOTP secret (base32)
            email: User's email address
            issuer: Service name (default: Leyzen Vault)

        Returns:
            otpauth:// URI for authenticator apps
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=issuer)

    def generate_qr_code(self, provisioning_uri: str) -> str:
        """Generate QR code as base64-encoded PNG image.

        Args:
            provisioning_uri: otpauth:// URI

        Returns:
            Base64-encoded PNG image data (data URI format)
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return f"data:image/png;base64,{img_base64}"

    def verify_token(self, secret: str, token: str, window: int = 0) -> bool:
        """Verify a TOTP token.

        Args:
            secret: TOTP secret (base32)
            token: 6-digit TOTP token from user
            window: Number of time periods to check before/after current
                   (default: 0 = no tolerance, exact match only)

        Returns:
            True if token is valid, False otherwise
        """
        if not token or not token.isdigit() or len(token) != 6:
            return False

        # Check if token was already used (replay protection)
        current_time = self._time.time()
        cache_key = f"{secret}:{token}"

        # Clean up expired entries (older than 3 minutes)
        expired_keys = [
            k
            for k, ts in self._used_tokens.items()
            if current_time - ts > 180  # 3 minutes
        ]
        for k in expired_keys:
            del self._used_tokens[k]

        # Check if token was recently used
        if cache_key in self._used_tokens:
            # Token was already used - reject to prevent replay
            return False

        totp = pyotp.TOTP(secret)
        is_valid = totp.verify(token, valid_window=window)

        if is_valid:
            self._used_tokens[cache_key] = current_time

        return is_valid

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup recovery codes.

        Args:
            count: Number of codes to generate (default: 10)

        Returns:
            List of backup codes (8 characters each, format: XXXX-XXXX)
        """
        codes = []
        for _ in range(count):
            # Generate 8-digit code
            code_num = secrets.randbelow(100000000)
            code_str = f"{code_num:08d}"
            # Format as XXXX-XXXX for readability
            formatted = f"{code_str[:4]}-{code_str[4:]}"
            codes.append(formatted)
        return codes

    def hash_backup_code(self, code: str) -> str:
        """Hash a backup code for secure storage.

        Args:
            code: Backup code (format: XXXX-XXXX or XXXXXXXX)

        Returns:
            Hashed code (hex string)
        """
        import hashlib

        # Remove dashes and normalize
        normalized = code.replace("-", "").strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def verify_backup_code(
        self, code: str, hashed_codes: list[str]
    ) -> tuple[bool, str | None]:
        """Verify a backup code against stored hashes.

        Args:
            code: Backup code from user
            hashed_codes: List of hashed backup codes

        Returns:
            Tuple of (is_valid, matched_hash)
            - is_valid: True if code matches one of the hashes
            - matched_hash: The hash that matched (to remove it), or None
        """
        code_hash = self.hash_backup_code(code)
        if code_hash in hashed_codes:
            return True, code_hash
        return False, None

    def encrypt_secret(self, secret: str) -> str:
        """Encrypt TOTP secret for database storage.

        Args:
            secret: TOTP secret (base32)

        Returns:
            Encrypted secret (base64-encoded)
        """
        encrypted = self.cipher.encrypt(secret.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt TOTP secret from database.

        Args:
            encrypted_secret: Encrypted secret (base64-encoded)

        Returns:
            Decrypted TOTP secret (base32)

        Raises:
            ValueError: If decryption fails (invalid key or corrupted data)
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_secret)
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt TOTP secret: {e}")

    def encrypt_backup_codes(self, codes: list[str]) -> str:
        """Encrypt backup codes for database storage.

        Args:
            codes: List of hashed backup codes

        Returns:
            Encrypted JSON string (base64-encoded)
        """
        json_data = json.dumps(codes)
        encrypted = self.cipher.encrypt(json_data.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_backup_codes(self, encrypted_codes: str) -> list[str]:
        """Decrypt backup codes from database.

        Args:
            encrypted_codes: Encrypted JSON string (base64-encoded)

        Returns:
            List of hashed backup codes

        Raises:
            ValueError: If decryption fails
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_codes)
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return safe_json_loads(
                decrypted.decode("utf-8"),
                max_size=1024,  # 1KB for backup codes
                max_depth=10,
                context="TOTP backup codes",
            )
        except Exception as e:
            raise ValueError(f"Failed to decrypt backup codes: {e}")


# Global service instance (initialized with app config)
_totp_service: TOTPService | None = None


def get_totp_service() -> TOTPService:
    """Get the global TOTP service instance.

    Returns:
        TOTPService instance

    Raises:
        RuntimeError: If service is not initialized
    """
    if _totp_service is None:
        raise RuntimeError(
            "TOTP service not initialized. Call init_totp_service() first."
        )
    return _totp_service


def init_totp_service(secret_key: str) -> TOTPService:
    """Initialize the global TOTP service instance.

    Args:
        secret_key: Application secret key

    Returns:
        TOTPService instance
    """
    global _totp_service

    # Derive encryption key from app secret key
    import hashlib

    encryption_key = hashlib.sha256(
        f"{secret_key}-totp-encryption".encode("utf-8")
    ).digest()

    _totp_service = TOTPService(encryption_key)
    return _totp_service
