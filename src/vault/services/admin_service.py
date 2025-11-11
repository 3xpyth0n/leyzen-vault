"""Admin service for Leyzen Vault administration operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from vault.database.schema import (
    ApiKey,
    AuditLogEntry,
    File,
    Quota,
    SSOProvider,
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
        now = datetime.now(timezone.utc)
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
        seven_days_ago = now - timedelta(days=7)
        recent_users = (
            db.session.query(User).filter(User.last_login >= seven_days_ago).count()
        )

        # Users by role
        users_by_role = {}
        for role in ["user", "admin", "superadmin"]:
            count = db.session.query(User).filter_by(global_role=role).count()
            users_by_role[role] = count

        # Calculate average vaultspaces per user
        avg_vaultspaces_per_user = (
            total_vaultspaces / total_users if total_users > 0 else 0
        )

        # Time-based statistics (30 days)
        thirty_days_ago = now - timedelta(days=30)
        users_timeline = []
        files_timeline = []
        storage_timeline = []

        for i in range(30):
            day_start = thirty_days_ago + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            # Users created on this day
            users_count = (
                db.session.query(User)
                .filter(User.created_at >= day_start, User.created_at < day_end)
                .count()
            )
            users_timeline.append(
                {
                    "date": day_start.date().isoformat(),
                    "count": users_count,
                }
            )

            # Files created on this day
            files_count = (
                db.session.query(File)
                .filter(File.created_at >= day_start, File.created_at < day_end)
                .filter(File.deleted_at.is_(None))
                .count()
            )
            files_timeline.append(
                {
                    "date": day_start.date().isoformat(),
                    "count": files_count,
                }
            )

            # Storage used at end of this day (cumulative)
            # Files created before or on this day and not deleted by this day
            storage_result = (
                db.session.query(func.sum(File.encrypted_size))
                .filter(File.created_at <= day_end)
                .filter(or_(File.deleted_at.is_(None), File.deleted_at > day_end))
                .scalar()
            )
            storage_bytes = storage_result or 0
            storage_timeline.append(
                {
                    "date": day_start.date().isoformat(),
                    "bytes": storage_bytes,
                    "gb": round(storage_bytes / (1024**3), 2),
                }
            )

        # Activity by type (last 7 days)
        activity_by_type = {}
        if self.audit_service:
            recent_logs = self.audit_service.get_logs(limit=1000)
            for log in recent_logs:
                # Check if log is within last 7 days
                if isinstance(log.timestamp, datetime):
                    log_dt = log.timestamp
                    if log_dt.tzinfo is None:
                        log_dt = log_dt.replace(tzinfo=timezone.utc)
                    if log_dt >= seven_days_ago:
                        action = log.action
                        activity_by_type[action] = activity_by_type.get(action, 0) + 1

        # Recent audit logs (last 10)
        recent_audit_logs = []
        if self.audit_service:
            logs = self.audit_service.get_logs(limit=10)
            for log in logs:
                recent_audit_logs.append(log.to_dict())

        # API Keys statistics
        total_api_keys = db.session.query(ApiKey).count()
        api_keys_with_usage = (
            db.session.query(ApiKey).filter(ApiKey.last_used_at.is_not(None)).count()
        )
        latest_api_key = (
            db.session.query(ApiKey).order_by(ApiKey.created_at.desc()).first()
        )
        latest_api_key_created = (
            latest_api_key.created_at.isoformat() if latest_api_key else None
        )

        # Top users by storage
        top_users = []
        all_users = db.session.query(User).all()
        user_storage = []
        for user in all_users:
            storage_used = self.quota_service.calculate_user_storage_used(user.id)
            if storage_used > 0:
                user_storage.append(
                    {
                        "user_id": user.id,
                        "email": user.email,
                        "storage_bytes": storage_used,
                        "storage_gb": round(storage_used / (1024**3), 2),
                    }
                )

        # Sort by storage and take top 5
        user_storage.sort(key=lambda x: x["storage_bytes"], reverse=True)
        top_users = user_storage[:5]

        # Quota alerts (users near limit)
        quota_alerts = []
        all_quotas = db.session.query(Quota).all()
        for quota in all_quotas:
            if quota.max_storage_bytes and quota.max_storage_bytes > 0:
                used = quota.used_storage_bytes or 0
                max_bytes = quota.max_storage_bytes
                usage_percent = (used / max_bytes * 100) if max_bytes > 0 else 0

                # Alert if usage >= 80%
                if usage_percent >= 80:
                    user = db.session.query(User).filter_by(id=quota.user_id).first()
                    quota_alerts.append(
                        {
                            "user_id": quota.user_id,
                            "email": user.email if user else quota.user_id,
                            "usage_percent": round(usage_percent, 1),
                            "used_bytes": used,
                            "max_bytes": max_bytes,
                            "used_gb": round(used / (1024**3), 2),
                            "max_gb": round(max_bytes / (1024**3), 2),
                        }
                    )

        # Sort by usage percent descending
        quota_alerts.sort(key=lambda x: x["usage_percent"], reverse=True)

        # SSO Providers count
        sso_providers_count = db.session.query(SSOProvider).count()
        active_sso_providers = (
            db.session.query(SSOProvider).filter_by(is_active=True).count()
        )

        # Growth rates (comparing last 7 days vs previous 7 days)
        fourteen_days_ago = now - timedelta(days=14)
        users_last_7d = (
            db.session.query(User).filter(User.created_at >= seven_days_ago).count()
        )
        users_prev_7d = (
            db.session.query(User)
            .filter(
                User.created_at >= fourteen_days_ago, User.created_at < seven_days_ago
            )
            .count()
        )
        users_growth_rate = (
            ((users_last_7d - users_prev_7d) / users_prev_7d * 100)
            if users_prev_7d > 0
            else 0
        )

        files_last_7d = (
            db.session.query(File)
            .filter(File.created_at >= seven_days_ago)
            .filter(File.deleted_at.is_(None))
            .count()
        )
        files_prev_7d = (
            db.session.query(File)
            .filter(
                File.created_at >= fourteen_days_ago, File.created_at < seven_days_ago
            )
            .filter(File.deleted_at.is_(None))
            .count()
        )
        files_growth_rate = (
            ((files_last_7d - files_prev_7d) / files_prev_7d * 100)
            if files_prev_7d > 0
            else 0
        )

        # Average storage per user
        avg_storage_per_user = total_storage / total_users if total_users > 0 else 0

        return {
            "users": {
                "total": total_users,
                "recent_activity": recent_users,
                "by_role": users_by_role,
                "growth_rate_7d": round(users_growth_rate, 1),
            },
            "files": {
                "total": total_files,
                "deleted": deleted_files,
                "growth_rate_7d": round(files_growth_rate, 1),
            },
            "vaultspaces": {
                "total": total_vaultspaces,
                "personal": personal_vaultspaces,
                "avg_per_user": round(avg_vaultspaces_per_user, 2),
            },
            "storage": {
                "total_bytes": total_storage,
                "total_gb": round(total_storage / (1024**3), 2),
                "total_tb": round(total_storage / (1024**4), 3),
                "avg_per_user_bytes": avg_storage_per_user,
                "avg_per_user_gb": round(avg_storage_per_user / (1024**3), 2),
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
                "percentage": round(disk_percentage, 2),
            },
            "timeline": {
                "users_30d": users_timeline,
                "files_30d": files_timeline,
                "storage_30d": storage_timeline,
            },
            "activity": {
                "by_type_7d": activity_by_type,
            },
            "recent_audit_logs": recent_audit_logs,
            "api_keys": {
                "total": total_api_keys,
                "with_usage": api_keys_with_usage,
                "latest_created": latest_api_key_created,
            },
            "top_users": top_users,
            "quota_alerts": quota_alerts,
            "sso_providers": {
                "total": sso_providers_count,
                "active": active_sso_providers,
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
