#!/usr/bin/env python3
"""
Migration script to update .env file from env.template while preserving existing values.

This script reads the current .env file and the env.template, then generates a new .env
file that:
- Preserves all existing variable values from .env
- Updates the structure and comments to match env.template
- Keeps variables that exist in .env but not in template (with a warning)
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


def parse_env_file(filepath: Path) -> Dict[str, str]:
    """
    Parse an .env file and extract key-value pairs.

    Returns a dictionary mapping variable names to their values.
    Handles quoted values and preserves the exact value format.
    """
    env_vars = {}

    if not filepath.exists():
        return env_vars

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip("\n\r")

            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Match KEY=VALUE pattern
            # This regex handles:
            # - KEY=value
            # - KEY="value"
            # - KEY='value'
            # - KEY= (empty value)
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
            if match:
                key = match.group(1)
                value = match.group(2)

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value

    return env_vars


def extract_key_from_line(line: str) -> Optional[Tuple[str, str, bool]]:
    """
    Extract variable key and value from a template line.

    Returns (key, value, is_commented) if the line contains a variable assignment,
    None otherwise (non-variable comment, empty line, etc.).

    is_commented is True if the variable is commented out (e.g., # KEY=value).
    """
    stripped = line.strip()

    # Skip empty lines
    if not stripped:
        return None

    # Check if it's a commented variable (e.g., # KEY=value or # KEY=)
    # This pattern matches lines that start with # followed by whitespace and a variable
    commented_match = re.match(r"^#\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", stripped)
    if commented_match:
        key = commented_match.group(1)
        value = commented_match.group(2).strip()

        # Remove quotes if present
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        return (key, value, True)

    # Check if it's a regular (non-commented) variable
    if not stripped.startswith("#"):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", stripped)
        if match:
            key = match.group(1)
            value = match.group(2)

            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            return (key, value, False)

    return None


def migrate_env(project_root: Path) -> None:
    """
    Migrate .env file from env.template while preserving existing values.
    """
    env_file = project_root / ".env"
    template_file = project_root / "env.template"

    # Check if template exists
    if not template_file.exists():
        print(f"Error: {template_file} not found", file=sys.stderr)
        sys.exit(1)

    # Parse existing .env file
    existing_vars = parse_env_file(env_file)

    if not existing_vars:
        print(
            f"Warning: No variables found in {env_file} (file may not exist or be empty)",
            file=sys.stderr,
        )

    # Track which variables from .env were used
    used_vars = set()

    # Read template and generate new .env
    new_env_lines = []
    with open(template_file, "r", encoding="utf-8") as f:
        for line in f:
            # Check if this line contains a variable assignment (commented or not)
            var_info = extract_key_from_line(line)

            if var_info:
                key, template_value, is_commented = var_info

                # Use existing value if available, otherwise use template value
                if key in existing_vars:
                    existing_value = existing_vars[key]
                    original_line = line.rstrip("\n\r")

                    if is_commented:
                        # Variable is commented in template but exists in .env - uncomment it
                        # Extract the comment part after the variable (if any)
                        # Pattern: # KEY=value (rest of line might be a comment)
                        # We need to find where the variable assignment ends
                        match = re.match(
                            r"^(\s*)#\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^#]*?)(\s*#.*)?$",
                            original_line,
                        )
                        if match:
                            leading_spaces = match.group(1)
                            # Preserve any comment that was after the variable
                            trailing_comment = match.group(4) if match.group(4) else ""
                            new_line = (
                                leading_spaces
                                + f"{key}={existing_value}{trailing_comment}"
                            )
                        else:
                            # Fallback: simple uncomment
                            new_line = re.sub(
                                r"^(\s*)#\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*",
                                lambda m: f"{m.group(1)}{m.group(2)}={existing_value}",
                                original_line,
                            )
                    else:
                        # Variable is not commented - replace value while preserving formatting
                        # Match: KEY=value (rest of line, which may include comments)
                        match = re.match(
                            r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^#]*?)(\s*#.*)?$",
                            original_line,
                        )
                        if match:
                            leading_spaces = match.group(1)
                            # Preserve comment if present
                            trailing_comment = match.group(4) if match.group(4) else ""
                            new_line = (
                                leading_spaces
                                + f"{key}={existing_value}{trailing_comment}"
                            )
                        else:
                            # Fallback: simple replacement
                            new_line = re.sub(
                                r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*",
                                lambda m: f"{m.group(1)}{m.group(2)}={existing_value}",
                                original_line,
                            )

                    new_env_lines.append(new_line)
                    used_vars.add(key)
                else:
                    # Variable doesn't exist in .env - keep template as-is (commented or not)
                    new_env_lines.append(line.rstrip("\n\r"))
            else:
                # Comment or empty line - keep as-is
                new_env_lines.append(line.rstrip("\n\r"))

    # Check for variables in .env that weren't in template
    unused_vars = set(existing_vars.keys()) - used_vars
    if unused_vars:
        print(
            f"Warning: The following variables from .env were not found in env.template:",
            file=sys.stderr,
        )
        for var in sorted(unused_vars):
            print(f"  - {var}", file=sys.stderr)
        print(
            f"These variables will not be included in the migrated .env file.",
            file=sys.stderr,
        )

    # Write new .env file
    backup_file = project_root / ".env.backup"
    if env_file.exists():
        # Create backup
        print(f"Creating backup: {backup_file}")
        with open(backup_file, "w", encoding="utf-8") as f:
            with open(env_file, "r", encoding="utf-8") as original:
                f.write(original.read())

    print(f"Writing migrated .env file...")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_env_lines))
        if new_env_lines and not new_env_lines[-1].endswith("\n"):
            f.write("\n")

    print(f"Migration complete! Migrated {len(used_vars)} variables.")
    if backup_file.exists():
        print(f"Original .env backed up to: {backup_file}")


def main():
    """Main entry point."""
    # Get project root (parent of tests/ directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    migrate_env(project_root)


if __name__ == "__main__":
    main()
