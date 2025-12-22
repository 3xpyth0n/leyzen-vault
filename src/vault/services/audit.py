"""Audit logging service for Leyzen Vault."""

from __future__ import annotations

from pathlib import Path
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from ..database.schema import AuditLogEntry, User, db
from ..models import AuditLog
from ..utils.safe_json import safe_json_loads

logger = logging.getLogger(__name__)


class AuditService:
    """Service for logging and retrieving audit logs using PostgreSQL."""

    def __init__(
        self,
        timezone: ZoneInfo | None = None,
        retention_days: int = 90,
        ip_enrichment_service: Any | None = None,
    ):
        """Initialize the audit service.

        Args:
            timezone: Timezone to use for timestamps. Defaults to UTC if not provided.
            retention_days: Number of days to retain audit logs (default: 90)
            ip_enrichment_service: Optional IPEnrichmentService instance for IP enrichment
        """
        self.timezone = timezone or ZoneInfo("UTC")
        self.retention_days = retention_days
        self.ip_enrichment_service = ip_enrichment_service

    def _init_db(self) -> None:
        """Initialize the audit log database schema.

        Note: The database schema is defined in database/schema.py as AuditLogEntry.
        Tables are created automatically by SQLAlchemy via db.create_all().
        """
        # Schema is managed by SQLAlchemy - tables are created automatically
        # This method is kept for backward compatibility but does nothing
        pass

    def log_action(
        self,
        action: str,
        user_ip: str,
        details: dict[str, Any],
        success: bool,
        file_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Log an action to the audit log using PostgreSQL.

        Args:
            action: Action name (e.g., 'upload', 'download', 'auth_login_success')
            user_ip: User IP address
            details: Additional details as dictionary
            success: Whether the action was successful
            file_id: Optional file ID if action is file-related
            user_id: Optional user ID if action is user-related (e.g., authentication)
        """
        try:
            # Enrich IP if enrichment service is available
            ipv4 = None
            ip_location = None
            if self.ip_enrichment_service:
                try:
                    enrichment = self.ip_enrichment_service.enrich_ip(user_ip)
                    ipv4 = enrichment.get("ipv4")
                    ip_location = enrichment.get("ip_location")
                    logger.debug(
                        f"IP enrichment for {user_ip}: ipv4={ipv4}, "
                        f"location={'present' if ip_location else 'none'}"
                    )
                except Exception as e:
                    # Don't fail audit logging if enrichment fails
                    logger.warning(
                        f"IP enrichment failed for audit log: {e}", exc_info=True
                    )

            # Create audit log entry in PostgreSQL
            audit_entry = AuditLogEntry(
                action=action,
                file_id=file_id,
                user_ip=user_ip,
                ipv4=ipv4,
                ip_location=ip_location,
                user_id=user_id,
                timestamp=datetime.now(self.timezone),
                details=json.dumps(details),
                success=success,
            )
            db.session.add(audit_entry)
            db.session.commit()
        except Exception as e:
            # Log error but don't fail the request
            logger.error(f"Failed to log audit action: {e}")
            db.session.rollback()

    def get_logs(
        self,
        limit: int = 100,
        action: str | None = None,
        file_id: str | None = None,
        success: bool | None = None,
        user_ip: str | None = None,
    ) -> list[AuditLog]:
        """Retrieve audit logs with optional filters from PostgreSQL."""
        try:
            # Build query using SQLAlchemy with outer join to User table to get user email
            query = db.session.query(AuditLogEntry, User.email).outerjoin(
                User, AuditLogEntry.user_id == User.id
            )

            if action:
                # Use ILIKE for case-insensitive partial matching
                query = query.filter(AuditLogEntry.action.ilike(f"%{action}%"))

            if file_id:
                # Use ILIKE for case-insensitive partial matching
                query = query.filter(AuditLogEntry.file_id.ilike(f"%{file_id}%"))

            if user_ip:
                # Use ILIKE for case-insensitive partial matching on user_ip, ipv4, or location (country/city)
                query = query.filter(
                    or_(
                        AuditLogEntry.user_ip.ilike(f"%{user_ip}%"),
                        AuditLogEntry.ipv4.ilike(f"%{user_ip}%"),
                        AuditLogEntry.ip_location.ilike(f"%{user_ip}%"),
                    )
                )

            if success is not None:
                query = query.filter(AuditLogEntry.success == success)

            # Order by timestamp descending and limit results
            query = query.order_by(AuditLogEntry.timestamp.desc()).limit(limit)

            # Execute query and convert to AuditLog objects
            # Also enrich logs that don't have location data yet (backfill, but limit to avoid performance issues)
            results = []
            backfill_count = 0
            max_backfill = 10  # Limit backfill to avoid performance issues

            for entry, user_email in query.all():
                # If entry doesn't have location data, try to enrich it (limited backfill)
                if (
                    backfill_count < max_backfill
                    and not entry.ip_location
                    and self.ip_enrichment_service
                    and entry.user_ip
                    and entry.user_ip != "unknown"
                ):
                    try:
                        enrichment = self.ip_enrichment_service.enrich_ip(entry.user_ip)
                        if enrichment.get("ip_location"):
                            # Update the entry in database
                            entry.ip_location = enrichment.get("ip_location")
                            if enrichment.get("ipv4") and not entry.ipv4:
                                entry.ipv4 = enrichment.get("ipv4")
                            db.session.commit()
                            backfill_count += 1
                    except Exception as e:
                        # Don't fail if enrichment fails
                        logger.debug(
                            f"Backfill enrichment failed for {entry.user_ip}: {e}"
                        )
                        db.session.rollback()

                results.append(
                    AuditLog(
                        action=entry.action,
                        file_id=entry.file_id,
                        user_ip=entry.user_ip,
                        ipv4=entry.ipv4,
                        ip_location=(
                            safe_json_loads(
                                entry.ip_location,
                                max_size=5 * 1024,  # 5KB for location data
                                max_depth=10,
                                context="audit log ip_location",
                            )
                            if entry.ip_location
                            else None
                        ),
                        user_id=entry.user_id,
                        user_email=user_email,
                        timestamp=entry.timestamp,
                        details=(
                            safe_json_loads(
                                entry.details,
                                max_size=10 * 1024,  # 10KB for audit details
                                max_depth=20,
                                context="audit log details",
                            )
                            if entry.details
                            else {}
                        ),
                        success=entry.success,
                    )
                )
            return results
        except Exception as e:
            # Log error and return empty list
            logger.error(f"Failed to retrieve audit logs: {e}")
            return []

    def export_csv(self, output_path: str | Path, limit: int = 1000) -> None:
        """Export audit logs to CSV format."""
        from pathlib import Path

        output_path_obj = (
            Path(output_path) if isinstance(output_path, str) else output_path
        )
        logs = self.get_logs(limit=limit)
        with output_path_obj.open("w", encoding="utf-8") as f:
            f.write(
                "action,file_id,user_ip,ipv4,ip_location,user_id,timestamp,success,details\n"
            )
            for log in logs:
                details_str = json.dumps(log.details).replace('"', '""')
                location_str = (
                    json.dumps(log.ip_location).replace('"', '""')
                    if log.ip_location
                    else ""
                )
                f.write(
                    f'"{log.action}","{log.file_id or ""}","{log.user_ip}","{log.ipv4 or ""}",'
                    f'"{location_str}","{log.user_id or ""}",'
                    f'"{log.timestamp.isoformat()}",{1 if log.success else 0},'
                    f'"{details_str}"\n'
                )

    def export_json(self, output_path: str | Path, limit: int = 1000) -> None:
        """Export audit logs to JSON format."""
        from pathlib import Path

        output_path_obj = (
            Path(output_path) if isinstance(output_path, str) else output_path
        )
        logs = self.get_logs(limit=limit)
        with output_path_obj.open("w", encoding="utf-8") as f:
            json.dump([log.to_dict() for log in logs], f, indent=2, ensure_ascii=False)

    def cleanup_old_logs(self) -> int:
        """Remove audit logs older than the retention period.

        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.now(self.timezone) - timedelta(
                days=self.retention_days
            )

            # Delete old logs using SQLAlchemy
            deleted_count = (
                db.session.query(AuditLogEntry)
                .filter(AuditLogEntry.timestamp < cutoff_date)
                .delete(synchronize_session=False)
            )
            db.session.commit()
            return deleted_count
        except Exception as e:
            # Log error and return 0
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to cleanup old audit logs: {e}")
            try:
                db.session.rollback()
            except Exception:
                # Ignore rollback errors (might be outside application context)
                pass
            return 0


__all__ = ["AuditService"]


__all__ = ["AuditService"]


__all__ = ["AuditService"]
