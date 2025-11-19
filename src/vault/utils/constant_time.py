"""Constant-time comparison utilities to prevent timing attacks."""

from __future__ import annotations

import hmac
import secrets


def constant_time_compare(a: str | bytes, b: str | bytes) -> bool:
    """Compare two strings/bytes in constant time to prevent timing attacks.

    Uses HMAC comparison which is designed to be constant-time regardless
    of where the first difference occurs.

    Args:
        a: First string or bytes to compare
        b: Second string or bytes to compare

    Returns:
        True if strings are equal, False otherwise
    """
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")

    # Use a random key for HMAC comparison
    # This ensures constant-time comparison regardless of input
    key = secrets.token_bytes(32)
    mac_a = hmac.new(key, a, digestmod="sha256").digest()
    mac_b = hmac.new(key, b, digestmod="sha256").digest()

    return hmac.compare_digest(mac_a, mac_b)


def constant_time_equals(a: str | bytes, b: str | bytes) -> bool:
    """Alias for constant_time_compare for readability."""
    return constant_time_compare(a, b)
