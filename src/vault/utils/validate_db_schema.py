#!/usr/bin/env python3
"""Validate that all expected database tables exist after initialization.

This script checks that all tables defined in the SQLAlchemy schema are
actually created in the PostgreSQL database. It's useful for verifying
that a fresh installation creates all required tables correctly.

Usage:
    # From Docker container (recommended):
    docker exec -it vault_web1 python3 /app/tools/validate_db_schema.py

    # From host (if PostgreSQL port is mapped):
    POSTGRES_HOST=localhost POSTGRES_PORT=5432 python tools/validate_db_schema.py

The script reads database connection settings from environment variables
or a .env file (same as the main application).

Note:
  - If running from Docker container, use the default "postgres" hostname
  - If running from host, set POSTGRES_HOST=localhost and ensure PostgreSQL
    port is mapped (docker run -p 5432:5432 ...)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src to path to import vault modules
REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from flask import Flask  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from vault.config import get_postgres_url  # noqa: E402
from common.env import load_env_with_override  # noqa: E402
from vault.database.schema import (  # noqa: E402
    db,
    init_db,
)

# Expected tables (from __tablename__ attributes)
EXPECTED_TABLES = {
    "sso_providers",
    "users",
    "vaultspaces",
    "vaultspace_keys",
    "user_pinned_vaultspaces",
    "files",
    "file_keys",
    "webhooks",
    "devices",
    "quotas",
    "workflows",
    "workflow_executions",
    "behavior_analytics",
    "vaultspace_templates",
    "backup_jobs",
    "replication_targets",
    "public_share_links",
    "rate_limit_tracking",
    "jwt_blacklist",
    "audit_logs",
    "share_links",
    "email_verification_tokens",
    "magic_link_tokens",
    "user_invitations",
    "domain_rules",
    "system_settings",
    "system_secrets",
    "api_keys",
    "schema_migrations",
}


def get_actual_tables(app: Flask) -> set[str]:
    """Get list of actual tables in the database."""
    with app.app_context():
        inspector = inspect(db.engine)
        # Get all table names (excluding system tables)
        all_tables = set(inspector.get_table_names())
        # Filter out PostgreSQL system tables (pg_* and information_schema)
        user_tables = {
            table
            for table in all_tables
            if not table.startswith("pg_") and not table.startswith("sql_")
        }
        return user_tables


def validate_schema() -> tuple[bool, list[str], list[str], str | None]:
    """Validate database schema.

    Returns:
        Tuple of (is_valid, missing_tables, extra_tables, error_message)
    """
    # Load environment variables
    env_values = load_env_with_override()
    env_values.update(dict(os.environ))

    # Create Flask app
    app = Flask(__name__)

    try:
        postgres_url = get_postgres_url(env_values)
    except Exception as e:
        error_msg = (
            f"Failed to get PostgreSQL connection URL: {e}\n"
            "Please ensure POSTGRES_* environment variables are set correctly.\n"
            "If running outside Docker, set POSTGRES_HOST=localhost"
        )
        return False, [], [], error_msg

    app.config["SQLALCHEMY_DATABASE_URI"] = postgres_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize database
    try:
        init_db(app)
    except Exception as e:
        error_msg = (
            f"Failed to initialize database: {e}\n\n"
            "Troubleshooting:\n"
            "1. Ensure PostgreSQL is running and accessible\n"
            "2. Check POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD\n"
            "3. If running outside Docker, use POSTGRES_HOST=localhost instead of 'postgres'\n"
            "4. Verify network connectivity to the database server"
        )
        return False, [], [], error_msg

    # Get actual tables
    actual_tables = get_actual_tables(app)

    # Find missing and extra tables
    missing_tables = EXPECTED_TABLES - actual_tables
    extra_tables = actual_tables - EXPECTED_TABLES

    is_valid = len(missing_tables) == 0

    return is_valid, sorted(missing_tables), sorted(extra_tables), None


def main() -> int:
    """Main entry point."""
    # CLI script output - using print() for direct console output
    print("Validating database schema...")
    print(f"Expected tables: {len(EXPECTED_TABLES)}")
    print()

    is_valid, missing_tables, extra_tables, error_msg = validate_schema()

    # Check for connection/initialization errors
    # CLI script output - using print() for direct console output
    if error_msg:
        print("ERROR: Database connection or initialization failed", file=sys.stderr)
        print(error_msg, file=sys.stderr)
        return 1

    if is_valid and len(extra_tables) == 0:
        print("✓ All expected tables exist in the database.")
        print(f"  Found {len(EXPECTED_TABLES)} tables as expected.")
        return 0

    # Report issues
    if missing_tables:
        print(f"✗ Missing {len(missing_tables)} table(s):")
        for table in missing_tables:
            print(f"  - {table}")
        print()

    if extra_tables:
        print(f"⚠ Found {len(extra_tables)} unexpected table(s):")
        for table in extra_tables:
            print(f"  - {table}")
        print()

    if missing_tables:
        print("ERROR: Some expected tables are missing from the database.")
        print("This indicates a problem with database initialization.")
        return 1

    if extra_tables:
        print("WARNING: Some unexpected tables were found.")
        print("This may indicate leftover tables from previous installations.")
        return 0  # Extra tables are not a critical error

    return 0


if __name__ == "__main__":
    sys.exit(main())
