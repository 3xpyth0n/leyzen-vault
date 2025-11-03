"""Environment parsing helpers shared across Leyzen Vault services.

Note on parser duplication:
This module provides a Python implementation of .env file parsing. A separate Go
implementation exists in cli/internal/env.go (LoadEnvFile). While both parsers
handle the same basic format (KEY=VALUE with optional quotes and comments), they
may exhibit subtle differences in edge cases:

- Quote handling: Both strip single and double quotes from values
- Comment handling: Both ignore lines starting with #
- Empty lines: Both are ignored
- Whitespace: Both trim keys and values

This duplication is necessary for linguistic reasons (Python services vs Go CLI)
but should be kept in sync to avoid configuration inconsistencies. If parser
behavior diverges, consider adding tests to ensure compatibility or updating
both implementations to match a formal specification.

For consistency, prefer using the functions in this module (read_env_file,
load_env_with_override) throughout Python code rather than reimplementing parsing
logic.
"""

from __future__ import annotations

import os
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


def load_env_with_override(root_dir: Path | None = None) -> dict[str, str]:
    """Load environment file with standardized LEYZEN_ENV_FILE override logic.

    Behavior:
    - If LEYZEN_ENV_FILE is set and non-empty, use that file
    - Otherwise, use .env in the root directory

    Args:
        root_dir: Root directory for resolving relative paths.
                  If None, uses current working directory.

    Returns:
        Dictionary of key/value pairs from the resolved environment file.
    """
    if root_dir is None:
        root_dir = Path.cwd()

    env_override = os.environ.get("LEYZEN_ENV_FILE", "").strip()

    if env_override:
        # Use the override file
        env_path = Path(env_override).expanduser()
        if not env_path.is_absolute():
            env_path = (root_dir / env_path).resolve()
        else:
            env_path = env_path.resolve()
    else:
        # Default to .env in root directory
        env_path = (root_dir / ".env").resolve()

    return read_env_file(env_path)
