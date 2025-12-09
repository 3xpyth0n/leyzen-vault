#!/usr/bin/env python3
"""Check storage mode from database configuration."""

import sys
import os
from pathlib import Path

# Bootstrap common modules (same logic as app.py)
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

    from vault.services.external_storage_config_service import (
        ExternalStorageConfigService,
    )
    from flask import Flask

    app = Flask(__name__)

    # Load environment values (same as in app.py)
    try:
        from common.env import load_env_with_override

        env_values = load_env_with_override()
        env_values.update(os.environ)
    except Exception as e:
        print(f"[check_storage_mode] Failed to load env: {e}", file=sys.stderr)
        env_values = os.environ.copy()

    app.config["SECRET_KEY"] = env_values.get("SECRET_KEY", "")

    # Configure database (same as in app.py)
    try:
        from vault.config import get_postgres_url

        postgres_url = get_postgres_url(env_values)
        app.config["SQLALCHEMY_DATABASE_URI"] = postgres_url
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    except Exception as e:
        print(f"[check_storage_mode] Failed to get postgres URL: {e}", file=sys.stderr)
        # If get_postgres_url fails, try to get from environment directly
        app.config["SQLALCHEMY_DATABASE_URI"] = env_values.get("DATABASE_URL", "")

    # Initialize database connection
    with app.app_context():
        from vault.database.schema import db

        db.init_app(app)

        # Try to connect to database with retries (database may not be ready yet)
        import time

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Try to connect to database
                db.session.execute(db.text("SELECT 1"))

                # Connection successful, check storage mode
                if ExternalStorageConfigService.is_enabled(
                    app.config["SECRET_KEY"], app
                ):
                    mode = ExternalStorageConfigService.get_storage_mode(
                        app.config["SECRET_KEY"], app
                    )
                    print(mode)
                    sys.exit(0)
                else:
                    # External storage not enabled, return empty
                    sys.exit(0)
            except Exception as e:
                if attempt < max_retries - 1:
                    # Retry after delay
                    time.sleep(retry_delay)
                    continue
                else:
                    # All retries failed, return empty (will default to normal message)
                    print(
                        f"[check_storage_mode] Failed to check storage mode after {max_retries} attempts: {e}",
                        file=sys.stderr,
                    )
                    pass
except Exception as e:
    # If anything fails, return empty (will default to normal message)
    print(f"[check_storage_mode] Fatal error: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc(file=sys.stderr)
    pass

sys.exit(0)
