"""Zero Trust access control service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app
from vault.database.schema import Device, File, User, db


class ZeroTrustService:
    """Zero Trust access control service."""

    def check_access(
        self,
        user_id: str,
        resource_id: str,
        resource_type: str,
        action: str,
        device_fingerprint: str | None = None,
        ip_address: str | None = None,
        location: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if user has access to resource with Zero Trust rules.

        Args:
            user_id: User ID
            resource_id: Resource ID
            resource_type: Resource type (file, vaultspace, etc.)
            action: Action being performed (read, write, delete)
            device_fingerprint: Device fingerprint
            ip_address: IP address
            location: Geographic location

        Returns:
            Tuple of (is_allowed, reason)
        """
        user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
        if not user:
            return False, "User not found or inactive"

        # Check device trust
        if device_fingerprint:
            device = (
                db.session.query(Device)
                .filter_by(device_fingerprint=device_fingerprint, user_id=user_id)
                .first()
            )

            if device and not device.is_trusted:
                # Check if device is suspicious (not seen recently)
                days_since_seen = (
                    datetime.now(timezone.utc) - device.last_seen_at
                ).days
                if days_since_seen > 30:
                    return False, "Device not trusted and suspicious"

        # Check resource access
        if resource_type == "file":
            file_obj = db.session.query(File).filter_by(id=resource_id).first()
            if not file_obj:
                return False, "Resource not found"

            # Only owner has access
            if file_obj.owner_user_id == user_id:
                return True, None

            return False, "Access denied: not owner"

        return False, "Unknown resource type"

    def require_mfa(
        self,
        user_id: str,
        action: str,
        sensitive: bool = False,
    ) -> bool:
        """Check if MFA is required for action.

        Args:
            user_id: User ID
            action: Action being performed
            sensitive: Whether action is sensitive

        Returns:
            True if MFA required, False otherwise
        """
        # Require MFA for sensitive actions
        sensitive_actions = ["delete", "share", "admin"]
        if action in sensitive_actions or sensitive:
            return True

        # Require MFA for admin users
        user = db.session.query(User).filter_by(id=user_id).first()
        if user and user.global_role.value in ["admin", "superadmin"]:
            return True

        return False

    def check_anomaly(
        self,
        user_id: str,
        action: str,
        ip_address: str | None = None,
        location: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check for anomalous behavior.

        Args:
            user_id: User ID
            action: Action being performed
            ip_address: IP address
            location: Geographic location

        Returns:
            Tuple of (is_anomalous, reason)
        """
        # Check for rapid successive actions (potential brute force)
        # This would be implemented with rate limiting and pattern detection

        # Check for unusual location
        if location:
            # Get user's usual locations
            devices = db.session.query(Device).filter_by(user_id=user_id).all()
            usual_locations = {d.location for d in devices if d.location}

            if usual_locations and location not in usual_locations:
                # New location - could be suspicious
                return True, f"Unusual location: {location}"

        # Check for unusual IP
        if ip_address:
            devices = db.session.query(Device).filter_by(user_id=user_id).all()
            usual_ips = {d.ip_address for d in devices if d.ip_address}

            if usual_ips and ip_address not in usual_ips:
                # New IP - could be suspicious
                return True, f"Unusual IP address: {ip_address}"

        return False, None

    def audit_access(
        self,
        user_id: str,
        resource_id: str,
        action: str,
        allowed: bool,
        reason: str | None = None,
        device_fingerprint: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Audit access attempt.

        Args:
            user_id: User ID
            resource_id: Resource ID
            action: Action attempted
            allowed: Whether access was allowed
            reason: Reason if denied
            device_fingerprint: Device fingerprint
            ip_address: IP address
        """
        # Store audit log
        from vault.services.audit import AuditService

        audit = current_app.config.get("VAULT_AUDIT")
        if audit:
            audit.log_action(
                action=action,
                user_ip=ip_address or "unknown",
                details={
                    "user_id": user_id,
                    "resource_id": resource_id,
                    "allowed": allowed,
                    "reason": reason,
                    "device_fingerprint": device_fingerprint,
                },
                success=allowed,
            )
