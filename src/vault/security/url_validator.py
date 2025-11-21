"""URL validation module to prevent SSRF attacks."""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFProtectionError(ValueError):
    """Exception raised when a URL fails SSRF protection checks."""

    pass


class SSRFProtection:
    """SSRF protection utility to validate URLs before making HTTP requests.

    This class provides protection against Server-Side Request Forgery (SSRF) attacks
    by validating URLs before they are used in HTTP requests. It blocks:
    - Private IP addresses (RFC 1918)
    - Localhost addresses (127.0.0.0/8, ::1)
    - Link-local addresses (169.254.0.0/16)
    - Cloud metadata services (169.254.169.254)
    - IPv6 local addresses

    It also supports an optional domain whitelist for stricter control.
    """

    # Private IP ranges (RFC 1918)
    PRIVATE_IP_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),  # Localhost
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local (includes cloud metadata)
        ipaddress.ip_network("::1/128"),  # IPv6 localhost
        ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    # Cloud metadata service IPs
    CLOUD_METADATA_IPS = [
        "169.254.169.254",  # AWS, GCP, Azure, DigitalOcean
        "fd00:ec2::254",  # AWS IPv6 metadata
    ]

    def __init__(self, allowed_domains: list[str] | None = None):
        """Initialize SSRF protection.

        Args:
            allowed_domains: Optional list of allowed domains (whitelist).
                            If provided, only these domains will be allowed.
        """
        self.allowed_domains = allowed_domains

    def is_private_ip(self, ip: str) -> bool:
        """Check if an IP address is private or restricted.

        Args:
            ip: IP address string

        Returns:
            True if IP is private/restricted, False otherwise
        """
        try:
            ip_obj = ipaddress.ip_address(ip)

            # Check if it's in any private range
            for private_range in self.PRIVATE_IP_RANGES:
                if ip_obj in private_range:
                    return True

            # Check cloud metadata IPs explicitly
            if str(ip_obj) in self.CLOUD_METADATA_IPS:
                return True

            return False
        except ValueError:
            # Invalid IP address
            return True

    def validate_hostname(self, hostname: str) -> None:
        """Validate a hostname and ensure it doesn't resolve to private IPs.

        Args:
            hostname: Hostname to validate

        Raises:
            SSRFProtectionError: If hostname is invalid or resolves to private IP
        """
        if not hostname:
            raise SSRFProtectionError("Empty hostname")

        # Check if hostname is actually an IP address
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if self.is_private_ip(str(ip_obj)):
                raise SSRFProtectionError(
                    f"Direct IP access to private/restricted address blocked: {hostname}"
                )
            return
        except ValueError:
            # Not an IP, continue with hostname validation
            pass

        # Check whitelist if configured
        if self.allowed_domains is not None:
            # Check if hostname matches any allowed domain
            hostname_lower = hostname.lower()
            allowed = False
            for domain in self.allowed_domains:
                domain_lower = domain.lower()
                # Exact match or subdomain match
                if hostname_lower == domain_lower or hostname_lower.endswith(
                    f".{domain_lower}"
                ):
                    allowed = True
                    break

            if not allowed:
                raise SSRFProtectionError(f"Domain not in whitelist: {hostname}")

        # Resolve hostname to check for private IPs (DNS rebinding protection)
        try:
            # Get all IP addresses for this hostname
            addr_info = socket.getaddrinfo(hostname, None)
            for info in addr_info:
                ip = info[4][0]
                # Remove IPv6 zone identifier if present
                ip = ip.split("%")[0]

                if self.is_private_ip(ip):
                    raise SSRFProtectionError(
                        f"Hostname {hostname} resolves to private/restricted IP: {ip}"
                    )
        except socket.gaierror as e:
            raise SSRFProtectionError(f"Failed to resolve hostname {hostname}: {e}")
        except OSError as e:
            raise SSRFProtectionError(f"Network error while resolving {hostname}: {e}")

    def validate_url(self, url: str) -> None:
        """Validate a URL for SSRF protection.

        Args:
            url: URL to validate

        Raises:
            SSRFProtectionError: If URL fails validation
        """
        if not url:
            raise SSRFProtectionError("Empty URL")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SSRFProtectionError(f"Invalid URL format: {e}")

        # Check scheme
        if parsed.scheme not in ["http", "https"]:
            raise SSRFProtectionError(
                f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed."
            )

        # Get hostname
        hostname = parsed.hostname
        if not hostname:
            raise SSRFProtectionError("URL has no hostname")

        # Validate hostname
        self.validate_hostname(hostname)

        # Check port for suspicious values
        port = parsed.port
        if port is not None:
            # Block common internal service ports
            blocked_ports = [
                22,  # SSH
                23,  # Telnet
                25,  # SMTP
                3306,  # MySQL
                5432,  # PostgreSQL
                6379,  # Redis
                27017,  # MongoDB
                9200,  # Elasticsearch
            ]
            if port in blocked_ports:
                logger.warning(f"Suspicious port {port} detected in URL: {url}")
                # Note: We log but don't block to allow legitimate use cases
                # Organizations can customize this list based on their needs

        logger.debug(f"URL validated successfully: {url}")

    def get_safe_request_kwargs(self) -> dict[str, Any]:
        """Get safe default kwargs for requests library.

        Returns:
            Dictionary with safe default parameters for requests
        """
        return {
            "allow_redirects": False,  # Disable redirects to prevent bypass
            "timeout": 10,  # Reasonable timeout to prevent DoS
        }


# Global instance for convenience
_default_protection = SSRFProtection()


def validate_url(url: str, allowed_domains: list[str] | None = None) -> None:
    """Validate a URL for SSRF protection (convenience function).

    Args:
        url: URL to validate
        allowed_domains: Optional list of allowed domains (whitelist)

    Raises:
        SSRFProtectionError: If URL fails validation
    """
    if allowed_domains is not None:
        protection = SSRFProtection(allowed_domains=allowed_domains)
        protection.validate_url(url)
    else:
        _default_protection.validate_url(url)
