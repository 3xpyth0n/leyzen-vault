"""Audit logging service for Leyzen Vault."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..database.schema import AuditLogEntry, db
from ..models import AuditLog


class AuditService:
    """Service for logging and retrieving audit logs using PostgreSQL."""

    def __init__(self, timezone: ZoneInfo | None = None, retention_days: int = 90):
        """Initialize the audit service.

        Args:
            timezone: Timezone to use for timestamps. Defaults to UTC if not provided.
            retention_days: Number of days to retain audit logs (default: 90)
        """
        self.timezone = timezone or ZoneInfo("UTC")
        self.retention_days = retention_days

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
    ) -> None:
        """Log an action to the audit log using PostgreSQL."""
        try:
            # Create audit log entry in PostgreSQL
            audit_entry = AuditLogEntry(
                action=action,
                file_id=file_id,
                user_ip=user_ip,
                timestamp=datetime.now(self.timezone),
                details=json.dumps(details),
                success=success,
            )
            db.session.add(audit_entry)
            db.session.commit()
        except Exception as e:
            # Log error but don't fail the request
            # Use Python logging instead of FileLogger to avoid circular dependency
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log audit action: {e}")
            db.session.rollback()

    def get_logs(
        self,
        limit: int = 100,
        action: str | None = None,
        file_id: str | None = None,
        success: bool | None = None,
    ) -> list[AuditLog]:
        """Retrieve audit logs with optional filters from PostgreSQL."""
        try:
            # Build query using SQLAlchemy
            query = db.session.query(AuditLogEntry)

            if action:
                query = query.filter(AuditLogEntry.action == action)

            if file_id:
                query = query.filter(AuditLogEntry.file_id == file_id)

            if success is not None:
                query = query.filter(AuditLogEntry.success == success)

            # Order by timestamp descending and limit results
            query = query.order_by(AuditLogEntry.timestamp.desc()).limit(limit)

            # Execute query and convert to AuditLog objects
            results = []
            for entry in query.all():
                results.append(
                    AuditLog(
                        action=entry.action,
                        file_id=entry.file_id,
                        user_ip=entry.user_ip,
                        timestamp=entry.timestamp,
                        details=json.loads(entry.details) if entry.details else {},
                        success=entry.success,
                    )
                )
            return results
        except Exception as e:
            # Log error and return empty list
            import logging

            logger = logging.getLogger(__name__)
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
            f.write("action,file_id,user_ip,timestamp,success,details\n")
            for log in logs:
                details_str = json.dumps(log.details).replace('"', '""')
                f.write(
                    f'"{log.action}","{log.file_id or ""}","{log.user_ip}",'
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
            db.session.rollback()
            return 0


__all__ = ["AuditService"]
