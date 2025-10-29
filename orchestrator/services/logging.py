"""Logging helpers for the orchestrator."""

from __future__ import annotations

import json
from datetime import datetime
from threading import Lock
from typing import Any, Optional

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
    """Write structured log lines to a dedicated file."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()

    @property
    def log_file(self):
        return self._settings.log_file

    def log(self, msg: Any, *, context: Optional[Any] = None) -> None:
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
            with open(self._settings.log_file, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")


__all__ = ["FileLogger", "_sanitize_log_value"]
