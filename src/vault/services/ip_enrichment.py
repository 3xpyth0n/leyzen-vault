"""IP address enrichment service for audit logs.

This service provides:
- IPv4 extraction from request headers
- IPv6 to IPv4 conversion when possible
- Geolocation using free public APIs with automatic fallback
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

from flask import request

logger = logging.getLogger(__name__)


class IPEnrichmentService:
    """Service for enriching IP addresses with additional information.

    Uses free public APIs for geolocation with automatic fallback.
    No configuration required - works out of the box.
    """

    def __init__(self):
        """Initialize the IP enrichment service.

        No configuration needed - uses free public APIs automatically.
        """
        pass

    def get_client_ipv4(self, user_ip: str | None = None) -> str | None:
        """Extract IPv4 address from request headers or convert IPv6 to IPv4.

        Priority:
        1. X-Forwarded-For header (first non-private IP)
        2. Convert IPv6 to IPv4 if possible
        3. Return None if no IPv4 can be determined

        Args:
            user_ip: Optional IP address to use instead of extracting from request

        Returns:
            IPv4 address as string, or None if not available
        """
        from ipaddress import IPv4Address, IPv6Address, ip_address

        # Try X-Forwarded-For header
        if request:
            xff = request.headers.get("X-Forwarded-For")
            if xff:
                for candidate in xff.split(","):
                    candidate = candidate.strip()
                    try:
                        ip = ip_address(candidate)
                        if isinstance(ip, IPv4Address):
                            # Skip private IPs
                            if not ip.is_private and not ip.is_loopback:
                                return str(ip)
                        elif isinstance(ip, IPv6Address) and ip.ipv4_mapped:
                            return str(ip.ipv4_mapped)
                    except ValueError:
                        continue

        # Use provided IP if available
        if user_ip:
            try:
                ip = ip_address(user_ip.strip())
                if isinstance(ip, IPv4Address):
                    return str(ip)
                if isinstance(ip, IPv6Address):
                    # Check for IPv4-mapped IPv6
                    if ip.ipv4_mapped:
                        return str(ip.ipv4_mapped)
                    # Try to extract IPv4 from 6to4 or Teredo (limited support)
                    # For now, we'll return None if no direct conversion is possible
            except ValueError:
                pass

        return None

    @lru_cache(maxsize=1000)
    def get_location(self, ip_address: str) -> dict[str, Any] | None:
        """Get geolocation information for an IP address.

        Uses free public APIs with automatic fallback chain:
        1. ip-api.com (45 req/min, no API key needed)
        2. ipwhois.app (10,000 req/month, no API key needed)
        3. ipapi.co (1,000 req/day, no API key needed)

        Args:
            ip_address: IP address to geolocate

        Returns:
            Dictionary with location data (country, city, etc.) or None
        """
        if not ip_address or ip_address == "unknown":
            return None

        # Try APIs in order of reliability/rate limits
        location = self._get_location_ipapi_com(ip_address)
        if location:
            return location

        location = self._get_location_ipwhois(ip_address)
        if location:
            return location

        location = self._get_location_ipapi_co(ip_address)
        return location

    def _get_location_ipapi_com(self, ip_address: str) -> dict[str, Any] | None:
        """Get location using ip-api.com (45 req/min, no API key).

        Supports both IPv4 and IPv6 addresses.

        Args:
            ip_address: IP address to geolocate

        Returns:
            Dictionary with location data or None
        """
        try:
            import requests

            # URL-encode the IP address to handle IPv6 properly
            from urllib.parse import quote

            encoded_ip = quote(ip_address, safe="")
            url = f"http://ip-api.com/json/{encoded_ip}?fields=status,message,country,countryCode,city,lat,lon,region,regionName"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    location_data: dict[str, Any] = {}
                    if data.get("countryCode"):
                        location_data["country_code"] = data["countryCode"]
                    if data.get("country"):
                        location_data["country"] = data["country"]
                    if data.get("city"):
                        location_data["city"] = data["city"]
                    if data.get("lat"):
                        location_data["latitude"] = float(data["lat"])
                    if data.get("lon"):
                        location_data["longitude"] = float(data["lon"])
                    if data.get("regionName"):
                        location_data["region"] = data["regionName"]

                    return location_data if location_data else None
        except ImportError:
            logger.debug("requests package not available for API geolocation")
        except Exception as e:
            logger.debug(f"ip-api.com geolocation failed for {ip_address}: {e}")

        return None

    def _get_location_ipwhois(self, ip_address: str) -> dict[str, Any] | None:
        """Get location using ipwhois.app (10,000 req/month, no API key).

        Supports both IPv4 and IPv6 addresses.

        Args:
            ip_address: IP address to geolocate

        Returns:
            Dictionary with location data or None
        """
        try:
            import requests

            # URL-encode the IP address to handle IPv6 properly
            from urllib.parse import quote

            encoded_ip = quote(ip_address, safe="")
            url = f"https://ipwhois.app/json/{encoded_ip}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("success") is True:
                    location_data: dict[str, Any] = {}
                    if data.get("country_code"):
                        location_data["country_code"] = data["country_code"]
                    if data.get("country"):
                        location_data["country"] = data["country"]
                    if data.get("city"):
                        location_data["city"] = data["city"]
                    if data.get("latitude"):
                        location_data["latitude"] = float(data["latitude"])
                    if data.get("longitude"):
                        location_data["longitude"] = float(data["longitude"])
                    if data.get("region"):
                        location_data["region"] = data["region"]

                    return location_data if location_data else None
        except ImportError:
            logger.debug("requests package not available for API geolocation")
        except Exception as e:
            logger.debug(f"ipwhois.app geolocation failed for {ip_address}: {e}")

        return None

    def _get_location_ipapi_co(self, ip_address: str) -> dict[str, Any] | None:
        """Get location using ipapi.co (1,000 req/day, no API key needed).

        Supports both IPv4 and IPv6 addresses.

        Args:
            ip_address: IP address to geolocate

        Returns:
            Dictionary with location data or None
        """
        try:
            import requests

            # URL-encode the IP address to handle IPv6 properly
            from urllib.parse import quote

            encoded_ip = quote(ip_address, safe="")
            url = f"https://ipapi.co/{encoded_ip}/json/"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()

                # Check for error in response
                if data.get("error"):
                    return None

                location_data: dict[str, Any] = {}
                if data.get("country_code"):
                    location_data["country_code"] = data["country_code"]
                if data.get("country_name"):
                    location_data["country"] = data["country_name"]
                if data.get("city"):
                    location_data["city"] = data["city"]
                if data.get("latitude"):
                    location_data["latitude"] = float(data["latitude"])
                if data.get("longitude"):
                    location_data["longitude"] = float(data["longitude"])
                if data.get("region"):
                    location_data["region"] = data["region"]

                return location_data if location_data else None
        except ImportError:
            logger.debug("requests package not available for API geolocation")
        except Exception as e:
            logger.debug(f"ipapi.co geolocation failed for {ip_address}: {e}")

        return None

    def enrich_ip(self, user_ip: str | None = None) -> dict[str, Any]:
        """Enrich IP address with IPv4 and location information.

        Args:
            user_ip: Optional IP address to enrich (if None, extracts from request)

        Returns:
            Dictionary with ipv4 and ip_location keys
        """
        from ipaddress import IPv4Address, IPv6Address, ip_address

        result: dict[str, Any] = {}

        if not user_ip or user_ip == "unknown":
            return result

        # Try to get IPv4 from headers first (may contain real client IP in X-Forwarded-For)
        ipv4_from_headers = self.get_client_ipv4(user_ip)
        if ipv4_from_headers:
            result["ipv4"] = ipv4_from_headers

        # If user_ip is provided, check if it's IPv4 or IPv4-mapped IPv6
        try:
            ip = ip_address(user_ip.strip())
            if isinstance(ip, IPv4Address):
                # Already IPv4
                result["ipv4"] = str(ip)
            elif isinstance(ip, IPv6Address):
                # Check if it's an IPv4-mapped IPv6 address (::ffff:x.x.x.x)
                if ip.ipv4_mapped:
                    result["ipv4"] = str(ip.ipv4_mapped)
                # For native IPv6, we cannot extract IPv4 - that's normal
        except ValueError:
            pass

        # Get location (use IPv4 if available, otherwise use original IP - APIs support IPv6)
        # Note: All three APIs (ip-api.com, ipwhois.app, ipapi.co) support IPv6
        location_ip = result.get("ipv4") or user_ip
        if location_ip:
            try:
                location = self.get_location(location_ip)
                if location:
                    result["ip_location"] = json.dumps(location)
            except Exception as e:
                # Log but don't fail
                logger.debug(f"Location lookup failed for {location_ip}: {e}")

        return result

    def close(self) -> None:
        """Close resources (no-op for API-based service)."""
        pass


__all__ = ["IPEnrichmentService"]
