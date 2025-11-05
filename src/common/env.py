"""Environment parsing helpers shared across Leyzen Vault services.

Note on parser duplication:
This module provides a Python implementation of .env file parsing. A separate Go
implementation exists in tools/cli/internal/env.go (LoadEnvFile). Both parsers must
maintain compatible behavior to ensure consistent configuration handling across the
codebase.

Both implementations are synchronized to ensure identical parsing semantics:

- Quote handling: Both strip matching single and double quotes from values
  - Python: `value[0] == value[-1] and value[0] in {'"', "'"}`
  - Go: Checks if first and last characters are matching quotes (" or ')
- Comment handling: Both ignore lines starting with #
  - Python: `line.startswith("#")`
  - Go: `strings.HasPrefix(trimmed, "#")`
- Empty lines: Both are ignored
  - Python: `if not line`
  - Go: `trimmed == ""`
- Whitespace: Both trim keys and values
  - Python: `key.strip()`, `value.strip()`
  - Go: `strings.TrimSpace(key)`, `strings.TrimSpace(value)`
- Key-value separation: Both split on first `=` only
  - Python: `line.split("=", 1)`
  - Go: `strings.Index(line, "=")` then split

Synchronization rules:
1. When modifying parsing logic in this file, update the Go implementation in
   tools/cli/internal/env.go::LoadEnvFile() to match
2. When modifying parsing logic in Go, update this Python implementation to match
3. Test both implementations with the same .env file to verify compatibility
4. Document any intentional differences in behavior

This duplication is necessary for linguistic reasons (Python services vs Go CLI)
but both implementations must stay synchronized to avoid configuration inconsistencies.

For consistency, prefer using the functions in this module (read_env_file,
load_env_with_override) throughout Python code rather than reimplementing parsing
logic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from common.constants import TIMEZONE_DEFAULT
from common.exceptions import ConfigurationError


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


def resolve_env_file_name(root_dir: Path | None = None) -> str:
    """Resolve the environment file name for use in docker-compose.yml.

    This function determines the filename (not full path) of the environment file
    to use in docker-compose.yml's env_file entries. It follows the same logic
    as load_env_with_override() but returns only the filename.

    Behavior:
    - If LEYZEN_ENV_FILE is set and non-empty, return its filename
    - Otherwise, return ".env"

    Args:
        root_dir: Root directory for resolving relative paths.
                  If None, uses current working directory.

    Returns:
        Filename of the environment file (e.g., ".env" or "custom.env")
    """
    if root_dir is None:
        root_dir = Path.cwd()

    env_override = os.environ.get("LEYZEN_ENV_FILE", "").strip()

    if env_override:
        # Use the override file's name
        env_path = Path(env_override).expanduser()
        if not env_path.is_absolute():
            env_path = (root_dir / env_path).resolve()
        else:
            env_path = env_path.resolve()
        return env_path.name
    else:
        # Default to .env
        return ".env"


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


def parse_timezone(
    env: dict[str, str] | None = None, *, allow_fallback: bool = False
) -> ZoneInfo:
    """Parse timezone from environment variables with consistent fallback logic.

    This function centralizes timezone parsing logic used across the codebase
    to ensure consistent behavior. It reads TIMEZONE from the provided environment
    dictionary or uses load_env_with_override() if not provided.

    Args:
        env: Optional dictionary of environment variables. If None, uses
             load_env_with_override() to load from .env file.
        allow_fallback: If True, falls back to UTC on invalid timezone instead
                       of raising ConfigurationError. Defaults to False.

    Returns:
        ZoneInfo object for the parsed timezone.

    Raises:
        ConfigurationError: If timezone is invalid and allow_fallback is False.
    """
    if env is None:
        env = load_env_with_override()

    # Merge with os.environ to allow runtime overrides
    env_values = env.copy()
    env_values.update(os.environ)

    timezone_name = env_values.get("TIMEZONE", TIMEZONE_DEFAULT).strip()

    try:
        return ZoneInfo(timezone_name)
    except Exception as exc:
        if allow_fallback:
            return ZoneInfo(TIMEZONE_DEFAULT)
        raise ConfigurationError(f"Unknown timezone '{timezone_name}'") from exc
