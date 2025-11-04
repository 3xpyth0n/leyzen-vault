"""Logging helpers for the orchestrator."""

from __future__ import annotations

import json
import logging.handlers
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from common.constants import LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT
from ..config import Settings


_CONTROL_CHAR_ESCAPES = {
    ord("\r"): "\\r",
    ord("\n"): "\\n",
    ord("\t"): "\\t",
}


def _sanitize_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.translate(_CONTROL_CHAR_ESCAPES)

    if isinstance(value, dict):
        return {str(k): _sanitize_log_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_sanitize_log_value(v) for v in value]

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return _sanitize_log_value(str(value))


class FileLogger:
    """Write structured log lines to a dedicated file with automatic rotation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()

        # Configure rotating file handler
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotate at 10MB, keep 5 backups
        self._handler = logging.handlers.RotatingFileHandler(
            str(log_path),
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        # We write our own formatted lines, so disable default formatting
        self._handler.setFormatter(logging.Formatter("%(message)s"))

        # Create a logger instance just for the handler
        self._logger = logging.getLogger(f"file_logger_{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.handlers = [self._handler]

    @property
    def log_file(self):
        return self._settings.log_file

    def log(self, msg: Any, *, context: Any | None = None) -> None:
        timestamp = datetime.now(self._settings.timezone).strftime("%Y-%m-%d %H:%M:%S")
        sanitized_msg = _sanitize_log_value(str(msg))
        line = f"[{timestamp}] {sanitized_msg}"

        if context is not None:
            sanitized_context = _sanitize_log_value(context)
            try:
                context_str = json.dumps(
                    sanitized_context, ensure_ascii=False, sort_keys=True
                )
            except (TypeError, ValueError):
                context_str = json.dumps(
                    _sanitize_log_value(str(sanitized_context)), ensure_ascii=False
                )
            line = f"{line} {context_str}"

        with self._lock:
            # Use the logger's handler for automatic rotation
            self._logger.info(line)


__all__ = ["FileLogger", "_sanitize_log_value"]
