"""Collaboration service for real-time collaboration features."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


class CollaborationSession:
    """Represents an active collaboration session."""

    def __init__(
        self,
        file_id: str,
        session_id: str | None = None,
        expires_at: datetime | None = None,
    ):
        """Initialize collaboration session.

        Args:
            file_id: File ID
            session_id: Session ID (generated if not provided)
            expires_at: Expiration time (default: 1 hour)
        """
        self.file_id = file_id
        self.session_id = session_id or str(uuid.uuid4())
        self.expires_at = expires_at or (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )
        self.participants: dict[str, dict[str, Any]] = {}  # user_id -> participant info
        self.cursor_positions: dict[str, dict[str, Any]] = (
            {}
        )  # user_id -> cursor position
        self.last_activity = datetime.now(timezone.utc)

    def add_participant(
        self,
        user_id: str,
        user_name: str,
        permission: str = "read",
    ) -> None:
        """Add participant to session.

        Args:
            user_id: User ID
            user_name: User name/email
            permission: Permission level (read, write)
        """
        self.participants[user_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "permission": permission,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
        self.last_activity = datetime.now(timezone.utc)

    def remove_participant(self, user_id: str) -> None:
        """Remove participant from session.

        Args:
            user_id: User ID
        """
        if user_id in self.participants:
            del self.participants[user_id]
        if user_id in self.cursor_positions:
            del self.cursor_positions[user_id]
        self.last_activity = datetime.now(timezone.utc)

    def update_cursor(
        self,
        user_id: str,
        position: dict[str, Any],
    ) -> None:
        """Update cursor position for a user.

        Args:
            user_id: User ID
            position: Cursor position data
        """
        self.cursor_positions[user_id] = {
            "user_id": user_id,
            "position": position,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.last_activity = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if session is expired.

        Returns:
            True if expired, False otherwise
        """
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "file_id": self.file_id,
            "participants": list(self.participants.values()),
            "cursor_positions": list(self.cursor_positions.values()),
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }


class CollaborationService:
    """Service for real-time collaboration."""

    def __init__(self):
        """Initialize collaboration service."""
        self._sessions: dict[str, CollaborationSession] = {}  # file_id -> session

    def create_session(
        self,
        file_id: str,
        user_id: str,
        user_name: str,
        permission: str = "read",
        duration_hours: int = 1,
    ) -> CollaborationSession:
        """Create a new collaboration session.

        Args:
            file_id: File ID
            user_id: User ID creating session
            user_name: User name/email
            permission: Permission level
            duration_hours: Session duration in hours

        Returns:
            CollaborationSession object
        """
        # Clean up expired sessions
        self._cleanup_expired()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        session = CollaborationSession(file_id, expires_at=expires_at)
        session.add_participant(user_id, user_name, permission)

        self._sessions[file_id] = session
        return session

    def get_session(self, file_id: str) -> CollaborationSession | None:
        """Get collaboration session for a file.

        Args:
            file_id: File ID

        Returns:
            CollaborationSession object if found, None otherwise
        """
        session = self._sessions.get(file_id)
        if session and session.is_expired():
            del self._sessions[file_id]
            return None
        return session

    def join_session(
        self,
        file_id: str,
        user_id: str,
        user_name: str,
        permission: str = "read",
    ) -> CollaborationSession | None:
        """Join an existing collaboration session.

        Args:
            file_id: File ID
            user_id: User ID
            user_name: User name/email
            permission: Permission level

        Returns:
            CollaborationSession object if found, None otherwise
        """
        session = self.get_session(file_id)
        if not session:
            return None

        session.add_participant(user_id, user_name, permission)
        return session

    def leave_session(self, file_id: str, user_id: str) -> bool:
        """Leave a collaboration session.

        Args:
            file_id: File ID
            user_id: User ID

        Returns:
            True if left successfully, False otherwise
        """
        session = self.get_session(file_id)
        if not session:
            return False

        session.remove_participant(user_id)

        # Remove session if no participants left
        if not session.participants:
            del self._sessions[file_id]

        return True

    def update_cursor(
        self,
        file_id: str,
        user_id: str,
        position: dict[str, Any],
    ) -> bool:
        """Update cursor position in collaboration session.

        Args:
            file_id: File ID
            user_id: User ID
            position: Cursor position data

        Returns:
            True if updated, False otherwise
        """
        session = self.get_session(file_id)
        if not session:
            return False

        session.update_cursor(user_id, position)
        return True

    def broadcast_change(
        self,
        file_id: str,
        change_type: str,
        change_data: dict[str, Any],
        changed_by: str,
    ) -> dict[str, Any]:
        """Broadcast a change to all session participants.

        Args:
            file_id: File ID
            change_type: Type of change (e.g., "content.update", "cursor.move")
            change_data: Change data
            changed_by: User ID making change

        Returns:
            Broadcast result dictionary
        """
        session = self.get_session(file_id)
        if not session:
            return {"success": False, "error": "No active session"}

        # In production, this would use WebSockets or Server-Sent Events
        # For now, return the change information
        return {
            "success": True,
            "session_id": session.session_id,
            "change_type": change_type,
            "change_data": change_data,
            "changed_by": changed_by,
            "participants": list(session.participants.keys()),
        }

    def _cleanup_expired(self) -> None:
        """Clean up expired sessions."""
        expired_files = [
            file_id
            for file_id, session in self._sessions.items()
            if session.is_expired()
        ]
        for file_id in expired_files:
            del self._sessions[file_id]
