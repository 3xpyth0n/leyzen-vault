"""Common utility functions shared across Leyzen Vault components."""

from __future__ import annotations

from ipaddress import ip_address

from flask import request


def get_client_ip(proxy_trust_count: int = 0) -> str | None:
    """Extract the real client IP address from request headers.

    Respects proxy trust count configuration to determine the correct
    IP address when behind a reverse proxy.

    Args:
        proxy_trust_count: Number of proxies to trust (0 = no proxy, 1+ = trust proxies)

    Returns:
        Client IP address as string, or None if cannot be determined
    """
    if proxy_trust_count > 0:
        header_value = request.headers.get("X-Forwarded-For", "")
        if header_value:
            forwarded_ips = [ip.strip() for ip in header_value.split(",") if ip.strip()]
            for candidate in forwarded_ips:
                try:
                    parsed = ip_address(candidate)
                except ValueError:
                    continue

                if not (
                    parsed.is_private
                    or parsed.is_loopback
                    or parsed.is_reserved
                    or parsed.is_link_local
                ):
                    return candidate

            if forwarded_ips:
                return forwarded_ips[0]

    return request.remote_addr


__all__ = ["get_client_ip"]
