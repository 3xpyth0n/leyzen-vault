"""Audit logging service for Leyzen Vault."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..models import AuditLog


class AuditService:
    """Service for logging and retrieving audit logs."""

    def __init__(self, db_path: Path, timezone: ZoneInfo | None = None):
        """Initialize the audit service.

        Args:
            db_path: Path to the audit database file
            timezone: Timezone to use for timestamps. Defaults to UTC if not provided.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone = timezone or ZoneInfo("UTC")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the audit log database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    file_id TEXT,
                    user_ip TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT NOT NULL,
                    success INTEGER NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_file_id ON audit_logs(file_id)
            """
            )
            conn.commit()
        finally:
            conn.close()

    def log_action(
        self,
        action: str,
        user_ip: str,
        details: dict[str, Any],
        success: bool,
        file_id: str | None = None,
    ) -> None:
        """Log an action to the audit log."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO audit_logs (action, file_id, user_ip, timestamp, details, success)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    action,
                    file_id,
                    user_ip,
                    datetime.now(self.timezone).isoformat(),
                    json.dumps(details),
                    1 if success else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_logs(
        self,
        limit: int = 100,
        action: str | None = None,
        file_id: str | None = None,
        success: bool | None = None,
    ) -> list[AuditLog]:
        """Retrieve audit logs with optional filters."""
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT action, file_id, user_ip, timestamp, details, success FROM audit_logs WHERE 1=1"
            params: list[Any] = []

            if action:
                query += " AND action = ?"
                params.append(action)

            if file_id:
                query += " AND file_id = ?"
                params.append(file_id)

            if success is not None:
                query += " AND success = ?"
                params.append(1 if success else 0)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            results = []
            for row in cursor.fetchall():
                # Parse timestamp, handling both timezone-aware and naive formats
                timestamp_str = row[3]
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    # If timestamp is naive, assume it's UTC
                    if timestamp.tzinfo is None:
                        from datetime import timezone

                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError) as exc:
                    # Fallback: try parsing as simple ISO format
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        # If all parsing fails, use current time as fallback
                        timestamp = datetime.now(self.timezone)

                results.append(
                    AuditLog(
                        action=row[0],
                        file_id=row[1],
                        user_ip=row[2],
                        timestamp=timestamp,
                        details=json.loads(row[4]),
                        success=bool(row[5]),
                    )
                )
            return results
        finally:
            conn.close()

    def export_csv(self, output_path: Path, limit: int = 1000) -> None:
        """Export audit logs to CSV format."""
        logs = self.get_logs(limit=limit)
        with output_path.open("w", encoding="utf-8") as f:
            f.write("action,file_id,user_ip,timestamp,success,details\n")
            for log in logs:
                details_str = json.dumps(log.details).replace('"', '""')
                f.write(
                    f'"{log.action}","{log.file_id or ""}","{log.user_ip}",'
                    f'"{log.timestamp.isoformat()}",{1 if log.success else 0},'
                    f'"{details_str}"\n'
                )

    def export_json(self, output_path: Path, limit: int = 1000) -> None:
        """Export audit logs to JSON format."""
        logs = self.get_logs(limit=limit)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump([log.to_dict() for log in logs], f, indent=2, ensure_ascii=False)


__all__ = ["AuditService"]
