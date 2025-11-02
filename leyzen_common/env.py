"""Environment parsing helpers shared across Leyzen Vault services."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def read_env_file(path: Path) -> dict[str, str]:
    """Return key/value pairs from a ``.env`` style file.

    Lines beginning with ``#`` or without an ``=`` separator are ignored. Values wrapped
    in single or double quotes are unwrapped to match Docker Compose semantics.
    """

    data: dict[str, str] = {}
    if not path.exists():
        return data

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        data[key] = value

    return data


def parse_container_names(raw_value: str | Iterable[str] | None) -> list[str]:
    """Split a container list into unique names while preserving order."""

    if raw_value is None:
        return []

    if isinstance(raw_value, str):
        tokens = re.split(r"[,\s]+", raw_value)
    else:
        tokens = list(raw_value)

    names: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        entry = token.strip()
        if not entry or entry in seen:
            continue
        seen.add(entry)
        names.append(entry)

    return names
