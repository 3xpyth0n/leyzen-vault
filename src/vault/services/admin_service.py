"""Admin service for Leyzen Vault administration operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from vault.database.schema import (
    File,
    Quota,
    User,
    VaultSpace,
    db,
)
from vault.services.audit import AuditService
from vault.services.quota_service import QuotaService


class AdminService:
    """Service for admin operations and statistics."""

    def __init__(
        self,
        audit_service: AuditService | None = None,
        quota_service: QuotaService | None = None,
    ):
        """Initialize admin service.

        Args:
            audit_service: Optional AuditService instance
            quota_service: Optional QuotaService instance. If not provided, creates a default one.
        """
        self.quota_service = (
            quota_service if quota_service is not None else QuotaService()
        )
        self.audit_service = audit_service

    def get_system_stats(self) -> dict[str, Any]:
        """Get comprehensive system statistics.

        Returns:
            Dictionary with system statistics
        """
        total_users = db.session.query(User).count()

        total_files = db.session.query(File).filter(File.deleted_at.is_(None)).count()
        deleted_files = (
            db.session.query(File).filter(File.deleted_at.is_not(None)).count()
        )

        total_vaultspaces = (
            db.session.query(VaultSpace).filter_by(type="personal").count()
        )
        personal_vaultspaces = total_vaultspaces

        # Calculate total storage (sum of file sizes in database)
        total_storage_result = (
            db.session.query(func.sum(File.encrypted_size))
            .filter(File.deleted_at.is_(None))
            .scalar()
        )
        total_storage = total_storage_result or 0

        # Get disk usage information (real disk stats)
        disk_usage = self.quota_service.get_disk_usage()
        disk_total_bytes = disk_usage.get("total") or 0

        # For admin dashboard, "used" should be the sum of file sizes in database
        # not the system disk usage (which may be 0 on tmpfs)
        disk_used_bytes = total_storage
        # Calculate free space as total minus used files
        disk_free_bytes = (
            max(0, disk_total_bytes - total_storage) if disk_total_bytes else 0
        )
        # Calculate percentage based on files used vs total disk
        disk_percentage = (
            (disk_used_bytes / disk_total_bytes * 100) if disk_total_bytes > 0 else 0.0
        )

        # Recent activity (last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_users = (
            db.session.query(User).filter(User.last_login >= seven_days_ago).count()
        )

        # Users by role
        users_by_role = {}
        for role in ["user", "admin", "superadmin"]:
            count = db.session.query(User).filter_by(global_role=role).count()
            users_by_role[role] = count

        return {
            "users": {
                "total": total_users,
                "recent_activity": recent_users,
                "by_role": users_by_role,
            },
            "files": {
                "total": total_files,
                "deleted": deleted_files,
            },
            "vaultspaces": {
                "total": total_vaultspaces,
                "personal": personal_vaultspaces,
            },
            "storage": {
                "total_bytes": total_storage,
                "total_gb": round(total_storage / (1024**3), 2),
                "total_tb": round(total_storage / (1024**4), 3),
            },
            "disk": {
                "total_bytes": disk_total_bytes,
                "used_bytes": disk_used_bytes,
                "free_bytes": disk_free_bytes,
                "total_mb": (
                    round(disk_total_bytes / (1024**2), 2) if disk_total_bytes else 0
                ),
                "total_gb": (
                    round(disk_total_bytes / (1024**3), 2) if disk_total_bytes else 0
                ),
                "total_tb": (
                    round(disk_total_bytes / (1024**4), 3) if disk_total_bytes else 0
                ),
                "used_mb": (
                    round(disk_used_bytes / (1024**2), 2) if disk_used_bytes else 0
                ),
                "used_gb": (
                    round(disk_used_bytes / (1024**3), 2) if disk_used_bytes else 0
                ),
                "used_tb": (
                    round(disk_used_bytes / (1024**4), 3) if disk_used_bytes else 0
                ),
                "free_mb": (
                    round(disk_free_bytes / (1024**2), 2) if disk_free_bytes else 0
                ),
                "free_gb": (
                    round(disk_free_bytes / (1024**3), 2) if disk_free_bytes else 0
                ),
                "free_tb": (
                    round(disk_free_bytes / (1024**4), 3) if disk_free_bytes else 0
                ),
                "percentage": disk_percentage,
            },
        }

    def search_users(
        self,
        query: str | None = None,
        role: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Search and filter users.

        Args:
            query: Search query (email)
            role: Filter by global role
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with paginated users
        """
        q = db.session.query(User)

        if query:
            q = q.filter(User.email.ilike(f"%{query}%"))

        if role:
            q = q.filter_by(global_role=role)

        pagination = q.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            "users": [u.to_dict() for u in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
        }

    def get_user_details(self, user_id: str) -> dict[str, Any] | None:
        """Get detailed information about a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user details or None if not found
        """
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return None

        # Get user's vaultspaces
        vaultspaces = (
            db.session.query(VaultSpace).filter_by(owner_user_id=user_id).all()
        )

        # Get user's files count
        files_count = (
            db.session.query(File)
            .join(VaultSpace)
            .filter(VaultSpace.owner_user_id == user_id)
            .filter(File.deleted_at.is_(None))
            .count()
        )

        # Get quota info
        quota_info = self.quota_service.check_user_quota(user_id)

        return {
            "user": user.to_dict(),
            "vaultspaces": [v.to_dict() for v in vaultspaces],
            "files_count": files_count,
            "quota": quota_info[1],
        }

    def get_audit_logs(
        self,
        limit: int = 100,
        action: str | None = None,
        file_id: str | None = None,
        success: bool | None = None,
        user_ip: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get audit logs with filters.

        Args:
            limit: Maximum number of logs to return
            action: Filter by action type
            file_id: Filter by file ID
            success: Filter by success status
            user_ip: Filter by user IP

        Returns:
            List of audit log dictionaries
        """
        if not self.audit_service:
            return []

        logs = self.audit_service.get_logs(
            limit=limit, action=action, file_id=file_id, success=success
        )

        # Filter by IP if provided
        if user_ip:
            logs = [log for log in logs if log.user_ip == user_ip]

        return [log.to_dict() for log in logs]

    def export_audit_logs_csv(self, output_path: str, limit: int = 1000) -> bool:
        """Export audit logs to CSV.

        Args:
            output_path: Output file path
            limit: Maximum number of logs to export

        Returns:
            True if successful, False otherwise
        """
        if not self.audit_service:
            return False

        try:
            from pathlib import Path

            self.audit_service.export_csv(Path(output_path), limit=limit)
            return True
        except Exception:
            return False

    def export_audit_logs_json(self, output_path: str, limit: int = 1000) -> bool:
        """Export audit logs to JSON.

        Args:
            output_path: Output file path
            limit: Maximum number of logs to export

        Returns:
            True if successful, False otherwise
        """
        if not self.audit_service:
            return False

        try:
            from pathlib import Path

            self.audit_service.export_json(Path(output_path), limit=limit)
            return True
        except Exception:
            return False
