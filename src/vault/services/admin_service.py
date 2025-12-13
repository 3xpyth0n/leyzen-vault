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
from vault.services.cache_service import get_cache_service
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

        Optimized to minimize database queries and prevent blocking.
        Uses caching to avoid recalculating expensive stats on every request.

        Returns:
            Dictionary with system statistics
        """
        # Use cache to avoid expensive recalculations (60 second TTL)
        cache = get_cache_service()
        cache_key = "admin_system_stats"
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats

        now = datetime.now(timezone.utc)

        # Use a single read-only transaction for all stats queries
        # This reduces lock contention and improves performance
        try:
            # Ensure we start with a clean session to avoid "current transaction is aborted" errors
            # from previous failed requests in the same session
            try:
                db.session.rollback()
            except Exception:
                pass
            # Basic counts - optimize by using subqueries where possible
            total_users = db.session.query(func.count(User.id)).scalar() or 0

            # Files count - separate queries for clarity
            total_files = (
                db.session.query(func.count(File.id))
                .filter(File.deleted_at.is_(None))
                .scalar()
                or 0
            )
            deleted_files = (
                db.session.query(func.count(File.id))
                .filter(File.deleted_at.is_not(None))
                .scalar()
                or 0
            )

            total_vaultspaces = (
                db.session.query(func.count(VaultSpace.id))
                .filter_by(type="personal")
                .scalar()
                or 0
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
                (disk_used_bytes / disk_total_bytes * 100)
                if disk_total_bytes > 0
                else 0.0
            )

            # Recent activity (last 7 days)
            seven_days_ago = now - timedelta(days=7)
            recent_users = (
                db.session.query(func.count(User.id))
                .filter(User.last_login >= seven_days_ago)
                .scalar()
                or 0
            )

            # Users by role - single query with GROUP BY instead of multiple queries
            from vault.database.schema import GlobalRole as GlobalRoleEnum

            users_by_role_query = (
                db.session.query(User.global_role, func.count(User.id))
                .group_by(User.global_role)
                .all()
            )
            users_by_role = {}
            for role_obj, count in users_by_role_query:
                role_name = (
                    role_obj.value if hasattr(role_obj, "value") else str(role_obj)
                )
                users_by_role[role_name] = count

            # Ensure all roles are present
            for role in ["user", "admin", "superadmin"]:
                if role not in users_by_role:
                    users_by_role[role] = 0

            # Calculate average vaultspaces per user
            avg_vaultspaces_per_user = (
                total_vaultspaces / total_users if total_users > 0 else 0
            )

            # Time-based statistics - optimized: use 7 data points (weekly) instead of 30 (daily)
            # This reduces queries from 30 to 7 while still providing useful trend data
            thirty_days_ago = now - timedelta(days=30)
            users_timeline = []
            files_timeline = []
            storage_timeline = []

            # Batch query for users timeline (more efficient than individual queries)
            users_created_query = (
                db.session.query(
                    func.date(User.created_at).label("date"),
                    func.count(User.id).label("count"),
                )
                .filter(User.created_at >= thirty_days_ago)
                .group_by(func.date(User.created_at))
                .all()
            )
            users_by_date = {str(row.date): row.count for row in users_created_query}

            # Batch query for files timeline
            files_created_query = (
                db.session.query(
                    func.date(File.created_at).label("date"),
                    func.count(File.id).label("count"),
                )
                .filter(File.created_at >= thirty_days_ago, File.deleted_at.is_(None))
                .group_by(func.date(File.created_at))
                .all()
            )
            files_by_date = {str(row.date): row.count for row in files_created_query}

            # Get current total storage once (used for final point)
            current_storage = (
                db.session.query(func.sum(File.encrypted_size))
                .filter(File.deleted_at.is_(None))
                .scalar()
                or 0
            )

            # Build timeline arrays with weekly data points (7 points over 30 days)
            # Aggregate daily data into weekly buckets to reduce queries
            for week_idx in range(7):
                week_start = thirty_days_ago + timedelta(
                    days=week_idx * 4
                )  # ~4.3 days per week
                week_end = week_start + timedelta(days=4) if week_idx < 6 else now
                week_str = week_start.date().isoformat()

                # Aggregate users created during this week
                users_count = sum(
                    count
                    for date_str, count in users_by_date.items()
                    if week_start.date().isoformat()
                    <= date_str
                    < week_end.date().isoformat()
                )
                users_timeline.append({"date": week_str, "count": users_count})

                # Aggregate files created during this week
                files_count = sum(
                    count
                    for date_str, count in files_by_date.items()
                    if week_start.date().isoformat()
                    <= date_str
                    < week_end.date().isoformat()
                )
                files_timeline.append({"date": week_str, "count": files_count})

                # Storage: calculate cumulative storage at end of week
                # For last week, use current storage. For others, query once per week.
                if week_idx == 6:
                    storage_bytes = current_storage
                else:
                    storage_result = (
                        db.session.query(func.sum(File.encrypted_size))
                        .filter(
                            File.created_at <= week_end,
                            or_(File.deleted_at.is_(None), File.deleted_at > week_end),
                        )
                        .scalar()
                    )
                    storage_bytes = storage_result or 0

                storage_timeline.append(
                    {
                        "date": week_str,
                        "bytes": storage_bytes,
                        "gb": round(storage_bytes / (1024**3), 2),
                    }
                )

            # Activity by type (last 7 days)
            activity_by_type = {}
            if self.audit_service:
                try:
                    recent_logs = self.audit_service.get_logs(limit=1000)
                    for log in recent_logs:
                        # Check if log is within last 7 days
                        if isinstance(log.timestamp, datetime):
                            log_dt = log.timestamp
                            if log_dt.tzinfo is None:
                                log_dt = log_dt.replace(tzinfo=timezone.utc)
                            if log_dt >= seven_days_ago:
                                action = log.action
                                activity_by_type[action] = (
                                    activity_by_type.get(action, 0) + 1
                                )
                except Exception as e:
                    # Rollback transaction to clear aborted state if lock failed
                    db.session.rollback()
                    # Log error but don't fail stats if audit logs are locked
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to get audit logs for stats: {e}")

            # Recent audit logs (last 10)
            recent_audit_logs = []
            if self.audit_service:
                try:
                    logs = self.audit_service.get_logs(limit=10)
                    for log in logs:
                        recent_audit_logs.append(log.to_dict())
                except Exception as e:
                    # Rollback transaction to clear aborted state if lock failed
                    db.session.rollback()
                    # Log error but don't fail stats if audit logs are locked
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to get recent audit logs: {e}")

            # API Keys statistics
            total_api_keys = db.session.query(ApiKey).count()
            api_keys_with_usage = (
                db.session.query(ApiKey)
                .filter(ApiKey.last_used_at.is_not(None))
                .count()
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
                        user = (
                            db.session.query(User).filter_by(id=quota.user_id).first()
                        )
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
                    User.created_at >= fourteen_days_ago,
                    User.created_at < seven_days_ago,
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
                    File.created_at >= fourteen_days_ago,
                    File.created_at < seven_days_ago,
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
                        round(disk_total_bytes / (1024**2), 2)
                        if disk_total_bytes
                        else 0
                    ),
                    "total_gb": (
                        round(disk_total_bytes / (1024**3), 2)
                        if disk_total_bytes
                        else 0
                    ),
                    "total_tb": (
                        round(disk_total_bytes / (1024**4), 3)
                        if disk_total_bytes
                        else 0
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

        except Exception as e:
            # Rollback on error and re-raise
            db.session.rollback()
            # Ensure session is removed to return connection to pool
            db.session.remove()
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error getting system stats: {e}", exc_info=True)
            raise

        # Cache result for 60 seconds to avoid expensive recalculations
        cache.set(cache_key, result, ttl=60)
        return result

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
            limit=limit,
            action=action,
            file_id=file_id,
            success=success,
            user_ip=user_ip,
        )

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
