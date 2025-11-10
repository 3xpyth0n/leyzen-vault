"""Device management service for multi-device security."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.database.schema import Device, User, db


class DeviceService:
    """Service for managing user devices."""

    def register_device(
        self,
        user_id: str,
        device_name: str,
        device_type: str,
        device_fingerprint: str,
        ip_address: str | None = None,
        location: str | None = None,
    ) -> Device:
        """Register a new device for a user.

        Args:
            user_id: User ID
            device_name: Device name
            device_type: Device type (desktop, mobile, tablet, etc.)
            device_fingerprint: Unique device fingerprint
            ip_address: IP address
            location: Geographic location

        Returns:
            Device object
        """
        # Check if device already exists
        existing = (
            db.session.query(Device)
            .filter_by(device_fingerprint=device_fingerprint)
            .first()
        )

        if existing:
            # Update existing device
            existing.device_name = device_name
            existing.device_type = device_type
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.ip_address = ip_address
            existing.location = location
            db.session.commit()
            return existing

        # Create new device
        device = Device(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_name=device_name,
            device_type=device_type,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            location=location,
            is_trusted=False,  # Require explicit trust
        )
        db.session.add(device)
        db.session.commit()

        return device

    def trust_device(self, device_id: str, user_id: str) -> Device | None:
        """Mark a device as trusted.

        Args:
            device_id: Device ID
            user_id: User ID (for authorization)

        Returns:
            Device object if found, None otherwise
        """
        device = (
            db.session.query(Device).filter_by(id=device_id, user_id=user_id).first()
        )
        if not device:
            return None

        device.is_trusted = True
        db.session.commit()
        return device

    def untrust_device(self, device_id: str, user_id: str) -> bool:
        """Mark a device as untrusted.

        Args:
            device_id: Device ID
            user_id: User ID (for authorization)

        Returns:
            True if device was untrusted, False otherwise
        """
        device = (
            db.session.query(Device).filter_by(id=device_id, user_id=user_id).first()
        )
        if not device:
            return False

        device.is_trusted = False
        db.session.commit()
        return True

    def remove_device(self, device_id: str, user_id: str) -> bool:
        """Remove a device.

        Args:
            device_id: Device ID
            user_id: User ID (for authorization)

        Returns:
            True if device was removed, False otherwise
        """
        device = (
            db.session.query(Device).filter_by(id=device_id, user_id=user_id).first()
        )
        if not device:
            return False

        db.session.delete(device)
        db.session.commit()
        return True

    def list_devices(self, user_id: str) -> list[Device]:
        """List all devices for a user.

        Args:
            user_id: User ID

        Returns:
            List of Device objects
        """
        # Legacy admin has no devices in database
        if user_id == "legacy_admin":
            return []

        return (
            db.session.query(Device)
            .filter_by(user_id=user_id)
            .order_by(Device.last_seen_at.desc())
            .all()
        )

    def update_device_last_seen(
        self,
        device_fingerprint: str,
        ip_address: str | None = None,
        location: str | None = None,
    ) -> Device | None:
        """Update device last seen timestamp.

        Args:
            device_fingerprint: Device fingerprint
            ip_address: IP address
            location: Geographic location

        Returns:
            Device object if found, None otherwise
        """
        device = (
            db.session.query(Device)
            .filter_by(device_fingerprint=device_fingerprint)
            .first()
        )
        if not device:
            return None

        device.last_seen_at = datetime.now(timezone.utc)
        if ip_address:
            device.ip_address = ip_address
        if location:
            device.location = location

        db.session.commit()
        return device

    def get_suspicious_devices(self, user_id: str, days: int = 30) -> list[Device]:
        """Get devices that haven't been seen recently.

        Args:
            user_id: User ID
            days: Number of days to consider as threshold

        Returns:
            List of suspicious Device objects
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        devices = db.session.query(Device).filter_by(user_id=user_id).all()

        suspicious = [
            d for d in devices if d.last_seen_at < threshold and not d.is_trusted
        ]

        return suspicious

    @staticmethod
    def generate_device_fingerprint(
        user_agent: str,
        screen_resolution: str | None = None,
        timezone: str | None = None,
    ) -> str:
        """Generate device fingerprint.

        Args:
            user_agent: User agent string
            screen_resolution: Screen resolution (optional)
            timezone: Timezone (optional)

        Returns:
            Device fingerprint hash
        """
        fingerprint_data = f"{user_agent}|{screen_resolution or ''}|{timezone or ''}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
