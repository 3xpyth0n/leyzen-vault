"""Quota management service for Leyzen Vault."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from vault.database.schema import Quota, User, VaultSpace, File, db
from vault.services.vaultspace_service import VaultSpaceService


class QuotaService:
    """Service for managing user quotas."""

    def __init__(
        self, storage_dir: Path | None = None, max_total_size_bytes: int | None = None
    ):
        """Initialize quota service.

        Args:
            storage_dir: Path to storage directory for disk usage calculation
            max_total_size_bytes: Maximum total disk size in bytes (if configured).
                                  If provided, this value will be used as the total disk size
                                  instead of detecting it from the filesystem.
        """
        self.vaultspace_service = VaultSpaceService()
        self.storage_dir = storage_dir
        self.max_total_size_bytes = max_total_size_bytes

    def get_user_quota(self, user_id: str) -> Quota | None:
        """Get quota for a user.

        Args:
            user_id: User ID

        Returns:
            Quota object or None if not found
        """
        return db.session.query(Quota).filter_by(user_id=user_id).first()

    def calculate_user_storage_used(self, user_id: str) -> int:
        """Calculate total storage used by a user across all VaultSpaces.

        Args:
            user_id: User ID

        Returns:
            Total bytes used
        """
        # Get all VaultSpaces owned by user
        vaultspaces = (
            db.session.query(VaultSpace).filter_by(owner_user_id=user_id).all()
        )

        total_size = 0
        for vaultspace in vaultspaces:
            # Sum encrypted_size of all non-deleted files
            files_size = (
                db.session.query(db.func.sum(File.encrypted_size))
                .filter_by(vaultspace_id=vaultspace.id)
                .filter(File.deleted_at.is_(None))
                .scalar()
            )
            if files_size:
                total_size += files_size

        return total_size or 0

    def calculate_user_files_count(self, user_id: str) -> int:
        """Calculate total number of files owned by a user across all VaultSpaces.

        Args:
            user_id: User ID

        Returns:
            Total number of non-deleted files
        """
        # Get all VaultSpaces owned by user
        vaultspaces = (
            db.session.query(VaultSpace).filter_by(owner_user_id=user_id).all()
        )

        total_files = 0
        for vaultspace in vaultspaces:
            # Count all non-deleted files in this vaultspace
            files_count = (
                db.session.query(File)
                .filter_by(vaultspace_id=vaultspace.id)
                .filter(File.deleted_at.is_(None))
                .count()
            )
            total_files += files_count

        return total_files

    def check_user_file_quota(
        self, user_id: str, additional_files: int = 1
    ) -> tuple[bool, dict[str, Any]]:
        """Check if user has enough file quota for additional files.

        Args:
            user_id: User ID
            additional_files: Additional files to check (default: 1)

        Returns:
            Tuple of (has_quota, info_dict)
            info_dict contains: used, limit, available
        """
        quota = self.get_user_quota(user_id)
        used = self.calculate_user_files_count(user_id)

        if not quota:
            # No quota set, unlimited
            return True, {
                "used": used,
                "limit": None,
                "available": None,
                "unlimited": True,
            }

        limit = quota.max_files
        if limit is None or limit == 0:
            # Unlimited quota
            return True, {
                "used": used,
                "limit": None,
                "available": None,
                "unlimited": True,
            }

        total_needed = used + additional_files
        has_quota = total_needed <= limit
        available = max(0, limit - used)

        return has_quota, {
            "used": used,
            "limit": limit,
            "available": available,
            "unlimited": False,
        }

    def get_disk_usage(self) -> dict[str, Any]:
        """Get disk usage information for the storage directory.

        If max_total_size_bytes is configured, it will be used as the total disk size.
        Otherwise, the actual disk size is detected from the filesystem.

        Returns:
            Dictionary with total, used, free bytes and percentage
        """
        if not self.storage_dir:
            # Fallback: try to get from current directory
            self.storage_dir = Path("/data/files")

        try:
            # Get disk usage statistics from filesystem
            total_real, used_real, free_real = shutil.disk_usage(self.storage_dir)

            # Use configured max_total_size_bytes if provided, otherwise use actual disk size
            if self.max_total_size_bytes is not None:
                total = self.max_total_size_bytes
                # Use the actual used space from the filesystem
                used = used_real
                # Calculate free space as the difference between configured total and used
                # But don't allow negative free space
                free = max(0, total - used)
                # If the configured total is smaller than actual used, cap free at 0
                # and cap used at total
                if used > total:
                    used = total
                    free = 0
            else:
                # Use actual disk size
                total = total_real
                used = used_real
                free = free_real

            # Calculate percentage used
            percentage = (used / total * 100) if total > 0 else 0.0

            return {
                "total": total,
                "used": used,
                "free": free,
                "percentage": percentage,
            }
        except Exception:
            # If disk usage cannot be determined, return None values
            # But if max_total_size_bytes is configured, use it as total with 0 used
            if self.max_total_size_bytes is not None:
                return {
                    "total": self.max_total_size_bytes,
                    "used": 0,
                    "free": self.max_total_size_bytes,
                    "percentage": 0.0,
                }
            return {
                "total": None,
                "used": None,
                "free": None,
                "percentage": 0.0,
            }

    def check_user_quota(
        self, user_id: str, additional_bytes: int = 0
    ) -> tuple[bool, dict[str, Any]]:
        """Check if user has enough quota for additional storage.

        Args:
            user_id: User ID
            additional_bytes: Additional bytes to check

        Returns:
            Tuple of (has_quota, info_dict)
            info_dict contains: used, limit, available, percentage
        """
        quota = self.get_user_quota(user_id)
        used = self.calculate_user_storage_used(user_id)

        if not quota:
            # No quota set, unlimited
            return True, {
                "used": used,
                "limit": None,
                "available": None,
                "percentage": 0.0,
                "unlimited": True,
            }

        limit = quota.max_storage_bytes
        if limit is None or limit == 0:
            # Unlimited quota
            return True, {
                "used": used,
                "limit": None,
                "available": None,
                "percentage": 0.0,
                "unlimited": True,
            }

        total_needed = used + additional_bytes
        has_quota = total_needed <= limit
        available = max(0, limit - used)
        percentage = (used / limit * 100) if limit > 0 else 0.0

        return has_quota, {
            "used": used,
            "limit": limit,
            "available": available,
            "percentage": percentage,
            "unlimited": False,
        }

    def create_or_update_user_quota(
        self, user_id: str, storage_limit_bytes: int | None = None
    ) -> Quota:
        """Create or update user quota.

        Args:
            user_id: User ID
            storage_limit_bytes: Storage limit in bytes (None for unlimited)

        Returns:
            Quota object
        """
        quota = self.get_user_quota(user_id)
        # Round to integer to ensure we store a clean integer value
        if storage_limit_bytes is not None:
            storage_limit_bytes = int(round(storage_limit_bytes))

        if not quota:
            quota = Quota(
                user_id=user_id,
                max_storage_bytes=storage_limit_bytes or 0,
            )
            db.session.add(quota)
        else:
            if storage_limit_bytes is not None:
                quota.max_storage_bytes = storage_limit_bytes

        db.session.commit()
        return quota

    def get_quota_info(self, user_id: str) -> dict[str, Any]:
        """Get comprehensive quota information for a user.

        Uses user-specific quota if defined, otherwise falls back to disk usage
        of the host system.

        Args:
            user_id: User ID

        Returns:
            Dictionary with quota information based on user-specific quota
            or host disk usage as fallback
        """
        # Calculate total storage used by user
        used = self.calculate_user_storage_used(user_id)
        # Ensure used is always an integer, not None
        if used is None:
            used = 0
        used = int(used)

        # Check if user has a specific quota defined
        quota = self.get_user_quota(user_id)
        user_limit = None
        if quota and quota.max_storage_bytes and quota.max_storage_bytes > 0:
            # User has a specific quota defined, use it
            user_limit = quota.max_storage_bytes

        if user_limit is not None:
            # Use user-specific quota
            available = max(0, user_limit - used)
            percentage = (used / user_limit * 100) if user_limit > 0 else 0.0

            return {
                "has_quota": True,
                "used": used,
                "limit": user_limit,
                "available": available,
                "percentage": percentage,
                "unlimited": False,
                "disk_percentage": percentage,
            }

        # No user-specific quota, fall back to disk total
        disk_usage = self.get_disk_usage()

        # Use disk total as limit, or None if unavailable
        total_bytes = disk_usage.get("total")

        if total_bytes is None or total_bytes == 0:
            # If disk usage cannot be determined, return basic info
            return {
                "has_quota": True,
                "used": used,
                "limit": None,
                "available": None,
                "percentage": 0.0,
                "unlimited": False,
            }

        # Calculate percentage based on disk usage
        disk_percentage = disk_usage.get("percentage", 0.0)

        # Calculate user's percentage of total disk
        user_percentage = (used / total_bytes * 100) if total_bytes > 0 else 0.0

        # Available space is calculated as total minus user's used space
        # This gives the actual available space for the user, not the system-wide free space
        available = max(0, total_bytes - used)

        return {
            "has_quota": True,
            "used": used,
            "limit": total_bytes,
            "available": available,
            "percentage": user_percentage,
            "unlimited": False,
            "disk_percentage": user_percentage,  # Use user's percentage, not overall disk usage
        }
