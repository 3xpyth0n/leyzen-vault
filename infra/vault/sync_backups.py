#!/usr/bin/env python3
"""Synchronize database backups from storage on startup."""

import sys
import os
from pathlib import Path

# Bootstrap common modules
_COMMON_DIR = Path("/common")
if _COMMON_DIR.exists() and _COMMON_DIR.is_dir():
    root_path = str(_COMMON_DIR.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
else:
    _SRC_DIR = Path("/app/src")
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

try:
    # Bootstrap common modules first
    from common.path_setup import bootstrap_entry_point

    bootstrap_entry_point()

    from flask import Flask
    from vault.services.database_backup_service import DatabaseBackupService

    app = Flask(__name__)

    # Load environment values with proper priority: .env file overrides os.environ
    # This ensures .env file values take precedence for security and isolation
    try:
        from common.env import load_env_with_priority

        env_values = load_env_with_priority()
    except Exception:
        # Fallback to os.environ if loading fails

        env_values = dict(os.environ)

    app.config["SECRET_KEY"] = env_values.get("SECRET_KEY", "")
    if not app.config["SECRET_KEY"]:
        # Try to load settings if SECRET_KEY is missing from env
        try:
            from vault.config import load_settings

            settings = load_settings()
            app.config["SECRET_KEY"] = settings.secret_key
        except Exception:
            pass

    if not app.config["SECRET_KEY"]:
        print(
            "Warning: SECRET_KEY not found, cannot sync backups",
            file=sys.stderr,
        )
        sys.exit(0)

    # Configure database
    try:
        from vault.config import get_postgres_url

        postgres_url = get_postgres_url(env_values)
        app.config["SQLALCHEMY_DATABASE_URI"] = postgres_url
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    except Exception as e:
        print(f"Failed to get postgres URL: {e}", file=sys.stderr)
        app.config["SQLALCHEMY_DATABASE_URI"] = env_values.get("DATABASE_URL", "")

    # Initialize database connection
    with app.app_context():
        from vault.database.schema import db

        db.init_app(app)

        # Try to connect to database with retries
        import time

        max_retries = 3
        retry_delay = 1.0

        try:
            for attempt in range(max_retries):
                try:
                    # Try to connect to database
                    db.session.execute(db.text("SELECT 1"))

                    # Connection successful, perform sync
                    print("Synchronizing backups from storage...")
                    service = DatabaseBackupService(app.config["SECRET_KEY"], app)
                    result = service.sync_backups_from_storage()

                    print(
                        f"Sync completed: added {result['added']}, processed {result['processed']}"
                    )
                    db.session.commit()
                    sys.exit(0)

                except Exception as e:
                    db.session.rollback()
                    if attempt < max_retries - 1:
                        # Retry after delay
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(
                            f"Failed to sync backups after {max_retries} attempts: {e}",
                            file=sys.stderr,
                        )
                        pass
        finally:
            try:
                db.session.remove()
            except Exception:
                pass
except Exception as e:
    print(f"Fatal error: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc(file=sys.stderr)
    pass

sys.exit(0)
