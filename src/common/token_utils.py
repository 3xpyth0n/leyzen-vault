"""Token derivation utilities for Leyzen Vault.

This module provides functions to derive authentication tokens from SECRET_KEY
using HMAC-based key derivation. All services use the same SECRET_KEY to generate
identical tokens without needing to share or persist them.
"""

from __future__ import annotations

import hashlib
import hmac


def derive_docker_proxy_token(secret_key: str) -> str:
    """Derive DOCKER_PROXY_TOKEN from SECRET_KEY using HMAC.

    This function generates a deterministic token for Docker proxy authentication.
    All services using the same SECRET_KEY will generate the same token.

    Args:
        secret_key: The SECRET_KEY to derive the token from

    Returns:
        A 64-character hexadecimal token (256 bits)
    """
    context = b"docker-proxy-token-v1"
    token_bytes = hmac.new(secret_key.encode(), context, hashlib.sha256).digest()
    return token_bytes.hex()


# derive_internal_api_token removed - now using random token generation stored in database
# The token is generated randomly by the vault service and stored encrypted in SystemSecrets table
# Orchestrator reads the token from the database

__all__ = ["derive_docker_proxy_token"]
