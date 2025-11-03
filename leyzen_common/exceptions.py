"""Shared exception hierarchy for Leyzen Vault components."""

from __future__ import annotations


class LeyzenBaseError(Exception):
    """Base exception for all Leyzen Vault errors."""


class ConfigurationError(LeyzenBaseError):
    """Raised when required configuration values are missing or invalid."""


class DockerProxyError(LeyzenBaseError):
    """Base error for controlled Docker proxy failures."""


class DockerProxyNotFound(DockerProxyError):
    """Raised when a container is not present on the proxy side."""


__all__ = [
    "LeyzenBaseError",
    "ConfigurationError",
    "DockerProxyError",
    "DockerProxyNotFound",
]
