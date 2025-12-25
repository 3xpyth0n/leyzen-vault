"""File event service for real-time file synchronization.

This service manages file events (create, update, delete, rename, move) and
provides a mechanism to broadcast these events to connected clients via SSE.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)


class FileEventType(str, Enum):
    """Types of file events."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RENAME = "rename"
    MOVE = "move"
    RESTORE = "restore"
    SHARE = "share"
    ZIP_CREATED = "zip_created"
    ZIP_EXTRACTION_STARTED = "zip_extraction_started"
    ZIP_EXTRACTION_COMPLETED = "zip_extraction_completed"


@dataclass
class FileEvent:
    """Represents a file event."""

    event_type: FileEventType
    file_id: str
    vaultspace_id: str
    user_id: str
    timestamp: datetime
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        result = asdict(self)
        result["event_type"] = self.event_type.value
        result["timestamp"] = self.timestamp.isoformat()
        return result


class FileEventService:
    """Service for managing and broadcasting file events."""

    def __init__(self):
        """Initialize the file event service."""
        self._subscribers: dict[str, list[Callable[[FileEvent], None]]] = defaultdict(
            list
        )
        self._lock = threading.RLock()
        self._event_history: dict[str, list[FileEvent]] = defaultdict(list)
        self._max_history_per_vaultspace = 100

    def subscribe(
        self, vaultspace_id: str, callback: Callable[[FileEvent], None]
    ) -> Callable[[], None]:
        """Subscribe to file events for a specific VaultSpace.

        Args:
            vaultspace_id: VaultSpace ID to subscribe to
            callback: Function to call when an event occurs

        Returns:
            Unsubscribe function
        """
        with self._lock:
            self._subscribers[vaultspace_id].append(callback)
            subscriber_id = id(callback)

        def unsubscribe():
            with self._lock:
                if vaultspace_id in self._subscribers:
                    self._subscribers[vaultspace_id] = [
                        cb
                        for cb in self._subscribers[vaultspace_id]
                        if id(cb) != subscriber_id
                    ]
                    if not self._subscribers[vaultspace_id]:
                        del self._subscribers[vaultspace_id]

        return unsubscribe

    def emit(
        self,
        event_type: FileEventType,
        file_id: str,
        vaultspace_id: str,
        user_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit a file event.

        Args:
            event_type: Type of event
            file_id: File ID
            vaultspace_id: VaultSpace ID
            user_id: User ID who triggered the event
            data: Additional event data
        """
        event = FileEvent(
            event_type=event_type,
            file_id=file_id,
            vaultspace_id=vaultspace_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            data=data or {},
        )

        # Store in history
        with self._lock:
            history = self._event_history[vaultspace_id]
            history.append(event)
            # Keep only recent history
            if len(history) > self._max_history_per_vaultspace:
                history.pop(0)

        # Notify subscribers
        with self._lock:
            subscribers = self._subscribers.get(vaultspace_id, [])
            # Copy list to avoid issues if subscribers modify during iteration
            subscribers_copy = list(subscribers)

        for callback in subscribers_copy:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    f"Error in file event subscriber for vaultspace {vaultspace_id}: {e}",
                    exc_info=True,
                )

    def get_event_stream(
        self, vaultspace_id: str, last_event_timestamp: datetime | None = None
    ) -> Iterator[FileEvent]:
        """Get a stream of events for a VaultSpace.

        Args:
            vaultspace_id: VaultSpace ID
            last_event_timestamp: Timestamp of last received event (for catch-up)

        Yields:
            FileEvent objects
        """
        # First, send any missed events from history
        if last_event_timestamp:
            with self._lock:
                history = self._event_history.get(vaultspace_id, [])
                for event in history:
                    if event.timestamp > last_event_timestamp:
                        yield event

        # Then, create a queue for new events
        event_queue: list[FileEvent] = []
        queue_lock = threading.Lock()
        stop_event = threading.Event()

        def event_handler(event: FileEvent) -> None:
            """Handle incoming events."""
            with queue_lock:
                event_queue.append(event)

        # Subscribe to new events
        unsubscribe = self.subscribe(vaultspace_id, event_handler)

        try:
            # Stream new events with heartbeat to keep connection alive
            # Use a longer sleep interval to reduce CPU usage
            # Uvicorn timeout is 120s, so we send heartbeat every 30s to stay well under
            last_heartbeat = time.time()
            heartbeat_interval = (
                25.0  # Send heartbeat every 25 seconds (well under 120s timeout)
            )
            sleep_interval = 1.0  # Check for events every second

            while not stop_event.is_set():
                # Check for new events
                event_to_send = None
                with queue_lock:
                    if event_queue:
                        event_to_send = event_queue.pop(0)

                if event_to_send:
                    yield event_to_send
                    last_heartbeat = time.time()
                else:
                    # Check if we need to send a heartbeat
                    current_time = time.time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        # Send heartbeat to keep connection alive
                        # This prevents Uvicorn from timing out
                        yield FileEvent(
                            event_type=FileEventType.UPDATE,
                            file_id="",
                            vaultspace_id=vaultspace_id,
                            user_id="",
                            timestamp=datetime.now(timezone.utc),
                            data={"type": "heartbeat"},
                        )
                        last_heartbeat = current_time

                    # Sleep to avoid busy-waiting
                    # Use threading.Event.wait() with timeout for better responsiveness
                    stop_event.wait(timeout=sleep_interval)
        finally:
            unsubscribe()
            stop_event.set()

    def get_recent_events(self, vaultspace_id: str, limit: int = 50) -> list[FileEvent]:
        """Get recent events for a VaultSpace.

        Args:
            vaultspace_id: VaultSpace ID
            limit: Maximum number of events to return

        Returns:
            List of recent FileEvent objects
        """
        with self._lock:
            history = self._event_history.get(vaultspace_id, [])
            return history[-limit:]


# Global instance
_file_event_service: FileEventService | None = None
_service_lock = threading.Lock()


def get_file_event_service() -> FileEventService:
    """Get the global file event service instance.

    Returns:
        FileEventService instance
    """
    global _file_event_service
    with _service_lock:
        if _file_event_service is None:
            _file_event_service = FileEventService()
        return _file_event_service
