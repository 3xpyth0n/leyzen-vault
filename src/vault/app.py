"""Flask application for Leyzen Vault backend."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from urllib.parse import urlsplit

import ipaddress

from flask import Flask, current_app
from werkzeug.middleware.proxy_fix import ProxyFix

# Bootstrap common modules
_COMMON_DIR = Path("/common")
if _COMMON_DIR.exists() and _COMMON_DIR.is_dir():
    root_path = str(_COMMON_DIR.parent)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
else:
    _SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

from common.path_setup import bootstrap_entry_point  # noqa: E402

# Internal API tokens are generated randomly and stored in the database

bootstrap_entry_point()


def _is_secure_request(req) -> bool:
    """Best-effort detection of HTTPS requests behind multiple proxies."""

    if getattr(req, "is_secure", False):
        return True

    forwarded_proto = req.headers.get("X-Forwarded-Proto", "")
    if forwarded_proto:
        for token in forwarded_proto.split(","):
            if token.strip().lower() == "https":
                return True

    forwarded = req.headers.get("Forwarded", "")
    if forwarded:
        for entry in forwarded.split(","):
            for token in entry.split(";"):
                token = token.strip().lower()
                if token.startswith("proto=") and token.split("=", 1)[1] == "https":
                    return True

    forwarded_scheme = req.headers.get("X-Forwarded-Scheme", "")
    if forwarded_scheme:
        for token in forwarded_scheme.split(","):
            if token.strip().lower() == "https":
                return True

    try:
        vault_settings = current_app.config.get("VAULT_SETTINGS")
    except Exception:
        vault_settings = None

    vault_url = None
    if vault_settings:
        vault_url = getattr(vault_settings, "vault_url", None)

    if vault_url:
        try:
            parsed = urlsplit(vault_url)
        except Exception:
            parsed = None
        if parsed and parsed.scheme.lower() == "https":
            request_host = _normalize_host(req.headers.get("Host") or req.host)
            target_host = _normalize_host(parsed.netloc)
            if request_host and target_host and request_host == target_host:
                return True

    return False


def _normalize_host(value: str | None) -> str:
    if not value:
        return ""
    host = value.strip().lower()
    if host.endswith(":443"):
        return host[:-4]
    if host.endswith(":80"):
        return host[:-3]
    return host


def _is_ip_host(value: str | None) -> bool:
    if not value:
        return False
    host = _normalize_host(value).split("%")[0]  # strip zone id for IPv6
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _normalize_origin(origin: str | None) -> str | None:
    """Return normalized scheme://host[:port] representation for an origin."""
    if not origin:
        return None
    origin = origin.strip()
    if not origin:
        return None

    try:
        parsed = urlsplit(origin)
    except Exception:
        return None

    if not parsed.scheme or not parsed.netloc:
        return None

    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return normalized.rstrip("/")


from .blueprints.admin import admin_api_bp  # noqa: E402
from .blueprints.auth_api import auth_api_bp  # noqa: E402
from .blueprints.config_api import config_api_bp  # noqa: E402
from .blueprints.files_api_v2 import files_api_bp  # noqa: E402

# Import file_events_api_bp with error handling
# Note: SSE endpoint is disabled but /recent endpoint is needed for polling
file_events_api_bp = None
try:
    from .blueprints.file_events_api import file_events_api_bp  # noqa: E402
except Exception as e:
    # Log error but don't fail startup
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import file_events_api_bp: {e}")
    file_events_api_bp = None
from .blueprints.internal_api import internal_api_bp  # noqa: E402
from .blueprints.quota_api import quota_api_bp as quota_api_v2_bp  # noqa: E402
from .blueprints.search_api import search_api_bp  # noqa: E402
from .blueprints.security import security_bp  # noqa: E402
from .blueprints.sharing_api import sharing_api_bp  # noqa: E402
from .blueprints.sso_api import sso_api_bp  # noqa: E402
from .blueprints.thumbnail_api import thumbnail_api_bp  # noqa: E402
from .blueprints.trash_api import trash_api_bp  # noqa: E402
from .blueprints.external_storage_api import (
    external_storage_api_bp,
)  # noqa: E402
from .blueprints.database_backup_api import (
    database_backup_api_bp,
)  # noqa: E402
from .blueprints.vaultspaces import vaultspace_api_bp  # noqa: E402
from .config import (
    VaultSettings,
    get_postgres_url,
    is_setup_complete,
    load_settings,
)  # noqa: E402
from .database import db, init_db  # noqa: E402
from .services.totp_service import init_totp_service  # noqa: E402

from .services.audit import AuditService  # noqa: E402
from common.services.logging import FileLogger  # noqa: E402
from .services.rate_limiter import RateLimiter  # noqa: E402
from .services.share_link_service import ShareService  # noqa: E402
from .storage import FileStorage  # noqa: E402


def _create_fallback_settings() -> VaultSettings:
    """Create fallback VaultSettings for development/testing.

    This function creates default settings when the main configuration
    cannot be loaded. It attempts to read the timezone from environment
    variables, falling back to UTC if not available or invalid.

    ⚠️ WARNING: This fallback mode requires environment variables to be set.
    Hardcoded secrets have been removed for security. This function should
    NOT be used in production.

    Raises:
        ConfigurationError: If required environment variables are missing

    Returns:
        VaultSettings with values from environment variables
    """
    import os
    from common.env import parse_timezone
    from common.exceptions import ConfigurationError

    # Try to get timezone from environment even in fallback
    # Use allow_fallback=True to gracefully fall back to UTC on error
    fallback_timezone = parse_timezone(allow_fallback=True)

    # Secret key (required)
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigurationError(
            "SECRET_KEY is required (minimum 32 characters). Fallback mode requires environment variables to be set. "
            "This function should NOT be used in production."
        )

    if len(secret_key) < 32:
        raise ConfigurationError(
            "SECRET_KEY must be at least 32 characters long. "
            "Generate a secure key with: openssl rand -hex 32"
        )

    return VaultSettings(
        secret_key=secret_key,
        timezone=fallback_timezone,
        proxy_trust_count=1,
        captcha_length=6,
        captcha_store_ttl=300,
        login_csrf_ttl=900,
        log_file=Path("/dev/shm/vault.log"),
        session_cookie_secure=False,
        max_file_size_mb=100,
        max_uploads_per_hour=50,
        audit_retention_days=90,
    )


def _get_or_generate_internal_api_token(
    env_values: dict[str, str],
    secret_key: str | None = None,
    logger=None,
    app=None,
) -> str:
    """Get or generate INTERNAL_API_TOKEN from environment or database.

    This function centralizes the logic for obtaining the INTERNAL_API_TOKEN.
    Priority:
    1. Environment variable INTERNAL_API_TOKEN (if explicitly set)
    2. Database (SystemSecrets table) - generated randomly on first use
    3. If neither available and SECRET_KEY provided, generate and store in database

    Args:
        env_values: Dictionary containing environment variables
        secret_key: Secret key for encrypting/decrypting the token in database
        logger: Optional logger instance for warning messages
        app: Optional Flask app instance (required for database access)

    Returns:
        The internal API token string
    """
    import os
    import secrets
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    import base64

    # Check environment variables first (explicit override)
    internal_api_token = env_values.get("INTERNAL_API_TOKEN", "")
    if not internal_api_token:
        internal_api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    # If explicitly set in environment, use it
    if internal_api_token:
        return internal_api_token

    # If not set, try to get from database or generate new one
    if not secret_key:
        if logger:
            logger.log(
                "[WARNING] INTERNAL_API_TOKEN not set and SECRET_KEY not available. "
                "Internal API endpoints will be disabled."
            )
        return ""

    # Need app context for database access
    if not app:
        # Try to get current app
        try:
            from flask import current_app

            app = current_app
        except RuntimeError:
            # Not in app context - cannot access database
            if logger:
                logger.log(
                    "[WARNING] Cannot access database for INTERNAL_API_TOKEN. "
                    "Internal API endpoints will be disabled."
                )
            return ""

    # Derive Fernet key from SECRET_KEY for encryption
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"leyzen-vault-internal-token-v1",
        iterations=100000,
        backend=default_backend(),
    )
    fernet_key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
    cipher = Fernet(fernet_key)

    # Ensure we're in app context and database is initialized
    # Use app.app_context() to ensure database is accessible
    from vault.database.schema import SystemSecrets, db

    # Try to get existing token from database
    secret_key_name = "internal_api_token"
    secret_record = None
    try:
        # Verify we can access the database
        with app.app_context():
            # Check if SystemSecrets table exists before querying
            # Handle all exceptions gracefully - table might not exist yet
            try:
                from sqlalchemy import inspect as sql_inspect

                inspector = sql_inspect(db.engine)
                table_exists = "system_secrets" in inspector.get_table_names()
            except Exception:
                # Inspection failed - assume table doesn't exist
                table_exists = False

            if not table_exists:
                # Table doesn't exist - create it
                if logger:
                    logger.log(
                        "[INFO] SystemSecrets table does not exist. Creating it..."
                    )
                try:
                    SystemSecrets.__table__.create(db.engine, checkfirst=True)
                    if logger:
                        logger.log("[INFO] SystemSecrets table created successfully.")
                except Exception as create_error:
                    # Creation failed - might already exist or other issue
                    if logger:
                        logger.log(
                            f"[WARNING] Failed to create SystemSecrets table: {create_error}"
                        )
                secret_record = None
            else:
                # Table exists - query for existing token
                try:
                    secret_record = (
                        db.session.query(SystemSecrets)
                        .filter_by(key=secret_key_name)
                        .first()
                    )
                except Exception as query_error:
                    # Query failed - table might not actually exist despite inspection
                    error_str = str(query_error).lower()
                    if "does not exist" in error_str or "undefinedtable" in error_str:
                        if logger:
                            logger.log(
                                "[INFO] SystemSecrets table does not exist (detected via query error). Creating it..."
                            )
                        try:
                            SystemSecrets.__table__.create(db.engine, checkfirst=True)
                        except Exception:
                            pass  # Ignore creation errors
                        secret_record = None
                    else:
                        # Other query error - log and continue
                        if logger:
                            logger.log(
                                f"[WARNING] Query failed for SystemSecrets: {query_error}"
                            )
                        secret_record = None
    except Exception as e:
        # Any exception - log but don't fail
        # This includes RuntimeError, AttributeError, ProgrammingError, etc.
        if logger:
            error_str = str(e).lower()
            if "does not exist" in error_str or "undefinedtable" in error_str:
                logger.log(
                    "[INFO] SystemSecrets table does not exist. Will be created when storing token."
                )
            else:
                logger.log(
                    f"[WARNING] Database not available for INTERNAL_API_TOKEN: {e}. "
                    "Internal API endpoints will be disabled."
                )
        return ""

    if secret_record:
        # Decrypt and return existing token
        try:
            decrypted_token = cipher.decrypt(
                secret_record.encrypted_value.encode()
            ).decode()
            return decrypted_token
        except Exception as e:
            # Decryption failed - log error and generate new token
            if logger:
                logger.log(
                    f"[WARNING] Failed to decrypt stored INTERNAL_API_TOKEN: {e}. "
                    "Generating new token."
                )
            # Delete corrupted record
            with app.app_context():
                db.session.delete(secret_record)
                db.session.commit()

    # Generate new random token
    new_token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits, URL-safe base64

    # Encrypt token before storing
    encrypted_token = cipher.encrypt(new_token.encode()).decode()

    # Store in database using leyzen_secrets role
    try:
        # Use leyzen_secrets role to write to SystemSecrets
        from vault.database.schema import get_secrets_connection
        from sqlalchemy import text

        try:
            secrets_engine = get_secrets_connection(app, secret_key)
            try:
                # Use engine.begin() for automatic transaction management
                # This ensures the operation is committed correctly in SQLAlchemy 2.0
                with secrets_engine.begin() as secrets_conn:
                    # Check if key already exists
                    result = secrets_conn.execute(
                        text("SELECT id FROM system_secrets WHERE key = :key"),
                        {"key": secret_key_name},
                    )
                    existing = result.fetchone()

                    if existing:
                        # Update existing record
                        secrets_conn.execute(
                            text(
                                """
                                UPDATE system_secrets 
                                SET encrypted_value = :encrypted_value, updated_at = NOW()
                                WHERE key = :key
                                """
                            ),
                            {
                                "key": secret_key_name,
                                "encrypted_value": encrypted_token,
                            },
                        )
                    else:
                        # Insert new record
                        secrets_conn.execute(
                            text(
                                """
                                INSERT INTO system_secrets (key, encrypted_value)
                                VALUES (:key, :encrypted_value)
                                """
                            ),
                            {
                                "key": secret_key_name,
                                "encrypted_value": encrypted_token,
                            },
                        )
            finally:
                secrets_engine.dispose()
        except Exception:
            # leyzen_secrets role not available yet, fall back to regular connection
            raise
    except Exception as secrets_error:
        # Fallback: use regular connection (for first startup)
        with app.app_context():
            # Ensure SystemSecrets table exists before storing
            # Try multiple times to create the table if it doesn't exist
            table_created = False
            max_table_attempts = 3

            for table_attempt in range(1, max_table_attempts + 1):
                try:
                    from sqlalchemy import inspect as sql_inspect

                    inspector = sql_inspect(db.engine)
                    table_exists = "system_secrets" in inspector.get_table_names()

                    if not table_exists:
                        if logger:
                            logger.log(
                                f"[INFO] SystemSecrets table does not exist. Creating it... (attempt {table_attempt}/{max_table_attempts})"
                            )
                        SystemSecrets.__table__.create(db.engine, checkfirst=True)
                        # Verify table was created
                        inspector = sql_inspect(db.engine)
                        table_exists = "system_secrets" in inspector.get_table_names()
                        if table_exists:
                            table_created = True
                            if logger:
                                logger.log(
                                    "[INFO] SystemSecrets table created successfully."
                                )
                            break
                        else:
                            if logger and table_attempt < max_table_attempts:
                                logger.log(
                                    f"[WARNING] Table creation attempt {table_attempt} failed. Retrying..."
                                )
                            import time

                            time.sleep(1.0)  # Wait 1 second before retry
                    else:
                        table_created = True
                        break
                except Exception as create_error:
                    # Table creation failed - log and retry if attempts left
                    if logger:
                        error_msg = str(create_error).lower()
                        if "already exists" in error_msg or "duplicate" in error_msg:
                            # Table already exists - this is fine
                            table_created = True
                            break
                        elif table_attempt < max_table_attempts:
                            logger.log(
                                f"[WARNING] SystemSecrets table creation failed (attempt {table_attempt}/{max_table_attempts}): {create_error}. Retrying..."
                            )
                        else:
                            logger.log(
                                f"[ERROR] Failed to create SystemSecrets table after {max_table_attempts} attempts: {create_error}"
                            )
                    if table_attempt < max_table_attempts:
                        import time

                        time.sleep(1.0)  # Wait 1 second before retry
                    else:
                        # All attempts failed - raise error
                        raise

            if not table_created:
                raise RuntimeError(
                    f"Failed to ensure SystemSecrets table exists after {max_table_attempts} attempts"
                )

            # Check if token already exists (race condition protection)
            existing_record = (
                db.session.query(SystemSecrets).filter_by(key=secret_key_name).first()
            )

            if existing_record:
                # Token already exists - decrypt and return it
                if logger:
                    logger.log(
                        "[INFO] INTERNAL_API_TOKEN already exists in database. Using existing token."
                    )
                try:
                    decrypted_token = cipher.decrypt(
                        existing_record.encrypted_value.encode()
                    ).decode()
                    return decrypted_token
                except Exception as decrypt_error:
                    # Existing token is corrupted - replace it
                    if logger:
                        logger.log(
                            f"[WARNING] Existing INTERNAL_API_TOKEN is corrupted: {decrypt_error}. Replacing it."
                        )
                    db.session.delete(existing_record)
                    db.session.commit()

            # Store new token
            new_secret = SystemSecrets(
                key=secret_key_name,
                encrypted_value=encrypted_token,
            )
            db.session.add(new_secret)
            db.session.commit()

            # Verify token was stored
            verify_record = (
                db.session.query(SystemSecrets).filter_by(key=secret_key_name).first()
            )

            # Force a refresh of the session to ensure we see the committed data
            db.session.expire_all()

            verify_record = (
                db.session.query(SystemSecrets).filter_by(key=secret_key_name).first()
            )

            if verify_record and verify_record.encrypted_value == encrypted_token:
                if logger:
                    logger.log(
                        "[INIT] Generated and stored new INTERNAL_API_TOKEN in database (verified after commit)"
                    )
                # Also verify we can decrypt it
                try:
                    test_decrypt = cipher.decrypt(
                        verify_record.encrypted_value.encode()
                    ).decode()
                    if test_decrypt == new_token:
                        if logger:
                            logger.log(
                                "[INIT] INTERNAL_API_TOKEN encryption/decryption verified successfully"
                            )
                        return new_token
                    else:
                        raise RuntimeError(
                            "Token decryption verification failed - decrypted value doesn't match"
                        )
                except Exception as decrypt_error:
                    raise RuntimeError(
                        f"Token decryption verification failed: {decrypt_error}"
                    ) from decrypt_error
            else:
                # Try once more after a short delay - sometimes there's a replication lag
                import time

                time.sleep(0.5)
                db.session.expire_all()
                verify_record = (
                    db.session.query(SystemSecrets)
                    .filter_by(key=secret_key_name)
                    .first()
                )
                if verify_record and verify_record.encrypted_value == encrypted_token:
                    if logger:
                        logger.log(
                            "[INIT] Generated and stored new INTERNAL_API_TOKEN in database (verified after retry)"
                        )
                    return new_token
                else:
                    raise RuntimeError(
                        f"INTERNAL_API_TOKEN was stored but verification failed after retry. "
                        f"Expected token exists: {verify_record is not None}, "
                        f"Values match: {verify_record.encrypted_value == encrypted_token if verify_record else False}"
                    )

    except Exception as e:
        # Database error - rollback and raise to allow retry
        try:
            with app.app_context():
                db.session.rollback()
        except Exception:
            pass  # Ignore rollback errors

        if logger:
            import traceback

            logger.log(
                f"[ERROR] Failed to store INTERNAL_API_TOKEN in database: {e}\n{traceback.format_exc()}"
            )
        # Re-raise to allow retry mechanism in create_app()
        raise


def _calculate_pool_settings(workers: int) -> dict[str, object]:
    """Calculate optimal SQLAlchemy pool settings based on number of workers.

    Uses adaptive formulas that scale appropriately with the number of workers,
    matching deployment sizes from env.template:
    - Small (1-10 users): 2-3 workers
    - Medium (10-100 users): 3-5 workers
    - Large (100+ users): 5-10 workers

    The pool size is calculated to provide sufficient connections without wasting
    resources. With Uvicorn workers, each worker has its own pool, so total
    connections = (pool_size + max_overflow) × workers.

    Examples:
        - 2 workers (1-10 users): pool_size=5, max_overflow=10 → 30 total connections
        - 4 workers (10-100 users): pool_size=8, max_overflow=12 → 80 total connections
        - 10 workers (100+ users): pool_size=20, max_overflow=30 → 500 total connections

    Args:
        workers: Number of Uvicorn workers (from VAULT_WORKERS)

    Returns:
        Dictionary with SQLAlchemy engine options for connection pooling
    """
    # Adaptive pool sizing: conservative for small deployments, scaling up for larger ones
    # Formula: pool_size starts at 5 for small deployments, scales with workers
    # This provides ~15-30 connections per worker, which is sufficient for concurrent requests
    pool_size = max(5, workers * 2)

    # max_overflow: additional connections for traffic spikes
    # Smaller relative overhead for small deployments, more headroom for larger ones
    max_overflow = max(10, workers * 3)

    # Cap max_overflow to prevent excessive connections (safety limit)
    max_overflow = min(max_overflow, 100)

    # Warn if configuration seems excessive (rare edge case)
    if pool_size > 50:
        import warnings

        warnings.warn(
            f"Large pool_size ({pool_size}) calculated for {workers} workers. "
            "Consider if PostgreSQL max_connections is sufficient.",
            UserWarning,
        )

    return {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": 30,  # Timeout when getting connection from pool
        "pool_recycle": 3600,  # Recycle connections after 1 hour to prevent stale connections
        "pool_pre_ping": True,  # Verify connections before using (detects stale connections)
        "connect_args": {
            "connect_timeout": 10,  # Connection timeout
            # PostgreSQL connection options to prevent deadlocks and long-running transactions
            # - lock_timeout: Maximum time to wait for a lock (5 seconds)
            # - statement_timeout: Maximum time for a single statement (30 seconds)
            # - idle_in_transaction_session_timeout: Kill idle transactions (30 seconds, reduced from 60s)
            "options": "-c lock_timeout=5000 -c statement_timeout=30000 -c idle_in_transaction_session_timeout=30000",
        },
    }


def create_app(
    storage_dir: Path | None = None,
    *args: object,
    **kwargs: object,
) -> Flask:
    """Create and configure the Flask application."""
    # Get the directory containing this file
    vault_dir = Path(__file__).parent

    # Check if dist/ exists (production build) or use static/ (development)
    static_dir = vault_dir / "static" / "dist"
    if not static_dir.exists():
        static_dir = vault_dir / "static"

    # Also keep reference to original static folder for fallback
    original_static_dir = vault_dir / "static"

    # Don't use Flask's default static folder mechanism - we'll handle it manually
    app = Flask(
        __name__,
        template_folder=str(vault_dir / "templates"),
        static_folder=None,  # Disable default static file serving
        static_url_path=None,
    )

    # Load environment values with proper priority: .env file overrides os.environ
    # This ensures .env file values take precedence for security and isolation
    import os

    env_values = {}
    try:
        # Import here to avoid circular dependency with common.env during module initialization
        from common.env import load_env_with_priority

        env_values = load_env_with_priority()
    except Exception:
        # Fallback to os.environ if loading fails
        env_values = dict(os.environ)

    # SECURITY: Detect production environment with strict validation
    # Default to production for security (hide error details by default)
    leyzen_env = env_values.get("LEYZEN_ENVIRONMENT", "").strip().lower()
    is_production = leyzen_env not in ("dev", "development")

    # Additional production checks: verify critical production settings
    if is_production:
        # In production, verify critical security settings
        secret_key = env_values.get("SECRET_KEY", "").strip()
        if len(secret_key) < 32:
            raise RuntimeError(
                "SECURITY ERROR: SECRET_KEY must be at least 32 characters in production. "
                "Generate a secure key with: openssl rand -hex 32"
            )

        # Check for development indicators that should not be present in production
        if leyzen_env in ("dev", "development"):
            raise RuntimeError(
                "SECURITY ERROR: LEYZEN_ENVIRONMENT is set to development mode in production. "
                "This is a security risk. Remove LEYZEN_ENVIRONMENT or set it to 'production'."
            )

        # Warn if session cookies are not secure in production
        session_cookie_secure = (
            env_values.get("SESSION_COOKIE_SECURE", "").strip().lower()
        )
        if session_cookie_secure not in ("true", "1", "yes"):
            import warnings

            warnings.warn(
                "SECURITY WARNING: SESSION_COOKIE_SECURE is not enabled in production. "
                "Session cookies should be marked as Secure when using HTTPS. "
                "Set SESSION_COOKIE_SECURE=true in your .env file.",
                UserWarning,
            )

    app.config["IS_PRODUCTION"] = is_production

    # Load settings
    try:
        settings = load_settings()
        app.config["VAULT_SETTINGS"] = settings
        app.config["SECRET_KEY"] = settings.secret_key
        # Configure session cookies
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        )
        # Initialize logger
        logger = FileLogger(settings)
        app.config["LOGGER"] = logger

        # Configure PostgreSQL database
        try:
            # For first startup, use POSTGRES_USER to create roles
            secret_key = settings.secret_key

            # Start with POSTGRES_USER (for role creation)
            postgres_url = get_postgres_url(env_values)
            app.config["SQLALCHEMY_DATABASE_URI"] = postgres_url
            app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
            app.config["SQLALCHEMY_COMMIT_ON_TEARDOWN"] = (
                False  # Explicitly disable auto-commit on teardown
            )
            # Configure connection pool for multiprocessing (Uvicorn workers)
            # The pool settings are auto-adapted based on the number of workers to ensure
            # optimal performance for different deployment sizes (small/medium/large).
            # Each worker has its own connection pool, so total PostgreSQL connections =
            # (pool_size + max_overflow) × number_of_workers
            #
            # Adaptive scaling examples (based on env.template recommendations):
            # - 2 workers (small, 1-10 users): ~30 total connections
            # - 4 workers (medium, 10-100 users): ~80 total connections
            # - 10 workers (large, 100+ users): ~500 total connections
            #
            # The pool automatically scales with VAULT_WORKERS, so adjusting workers is sufficient
            # to optimize for your deployment size. No additional configuration needed.
            import os

            vault_workers = int(os.environ.get("VAULT_WORKERS", "2"))
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = _calculate_pool_settings(
                vault_workers
            )

            # Initialize db_initialized_by_this_worker to False before try block
            # This ensures it's accessible even if the try block fails
            db_initialized_by_this_worker = False

            # Initialize database (this will create roles if needed)
            # Only log initialization messages if this worker actually performed the initialization
            try:
                db_initialized_by_this_worker = init_db(app)

                # Note: We keep using POSTGRES_USER for the default database connection
                # The application can use the leyzen_app role by reading the password from system_secrets
                # when needed, but we don't change the default connection after initialization
                # to avoid SQLAlchemy reinitialization issues (SQLAlchemy doesn't allow db.init_app() twice)

                if db_initialized_by_this_worker:
                    logger.log("[INIT] PostgreSQL database initialized")
                    logger.flush()
                    # jti column is already verified in init_db() - no need to check again
            except Exception as db_exc:
                # Log the error with full details
                # Import traceback here to avoid importing it at module level if not needed
                import traceback

                error_details = f"Failed to initialize PostgreSQL: {db_exc}\n{traceback.format_exc()}"
                logger.log(f"[ERROR] {error_details}")

                # In production, fail startup if PostgreSQL is unavailable
                # In development mode, allow fallback for testing
                if is_production:
                    raise RuntimeError(
                        "PostgreSQL database initialization failed. "
                        "Leyzen Vault requires PostgreSQL to run in production mode. "
                        "Please ensure PostgreSQL is available and properly configured. "
                        "Set LEYZEN_ENVIRONMENT=dev only for development/testing."
                    ) from db_exc
                else:
                    # Development mode: log warning but continue
                    logger.log(
                        "[WARNING] Continuing without PostgreSQL (development mode only). "
                        "This is not recommended for production use."
                    )
                    # Continue without PostgreSQL for development/testing only
        except Exception as db_config_exc:
            # If database configuration fails completely, log and continue
            # (this should not happen in normal operation)
            logger.log(
                f"[ERROR] Database configuration failed: {db_config_exc}. "
                "Application may not function correctly."
            )

        # Internal API token for orchestrator operations
        # Derive deterministically from SECRET_KEY (like DOCKER_PROXY_TOKEN)
        # This avoids database dependency and ensures vault and orchestrator use the same token
        # CRITICAL: This must be set even if init_db() fails, so place it after the try/except
        internal_api_token = ""
        try:
            # Check environment variable first (explicit override)
            internal_api_token = env_values.get("INTERNAL_API_TOKEN", "")
            if not internal_api_token:
                import os

                internal_api_token = os.environ.get("INTERNAL_API_TOKEN", "")

            # If not explicitly set, derive from SECRET_KEY
            if not internal_api_token:
                if not settings or not settings.secret_key:
                    logger.log(
                        "[ERROR] Cannot derive INTERNAL_API_TOKEN: SECRET_KEY not available in settings"
                    )
                    internal_api_token = ""
                else:
                    from common.token_utils import derive_internal_api_token

                    internal_api_token = derive_internal_api_token(settings.secret_key)
                    if db_initialized_by_this_worker:
                        logger.log(
                            f"[INIT] INTERNAL_API_TOKEN derived from SECRET_KEY (deterministic, no database required): {internal_api_token[:16]}..."
                        )
            else:
                if db_initialized_by_this_worker:
                    logger.log(
                        "[INIT] INTERNAL_API_TOKEN set from environment variable (explicit override)"
                    )
        except Exception as token_error:
            import traceback

            logger.log(
                f"[ERROR] Failed to set INTERNAL_API_TOKEN: {token_error}\n"
                f"{traceback.format_exc()}"
            )
            internal_api_token = ""

        # Always set the token in config, even if empty
        app.config["INTERNAL_API_TOKEN"] = internal_api_token
        if internal_api_token:
            if db_initialized_by_this_worker:
                logger.log(
                    f"[INIT] INTERNAL_API_TOKEN configured successfully (length: {len(internal_api_token)})"
                )
        else:
            # Error logs should always be shown
            logger.log(
                "[ERROR] INTERNAL_API_TOKEN is empty - internal API will be disabled"
            )

        # SECURITY: Verify production mode detection at startup
        if is_production:
            if db_initialized_by_this_worker:
                logger.log(
                    "[INIT] Running in PRODUCTION mode - security checks enabled"
                )
        else:
            if db_initialized_by_this_worker:
                logger.log(
                    "[INIT] Running in DEVELOPMENT mode - permissive security checks"
                )
            import warnings

            warnings.warn(
                "WARNING: Application is running in DEVELOPMENT mode. "
                "This should never be used in production. "
                "Set LEYZEN_ENVIRONMENT=production for production deployments.",
                UserWarning,
            )

        # jti column is already verified in init_db() - no need to check again here
        # This prevents SQLAlchemy errors and duplicate checks across workers

        # Initialize TOTP service for 2FA
        init_totp_service(settings.secret_key)

        # Check if setup is complete
        try:
            if not is_setup_complete(app, quiet=True):
                if db_initialized_by_this_worker:
                    logger.log(
                        "[WARNING] Setup not complete. Visit /setup to create superadmin account."
                    )
            else:
                if db_initialized_by_this_worker:
                    logger.log("[INIT] Setup complete - users exist in database")
                    logger.flush()
        except Exception as setup_check_error:
            logger.log(f"[WARNING] Failed to check setup status: {setup_check_error}")
            logger.flush()
    except Exception as exc:
        # Fallback for development/testing only - NOT allowed in production
        # Fallback requires environment variables to be set
        # Secrets are loaded from environment variables

        # SECURITY: Prevent fallback mode in production
        # If we're in production mode, fail fast rather than using fallback settings
        if is_production:
            raise RuntimeError(
                "Cannot start in production mode without valid configuration. "
                "The application failed to load settings and fallback mode is not allowed in production. "
                "Please check your environment variables and configuration files. "
                "Set LEYZEN_ENVIRONMENT=dev only for development/testing."
            ) from exc

        # Set IS_PRODUCTION if not already set (default to False for fallback mode)
        if "IS_PRODUCTION" not in app.config:
            app.config["IS_PRODUCTION"] = is_production

        fallback_settings = _create_fallback_settings()
        app.config["SECRET_KEY"] = fallback_settings.secret_key
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=False,
        )
        app.config["VAULT_SETTINGS"] = fallback_settings
        app.config["LOGGER"] = FileLogger(fallback_settings)
        # Internal API token for orchestrator operations
        # In fallback mode, database may not be available, so use environment variable only
        import os

        internal_api_token = env_values.get("INTERNAL_API_TOKEN", "") or os.environ.get(
            "INTERNAL_API_TOKEN", ""
        )
        if not internal_api_token:
            # In fallback mode without database, cannot generate token
            # This is acceptable for development/testing only
            internal_api_token = ""
        app.config["INTERNAL_API_TOKEN"] = internal_api_token

    # SECURITY: Configure allowed origins (CORS + Origin validation)
    # If ALLOWED_ORIGINS is not set, VAULT_URL will be used as fallback
    vault_settings = app.config.get("VAULT_SETTINGS")
    trust_count = getattr(vault_settings, "proxy_trust_count", 1)
    if trust_count < 0:
        trust_count = 0
    app.wsgi_app = ProxyFix(  # type: ignore[assignment]
        app.wsgi_app,
        x_for=trust_count,
        x_proto=trust_count,
        x_host=trust_count,
        x_port=trust_count,
    )
    allowed_origins_value = (
        env_values.get("VAULT_ALLOWED_ORIGINS")
        or env_values.get("ALLOWED_ORIGINS")
        or env_values.get("CORS_ALLOWED_ORIGINS")
    )
    allowed_origins: list[str] = []
    if allowed_origins_value:
        for origin in allowed_origins_value.split(","):
            normalized = origin.strip()
            if normalized:
                allowed_origins.append(normalized.rstrip("/"))

    # SECURITY: Use VAULT_URL as fallback if ALLOWED_ORIGINS is empty
    if not allowed_origins and vault_settings and vault_settings.vault_url:
        allowed_origins.append(vault_settings.vault_url.rstrip("/"))

    # SECURITY: Validate CORS configuration at startup
    if is_production:
        if not allowed_origins:
            # In production, log warning but allow startup with empty origins
            # This allows the application to start and CORS can be configured later
            logger.log(
                "[WARNING] ALLOWED_ORIGINS is empty in production. "
                "CORS is not configured. Set VAULT_ALLOWED_ORIGINS or ALLOWED_ORIGINS in your .env file. "
                "Application will start but CORS requests may be blocked."
            )
        # Validate that origins are not wildcards or localhost in production
        for origin in allowed_origins:
            if origin == "*":
                raise RuntimeError(
                    "SECURITY ERROR: Wildcard CORS origin (*) is not allowed in production. "
                    "Specify explicit origins in ALLOWED_ORIGINS."
                )
            if "localhost" in origin.lower() or "127.0.0.1" in origin:
                import warnings

                warnings.warn(
                    f"SECURITY WARNING: Localhost origin '{origin}' is configured in production. "
                    "This should only be used in development.",
                    UserWarning,
                )

    app.config["ALLOWED_ORIGINS"] = allowed_origins
    app.config["ALLOWED_ORIGINS_NORMALIZED"] = {
        normalized
        for normalized in (_normalize_origin(origin) for origin in allowed_origins)
        if normalized
    }

    # Configure development allowed origins (for permissive but still active validation)
    allowed_origins_dev_value = env_values.get("ALLOWED_ORIGINS_DEV", "")
    allowed_origins_dev: list[str] = []
    if allowed_origins_dev_value:
        for origin in allowed_origins_dev_value.split(","):
            normalized = origin.strip()
            if normalized:
                allowed_origins_dev.append(normalized.rstrip("/"))
    app.config["ALLOWED_ORIGINS_DEV"] = allowed_origins_dev

    # Configure internal API IP whitelist (optional, for additional security)
    internal_api_allowed_ips_value = env_values.get("INTERNAL_API_ALLOWED_IPS", "")
    internal_api_allowed_ips: list[str] = []
    if internal_api_allowed_ips_value:
        for ip in internal_api_allowed_ips_value.split(","):
            normalized_ip = ip.strip()
            if normalized_ip:
                internal_api_allowed_ips.append(normalized_ip)
    app.config["INTERNAL_API_ALLOWED_IPS"] = internal_api_allowed_ips
    # Default list of headers allowed for CORS requests
    app.config.setdefault(
        "ALLOWED_CORS_HEADERS",
        "Authorization, Content-Type, X-Requested-With, Accept, X-CSRF-Token",
    )

    # CSRF protection disabled - using JWT-only authentication
    # JWT tokens in Authorization headers are protected by Same-Origin Policy
    # Additional security provided by Origin/Referer validation in jwt_required decorator
    # csrf.init_app(app)  # Disabled - not needed for JWT-based API
    # No additional configuration needed for FormData uploads

    # Default paths - ensure they are Path objects
    if storage_dir is None:
        storage_dir = Path("/data")
    elif not isinstance(storage_dir, Path):
        # Convert to Path if it's not already a Path object
        storage_dir = Path(str(storage_dir))

    # Source directory for persistent storage (mounted from vault-data-source volume)
    # Note: source_dir should point to the parent directory, FileStorage will handle /files subdirectory
    source_dir = Path("/data-source") if Path("/data-source").exists() else None

    # Check storage mode to determine if local storage is needed
    storage_mode = "local"
    secret_key = env_values.get("SECRET_KEY", "")
    if secret_key:
        try:
            from vault.services.external_storage_config_service import (
                ExternalStorageConfigService,
            )

            # We need app context to check storage mode, but we can't use current_app here
            # So we'll check it later after app is created, but we can prepare the check
            storage_mode = "local"  # Will be updated after app context is available
        except Exception:
            pass

    # Initialize storage with primary directory (tmpfs) and source directory (persistent)
    # FileStorage will check source_dir/files if file is not found in storage_dir/files
    storage = FileStorage(storage_dir, source_dir=source_dir)

    # Check if S3-only mode is enabled and log appropriate message
    # This check needs to happen after app is created but before logger is fully initialized
    # We'll do a preliminary check here and log later after app context is available
    _check_s3_only_mode = False
    if secret_key:
        try:
            # Try to check storage mode (may fail if DB not ready, that's OK)
            from vault.services.external_storage_config_service import (
                ExternalStorageConfigService,
            )

            # We can't use app here yet, so we'll check later
            _check_s3_only_mode = True
        except Exception:
            pass

    # Initialize IP enrichment service (uses free public APIs, no configuration needed)
    from vault.services.ip_enrichment import IPEnrichmentService

    ip_enrichment_service = IPEnrichmentService()

    # Initialize audit service (uses PostgreSQL)
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            audit_service = AuditService(
                timezone=settings.timezone,
                retention_days=settings.audit_retention_days,
                ip_enrichment_service=ip_enrichment_service,
            )
        else:
            # Fallback: use UTC and default retention
            from zoneinfo import ZoneInfo

            audit_service = AuditService(
                timezone=ZoneInfo("UTC"),
                retention_days=90,
                ip_enrichment_service=ip_enrichment_service,
            )
    except Exception:
        # Fallback: use UTC and default retention
        from zoneinfo import ZoneInfo

        audit_service = AuditService(
            timezone=ZoneInfo("UTC"),
            retention_days=90,
            ip_enrichment_service=ip_enrichment_service,
        )

    # Initialize share service (uses PostgreSQL)
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            share_service = ShareService(timezone=settings.timezone)
        else:
            # Fallback: use UTC
            from zoneinfo import ZoneInfo

            share_service = ShareService(timezone=ZoneInfo("UTC"))
    except Exception:
        # Fallback: use UTC
        from zoneinfo import ZoneInfo

        share_service = ShareService(timezone=ZoneInfo("UTC"))

    # Initialize rate limiter
    try:
        settings = app.config.get("VAULT_SETTINGS")
        if settings:
            rate_limiter = RateLimiter(settings)
        else:
            # Fallback: create with default settings
            fallback_settings = _create_fallback_settings()
            rate_limiter = RateLimiter(fallback_settings)
    except Exception:
        # Fallback rate limiter
        fallback_settings = _create_fallback_settings()
        rate_limiter = RateLimiter(fallback_settings)

    # Store services in app config
    app.config["VAULT_STORAGE"] = storage
    app.config["VAULT_AUDIT"] = audit_service
    app.config["VAULT_SHARE"] = share_service
    app.config["VAULT_RATE_LIMITER"] = rate_limiter
    # Internal API token is already set earlier after database initialization
    # If not set (e.g., in fallback mode), try to get from environment
    if "INTERNAL_API_TOKEN" not in app.config or not app.config.get(
        "INTERNAL_API_TOKEN"
    ):
        import os

        internal_api_token = env_values.get("INTERNAL_API_TOKEN", "") or os.environ.get(
            "INTERNAL_API_TOKEN", ""
        )
        app.config["INTERNAL_API_TOKEN"] = internal_api_token

    # Start background thread for automatic audit log cleanup
    def _audit_cleanup_worker() -> None:
        """Background worker to periodically clean up old audit logs."""
        # Import here to avoid importing at module level if worker thread is not started
        import time
        import logging

        logger = logging.getLogger(__name__)
        while True:
            try:
                time.sleep(3600)  # Run every hour
                # Use application context for database operations
                with app.app_context():
                    deleted_count = audit_service.cleanup_old_logs()
                    if deleted_count > 0:
                        logger.log(f"Cleaned up {deleted_count} old audit log entries")
            except Exception as e:
                logger.log(f"Error during audit log cleanup: {e}")

    # Import threading here to avoid importing at module level if cleanup thread is not started
    import threading

    cleanup_thread = threading.Thread(target=_audit_cleanup_worker, daemon=True)
    cleanup_thread.start()

    # Start background thread for periodic orphaned file cleanup
    def _orphaned_files_cleanup_worker() -> None:
        """Background worker to periodically clean up orphaned files."""
        # Import here to avoid importing at module level if worker thread is not started
        import time
        import logging

        logger = logging.getLogger(__name__)
        while True:
            try:
                time.sleep(3600)  # Run every hour
                # Use application context for database operations
                with app.app_context():
                    try:
                        from common.services.file_promotion_service import (
                            FilePromotionService,
                        )
                        from common.services.sync_validation_service import (
                            SyncValidationService,
                        )
                        from vault.database.schema import File, db

                        # Initialize validation service with database
                        validation_service = SyncValidationService(
                            db_session=db.session,
                            File_model=File,
                            logger=logger,
                        )
                        promotion_service = FilePromotionService(
                            validation_service=validation_service,
                            logger_instance=logger,
                        )

                        if storage.source_dir:
                            result = promotion_service.cleanup_orphaned_files(
                                target_dir=storage.source_dir,
                                base_dir=storage.storage_dir / "files",
                                dry_run=False,
                            )
                            deleted_count = result.get("deleted_count", 0)
                            if deleted_count > 0:
                                logger.info(
                                    f"Cleaned up {deleted_count} orphaned files from persistent storage"
                                )
                    except Exception as cleanup_error:
                        logger.error(
                            f"Error during orphaned files cleanup: {cleanup_error}"
                        )
            except Exception as e:
                logger.error(f"Error in orphaned files cleanup worker: {e}")

    orphaned_cleanup_thread = threading.Thread(
        target=_orphaned_files_cleanup_worker, daemon=True
    )
    orphaned_cleanup_thread.start()

    # Start background thread for periodic file promotion
    # This ensures files in tmpfs are promoted to persistent storage even if
    # immediate promotion during upload fails
    def _periodic_promotion_worker() -> None:
        """Background worker to periodically promote files from tmpfs to persistent storage."""
        import time
        import logging

        logger = logging.getLogger(__name__)
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                # Use application context for database operations
                with app.app_context():
                    try:
                        from common.services.file_promotion_service import (
                            FilePromotionService,
                        )
                        from common.services.sync_validation_service import (
                            SyncValidationService,
                        )
                        from vault.database.schema import File, db

                        storage = app.config.get("VAULT_STORAGE")
                        if not storage or not storage.source_dir:
                            continue

                        # Initialize services
                        validation_service = SyncValidationService(
                            db_session=db.session,
                            File_model=File,
                            logger=logger,
                        )
                        promotion_service = FilePromotionService(
                            validation_service=validation_service,
                            logger_instance=logger,
                        )

                        # Load whitelist
                        validation_service.load_whitelist()

                        # Get all files from database
                        files = (
                            db.session.query(File)
                            .filter(File.deleted_at.is_(None))
                            .all()
                        )

                        promoted_count = 0
                        for file_obj in files:
                            storage_ref = file_obj.storage_ref
                            # Normalize storage_ref
                            if "/" in storage_ref:
                                storage_ref = storage_ref.split("/")[-1]

                            # Check if file exists in tmpfs but not in persistent storage
                            tmpfs_path = storage.get_file_path(storage_ref)
                            source_path = storage.get_source_file_path(storage_ref)

                            if tmpfs_path.exists() and (
                                not source_path or not source_path.exists()
                            ):
                                # File is in tmpfs but not in persistent storage - promote it
                                try:
                                    success, error_msg = promotion_service.promote_file(
                                        file_id=storage_ref,
                                        source_path=tmpfs_path,
                                        target_dir=storage.source_dir,
                                        base_dir=storage.storage_dir / "files",
                                    )
                                    if success:
                                        promoted_count += 1
                                        logger.log(
                                            f"[PERIODIC PROMOTION] Promoted file {storage_ref} to persistent storage"
                                        )
                                    else:
                                        logger.log(
                                            f"[PERIODIC PROMOTION] Failed to promote file {storage_ref}: {error_msg}"
                                        )
                                except Exception as e:
                                    logger.log(
                                        f"[PERIODIC PROMOTION ERROR] Exception promoting {storage_ref}: {e}"
                                    )

                        if promoted_count > 0:
                            logger.log(
                                f"[PERIODIC PROMOTION] Promoted {promoted_count} files to persistent storage"
                            )
                    except Exception as promotion_error:
                        logger.log(
                            f"Error during periodic file promotion: {promotion_error}"
                        )
            except Exception as e:
                logger.log(f"Error in periodic promotion worker: {e}")

    periodic_promotion_thread = threading.Thread(
        target=_periodic_promotion_worker, daemon=True
    )
    periodic_promotion_thread.start()

    # Initialize external storage worker and metrics
    try:
        from vault.services.external_storage_worker import ExternalStorageWorker
        from vault.services.external_storage_config_service import (
            ExternalStorageConfigService,
        )
        from vault.services.external_storage_metrics import (
            ExternalStorageMetricsService,
        )

        secret_key = app.config.get("SECRET_KEY", "")
        if secret_key:
            # Initialize metrics service
            metrics_service = ExternalStorageMetricsService()
            app.config["EXTERNAL_STORAGE_METRICS"] = metrics_service

            external_storage_worker = ExternalStorageWorker(
                secret_key=secret_key, app=app, local_storage=storage
            )
            app.config["EXTERNAL_STORAGE_WORKER"] = external_storage_worker

            # Start worker if external storage is enabled
            if ExternalStorageConfigService.is_enabled(secret_key, app):
                external_storage_worker.start()
                if db_initialized_by_this_worker:
                    logger.log("[INIT] External storage worker started")
    except Exception as e:
        logger.log(f"[INIT] Failed to initialize external storage worker: {e}")

    # Initialize database backup worker
    try:
        from vault.services.database_backup_worker import DatabaseBackupWorker
        from vault.services.database_backup_config_service import (
            DatabaseBackupConfigService,
        )

        secret_key = app.config.get("SECRET_KEY", "")
        if secret_key:
            database_backup_worker = DatabaseBackupWorker(
                secret_key=secret_key, app=app
            )
            app.config["DATABASE_BACKUP_WORKER"] = database_backup_worker

            # Start worker if database backup is enabled
            if DatabaseBackupConfigService.is_enabled(secret_key, app):
                database_backup_worker.start()
                if db_initialized_by_this_worker:
                    logger.log("[INIT] Database backup worker started")
    except Exception as e:
        logger.log(f"[INIT] Failed to initialize database backup worker: {e}")

    # Continue with external storage worker logging
    try:
        from vault.services.external_storage_config_service import (
            ExternalStorageConfigService,
        )

        secret_key = app.config.get("SECRET_KEY", "")
        if secret_key:
            # Check storage mode and log appropriate message about empty directories
            storage_mode = ExternalStorageConfigService.get_storage_mode(
                secret_key, app
            )
            if storage_mode == "s3":
                # Check if source directory is empty (expected in S3-only mode)
                if source_dir and source_dir.exists():
                    source_files_dir = source_dir / "files"
                    if source_files_dir.exists() and not any(
                        source_files_dir.iterdir()
                    ):
                        logger.log(
                            "[INIT] S3-only mode is enabled. No files will be written to local disk. "
                            "You can modify this setting from the admin interface, Integrations tab."
                        )
                    elif not source_files_dir.exists() or not any(
                        source_files_dir.iterdir()
                    ):
                        logger.log(
                            "[INIT] S3-only mode is enabled. No files will be written to local disk. "
                            "You can modify this setting from the admin interface, Integrations tab."
                        )
                else:
                    logger.log(
                        "[INIT] S3-only mode is enabled. No files will be written to local disk. "
                        "You can modify this setting from the admin interface, Integrations tab."
                    )
    except Exception as worker_error:
        logger.log(
            f"[WARNING] Failed to initialize external storage worker: {worker_error}"
        )
        # Don't fail startup if worker initialization fails
        app.config["EXTERNAL_STORAGE_WORKER"] = None
        app.config["EXTERNAL_STORAGE_METRICS"] = None

    # Storage cleanup worker runs in orchestrator service
    # Storage cleanup is triggered via internal API endpoint from orchestrator
    # Autonomous cleanup for orphaned files in persistent storage also runs here

    def _origin_is_allowed_for_request(origin: str | None) -> bool:
        """Check if the provided Origin header is allowed for this request."""
        if not origin:
            # No origin header - allow for same-origin requests
            return True

        normalized_origin = _normalize_origin(origin)
        if not normalized_origin:
            return False

        from flask import request

        host_origin = _normalize_origin(f"{request.scheme}://{request.host}")
        allowed_set = app.config.get("ALLOWED_ORIGINS_NORMALIZED", set())

        # Allow same-origin requests (exact match)
        if host_origin and normalized_origin == host_origin:
            return True

        # Allow localhost variants (localhost, 127.0.0.1, [::1]) regardless of port
        # This handles cases where browser sends different localhost formats
        if host_origin and normalized_origin:
            # Extract hostname from origins (without scheme and port)
            try:
                from urllib.parse import urlparse

                host_parsed = urlparse(host_origin)
                origin_parsed = urlparse(normalized_origin)

                # Check if both are localhost variants
                localhost_variants = {"localhost", "127.0.0.1", "[::1]", "::1"}
                host_hostname = host_parsed.hostname or ""
                origin_hostname = origin_parsed.hostname or ""

                if (
                    host_hostname.lower() in localhost_variants
                    and origin_hostname.lower() in localhost_variants
                    and host_parsed.scheme == origin_parsed.scheme
                ):
                    return True
            except Exception:
                # If parsing fails, fall through to normal check
                pass

        return normalized_origin in allowed_set

    # Register blueprints
    app.register_blueprint(admin_api_bp)  # Admin API
    app.register_blueprint(auth_api_bp)  # JWT-based auth API
    app.register_blueprint(config_api_bp)  # Configuration API
    app.register_blueprint(files_api_bp)  # Advanced files API v2
    app.register_blueprint(external_storage_api_bp)  # External storage API
    app.register_blueprint(database_backup_api_bp)  # Database backup API
    if file_events_api_bp is not None:
        try:
            app.register_blueprint(file_events_api_bp)  # File events API (SSE)
        except Exception as e:
            logger.log(f"Failed to register file_events_api_bp: {e}")
            # Don't fail startup if file events API fails to register
            # This allows the application to continue running without real-time sync

    app.register_blueprint(internal_api_bp)  # Internal API for orchestrator
    app.register_blueprint(search_api_bp)  # Search API
    app.register_blueprint(sso_api_bp)  # SSO API (SAML, OAuth2, OIDC)
    app.register_blueprint(trash_api_bp)  # Trash API v2
    app.register_blueprint(quota_api_v2_bp)  # Quota API v2
    app.register_blueprint(sharing_api_bp)  # Advanced Sharing API v2
    app.register_blueprint(thumbnail_api_bp)  # Thumbnail API v2
    app.register_blueprint(security_bp)  # Security stats
    app.register_blueprint(vaultspace_api_bp)  # VaultSpaces API

    # Custom static file handler - check dist/ first, then fallback to static/
    # This must be registered AFTER blueprints to have priority
    @app.route("/static/<path:filename>")
    def serve_static_fallback(filename):
        """Serve static files from dist/ first, then fallback to static/.

        Optimized to use try/except instead of exists() checks for better performance.
        This prevents HAProxy from returning 503 due to slow file system operations.
        """
        from flask import send_from_directory, abort
        from werkzeug.exceptions import NotFound
        import logging

        logger = logging.getLogger(__name__)

        # If filename starts with "assets/", it's from Vue.js build
        # Request: /static/assets/index-BNuRR0jV.js
        # Should serve: dist/assets/index-BNuRR0jV.js
        if filename.startswith("assets/"):
            dist_dir = vault_dir / "static" / "dist"
            if dist_dir.exists():
                try:
                    # Try to serve directly - faster than checking existence first
                    response = send_from_directory(str(dist_dir), filename)
                    # Add cache headers for static assets
                    response.cache_control.public = True
                    response.cache_control.max_age = 31536000  # 1 year
                    # Ensure we don't force HTTPS - remove any HSTS headers
                    response.headers.pop("Strict-Transport-Security", None)
                    return response
                except NotFound:
                    # File doesn't exist in dist/assets/, continue to next check
                    pass
                except Exception as e:
                    logger.log(f"Error serving asset {filename}: {e}")
                    abort(500)

        # Try dist/ first (for Vue.js build assets and index.html)
        try:
            response = send_from_directory(str(static_dir), filename)
            # Add cache headers for static assets
            response.cache_control.public = True
            response.cache_control.max_age = 31536000  # 1 year
            # Ensure we don't force HTTPS - remove any HSTS headers
            response.headers.pop("Strict-Transport-Security", None)
            return response
        except NotFound:
            # File doesn't exist in dist/, try static/ fallback
            pass
        except Exception as e:
            logger.log(f"Error serving file {filename} from dist: {e}")
            abort(500)

        # Fallback to original static/ (for legacy files like vault.css, vault.js, etc.)
        try:
            response = send_from_directory(str(original_static_dir), filename)
            # Add cache headers for static assets
            response.cache_control.public = True
            response.cache_control.max_age = 31536000  # 1 year
            # Remove HSTS headers to allow HTTP access
            response.headers.pop("Strict-Transport-Security", None)
            return response
        except NotFound:
            # File not found anywhere
            abort(404)
        except Exception as e:
            logger.log(f"Error serving file {filename} from static: {e}")
            abort(500)

    @app.after_request
    def save_session(response):
        """Ensure session is saved before sending response."""
        # Flask sessions are automatically saved, but explicitly mark as modified
        # to ensure it persists before redirects
        from flask import session

        if session.get("logged_in") and session.modified:
            # Session will be automatically saved by Flask
            pass
        return response

    @app.before_request
    def handle_cors_preflight():
        """Handle restrictive CORS preflight checks."""
        from flask import make_response, jsonify, request

        if request.method != "OPTIONS":
            return None

        origin = request.headers.get("Origin")
        if origin and _origin_is_allowed_for_request(origin):
            response = make_response("", 204)
            response.headers["Content-Length"] = "0"
            return response

        if origin:
            return jsonify({"error": "CORS origin not allowed"}), 403

        return None

    @app.before_request
    def generate_csp_nonce():
        """Generate CSP nonce for each request and make it available to templates."""
        # Import secrets here to avoid importing at module level if not needed
        import secrets
        from flask import g

        from flask import request

        if request.path.startswith("/api/") and "upload" in request.path:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"API upload request received: {request.method} {request.path}, "
                f"Content-Length: {request.headers.get('Content-Length', 'unknown')}"
            )

        # Generate a secure random nonce (base64url encoded, 16 bytes = 128 bits)
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_csp_nonce():
        """Make CSP nonce available to all templates."""
        from flask import g

        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def add_security_headers(response):
        """Add strict security headers including CSP."""
        # Import json here to avoid importing at module level if not needed
        import json
        from flask import current_app, g, request
        from common.constants import SESSION_MAX_AGE_SECONDS

        # Get CSP nonce for this request
        csp_nonce = getattr(g, "csp_nonce", "")

        # Content Security Policy - enhanced with trusted types and reporting
        # Note: 'wasm-unsafe-eval' is required for Argon2-browser WebAssembly module
        csp_directives = [
            "default-src 'self'",
            (
                f"script-src 'self' 'nonce-{csp_nonce}' 'wasm-unsafe-eval' https://static.cloudflareinsights.com"
                if csp_nonce
                else "script-src 'self' 'wasm-unsafe-eval' https://static.cloudflareinsights.com"
            ),
            "style-src 'self' https://fonts.googleapis.com",
            "img-src 'self' data: blob: https://github.com https://img.shields.io https://shields.io",
            "media-src 'self' blob:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://static.cloudflareinsights.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "trusted-types default vault-html notifications-html vault-script-url vue goog#html",
            "require-trusted-types-for 'script'",
            "report-uri /orchestrator/csp-violation-report-endpoint",
            "report-to vault-csp",
        ]
        # Only add upgrade-insecure-requests if we're actually using HTTPS
        # For HTTP (especially on IP addresses), this directive forces browsers to use HTTPS
        # which breaks the application when HTTPS is not available
        if request.is_secure:
            csp_directives.append("upgrade-insecure-requests")
        csp_policy = "; ".join(csp_directives)

        # Add or merge CSP policy
        if existing_csp := response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = (
                f"{existing_csp}; {csp_policy}"
            )
        else:
            response.headers["Content-Security-Policy"] = csp_policy

        # Add Report-To header pointing to orchestrator CSP endpoint
        # Use the same format as orchestrator for consistency
        # Construct orchestrator URL from current request
        orchestrator_url = None
        use_fallback = False
        try:
            from flask import request
            from urllib.parse import urlparse

            # Construct URL from request context
            constructed_url = f"{request.scheme}://{request.host}/orchestrator/csp-violation-report-endpoint"
            # Validate URL format
            parsed = urlparse(constructed_url)
            if parsed.scheme and parsed.netloc:
                orchestrator_url = constructed_url
            else:
                use_fallback = True
        except Exception:
            # Fallback: use relative URL if request context unavailable or URL invalid
            use_fallback = True

        if use_fallback or not orchestrator_url:
            orchestrator_url = "/orchestrator/csp-violation-report-endpoint"
            # Log warning if fallback is used (only in development to avoid log spam)
            is_production = current_app.config.get("IS_PRODUCTION", True)
            if not is_production:
                current_app.logger.debug(
                    "CSP Report-To: Using fallback relative URL (request context unavailable or invalid)"
                )

        report_to = {
            "group": "vault-csp",
            "max_age": SESSION_MAX_AGE_SECONDS,
            "endpoints": [{"url": orchestrator_url}],
        }

        response.headers["Report-To"] = json.dumps(report_to)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers["X-Frame-Options"] = "DENY"

        # Enforce additional security headers
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        # Cross-Origin-Opener-Policy and Cross-Origin-Resource-Policy require
        # a "trustworthy" origin (HTTPS or localhost). For IP addresses in HTTP,
        # these headers can force browsers to use HTTPS, causing mixed content issues.
        # Only add them if we're using HTTPS or localhost
        # IMPORTANT: For IP addresses in HTTP, we MUST NOT add these headers
        # as they cause browsers to force HTTPS, breaking the application
        is_localhost = (
            request.host.startswith("localhost")
            or request.host.startswith("127.0.0.1")
            or request.host.startswith("[::1]")
        )
        # Only add these headers if we're actually using HTTPS (not just configured for it)
        # For HTTP on IP addresses, these headers cause browsers to force HTTPS
        if request.is_secure or is_localhost:
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        else:
            # For HTTP on IP addresses, explicitly remove these headers to prevent HTTPS upgrade
            response.headers.pop("Cross-Origin-Opener-Policy", None)
            response.headers.pop("Cross-Origin-Resource-Policy", None)

        # Strict-Transport-Security (only when HTTPS is actually being used)
        # Don't add HSTS header if we're using HTTP (request.is_secure will be False)
        # This prevents browsers from forcing HTTPS when accessing via HTTP
        settings = current_app.config.get("VAULT_SETTINGS")
        enforce_https = bool(settings and settings.session_cookie_secure)
        # Only add HSTS if we're actually using HTTPS (not just configured to use it)
        if enforce_https and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )

        # Restrictive CORS headers
        origin_header = request.headers.get("Origin")
        allowed_cors_headers = current_app.config.get(
            "ALLOWED_CORS_HEADERS",
            "Authorization, Content-Type, X-Requested-With, Accept, X-CSRF-Token",
        )
        # Allow same-origin requests (no Origin header) or explicitly allowed origins
        if not origin_header or _origin_is_allowed_for_request(origin_header):
            if origin_header:
                # Cross-origin request from allowed origin
                response.headers["Access-Control-Allow-Origin"] = origin_header
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET,POST,PUT,PATCH,DELETE,OPTIONS"
                )
                response.headers["Access-Control-Allow-Headers"] = allowed_cors_headers
                response.headers["Access-Control-Expose-Headers"] = (
                    "Content-Disposition"
                )
                response.headers["Access-Control-Max-Age"] = "600"
                response.headers.add("Vary", "Origin")
            # For same-origin requests (no Origin header), no CORS headers needed
            # but we don't block them either
        elif request.method == "OPTIONS" and origin_header:
            # Preflight request from disallowed origin -> ensure browsers fail fast
            response.status_code = 403

        return response

    @app.route("/favicon.ico")
    def favicon():
        """Serve favicon."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static" / "icons"), "favicon.ico", mimetype="image/x-icon"
        )

    @app.route("/site.webmanifest")
    def webmanifest():
        """Serve web app manifest."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static" / "icons"),
            "site.webmanifest",
            mimetype="application/manifest+json",
        )

    @app.route("/apple-touch-icon.png")
    def apple_touch_icon():
        """Serve Apple touch icon."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static" / "icons"),
            "apple-touch-icon.png",
            mimetype="image/png",
        )

    @app.route("/favicon.svg")
    def favicon_svg():
        """Serve SVG favicon."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static" / "icons"), "favicon.svg", mimetype="image/svg+xml"
        )

    @app.route("/favicon-96x96.png")
    def favicon_96x96():
        """Serve 96x96 favicon."""
        from flask import send_from_directory

        return send_from_directory(
            str(vault_dir / "static" / "icons"),
            "favicon-96x96.png",
            mimetype="image/png",
        )

    @app.route("/robots.txt")
    def robots_txt():
        """Serve robots.txt to disallow all crawling.

        CRITICAL: This file is legally required by the license terms.
        It MUST refuse all indexing (Disallow: /) to prevent external
        organizations from discovering or reselling this software.
        Never remove or modify this route without legal review.
        """
        from flask import Response, send_from_directory
        from werkzeug.exceptions import NotFound
        import logging

        logger = logging.getLogger(__name__)

        # CRITICAL: Required content that MUST be served
        # License requirement: must refuse all indexing to prevent resale
        required_content = "User-agent: *\nDisallow: /\n"

        # Try to serve the physical file first, but validate its content
        robots_file = vault_dir / "static" / "icons" / "robots.txt"
        if robots_file.exists():
            try:
                # Validate file content to ensure it contains "Disallow: /"
                file_content = robots_file.read_text(encoding="utf-8")
                if "Disallow: /" in file_content:
                    # File is valid, serve it
                    return send_from_directory(
                        str(vault_dir / "static" / "icons"),
                        "robots.txt",
                        mimetype="text/plain",
                    )
                else:
                    # File exists but is invalid - log warning and use safe content
                    logger.log(
                        "CRITICAL: robots.txt file exists but does not contain 'Disallow: /'. "
                        "Serving correct content to comply with license requirements. "
                        f"File location: {robots_file}"
                    )
                    return Response(required_content, mimetype="text/plain")
            except (NotFound, Exception) as e:
                logger.debug(
                    f"Error reading robots.txt file: {e}. Using fallback content."
                )

        # CRITICAL FALLBACK: If file is missing or invalid, generate the required content
        # This ensures robots.txt is ALWAYS served with Disallow: /
        # License requirement: must refuse all indexing
        logger.debug(
            "robots.txt file not found or invalid, serving generated content. "
            "Please ensure src/vault/static/icons/robots.txt exists with 'Disallow: /'."
        )
        return Response(required_content, mimetype="text/plain")

    @app.route("/healthz")
    def healthz():
        """Health check endpoint - must respond quickly for HAProxy.

        Always returns 200 to avoid HAProxy custom error pages.
        Does not perform blocking operations to ensure fast response.
        """
        from flask import Response

        # Always return 200 immediately - no blocking operations
        # If workers are blocked, this endpoint will still respond quickly
        # HAProxy will detect worker issues through request timeouts, not status codes
        return Response('{"status":"ok"}', mimetype="application/json", status=200)

    @app.route("/healthz/stream")
    def healthz_stream():
        """Server-Sent Events stream for real-time health status monitoring."""
        import json
        import time
        from flask import Response, stream_with_context

        def get_restore_status():
            """Get current restore status from app config."""
            restore_running = current_app.config.get("DATABASE_RESTORE_RUNNING", False)
            restore_error = current_app.config.get("DATABASE_RESTORE_ERROR", None)
            maintenance_mode = current_app.config.get("MAINTENANCE_MODE", False)
            return {
                "running": restore_running,
                "error": restore_error,
                "maintenance_mode": maintenance_mode,
            }

        @stream_with_context
        def generate_health_events():
            """Generate SSE health status events."""
            try:
                # Get initial restore status
                last_restore_status = get_restore_status()

                # Send initial status event with restore status
                initial_data = {
                    "status": "ok",
                    "restore_status": last_restore_status,
                }
                yield f"data: {json.dumps(initial_data)}\n\n"

                # Send heartbeats every 25 seconds to keep connection alive
                heartbeat_interval = 25.0
                last_heartbeat = time.time()
                # Check for restore status changes more frequently (every 1 second)
                status_check_interval = 1.0
                last_status_check = time.time()

                while True:
                    current_time = time.time()
                    elapsed = current_time - last_heartbeat
                    status_elapsed = current_time - last_status_check

                    # Check for restore status changes
                    if status_elapsed >= status_check_interval:
                        current_restore_status = get_restore_status()
                        # Send event if restore status changed
                        if current_restore_status != last_restore_status:
                            status_data = {
                                "status": "ok",
                                "restore_status": current_restore_status,
                            }
                            yield f"data: {json.dumps(status_data)}\n\n"
                            last_restore_status = current_restore_status
                        last_status_check = current_time

                    if elapsed >= heartbeat_interval:
                        # Send heartbeat with current restore status
                        current_restore_status = get_restore_status()
                        heartbeat_data = {
                            "status": "ok",
                            "restore_status": current_restore_status,
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_restore_status = current_restore_status
                        last_heartbeat = current_time
                    else:
                        # Sleep for remaining time until next check (min of heartbeat or status check)
                        sleep_time = min(
                            heartbeat_interval - elapsed,
                            status_check_interval - status_elapsed,
                            1.0,
                        )
                        if sleep_time > 0:
                            time.sleep(sleep_time)

            except (GeneratorExit, StopIteration):
                # Client disconnected
                pass
            except Exception as e:
                # Log error but don't send error event (connection will close naturally)
                logger = current_app.logger
                logger.debug(f"Health check SSE stream error: {e}")

        response = Response(
            generate_health_events(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
        return response

    # All frontend routes (/share) are handled by Vue.js SPA
    # Share route is now handled by Vue Router at /share/:token

    @app.route("/")
    def serve_vue_app_root():
        """Serve Vue.js SPA root - return index.html."""
        from flask import make_response, redirect, request, send_file
        import re

        # Check setup status within app context
        # is_setup_complete() already uses app.app_context() internally,
        # but we ensure we're in the request context here
        try:
            setup_complete = is_setup_complete(app)
            if not setup_complete:
                return redirect("/setup", code=302)
        except Exception as setup_error:
            # If setup check fails, log error but allow access to setup page
            logger = app.config.get("LOGGER", None)
            if logger:
                logger.log(
                    f"[WARNING] Failed to check setup status in root route: {setup_error}"
                )
            # On error, redirect to setup to be safe
            return redirect("/setup", code=302)

        dist_index = static_dir / "index.html"
        if dist_index.exists():
            # Read the HTML file
            with open(dist_index, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Only force HTTP rewrites for direct IP access (browsers may auto-upgrade)
            should_force_http = not _is_secure_request(request) and _is_ip_host(
                request.headers.get("Host") or request.host
            )
            if should_force_http:
                # Replace any absolute HTTPS URLs with HTTP URLs
                html_content = re.sub(
                    r'https://([^"\'<>]+)(/static/[^"\'<>]+)',
                    rf"http://\1\2",
                    html_content,
                    flags=re.IGNORECASE,
                )
                # Replace any absolute HTTP URLs with relative URLs (more reliable)
                current_origin = f"{request.scheme}://{request.host}"
                html_content = re.sub(
                    rf'{re.escape(current_origin)}(/static/[^"\'<>]+)',
                    r"\1",
                    html_content,
                    flags=re.IGNORECASE,
                )
                # Inject <base> tag with HTTP protocol to force all relative URLs to use HTTP
                # This is critical for IP addresses - browsers force HTTPS otherwise
                if "<base" not in html_content.lower():
                    scheme = "https" if _is_secure_request(request) else request.scheme
                    base_url = f"{scheme}://{request.host}"
                    # Insert <base> tag right after <head> to force HTTP protocol
                    html_content = re.sub(
                        r"(<head[^>]*>)",
                        rf'\1\n    <base href="{base_url}/">',
                        html_content,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                # Remove any meta tags that force HTTPS upgrade
                html_content = re.sub(
                    r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*upgrade-insecure-requests[^>]*>',
                    "",
                    html_content,
                    flags=re.IGNORECASE,
                )

            response = make_response(html_content)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            # Ensure we don't force HTTPS - remove any HSTS headers
            response.headers.pop("Strict-Transport-Security", None)
            return response

        # Frontend must be built - return error
        return (
            "<html><body><h1>Leyzen Vault</h1><p>Frontend not built. Run 'npm run build' in src/vault/static/</p></body></html>",
            404,
        )

    def _is_spa_route(path: str) -> bool:
        """Check if a path matches a valid Vue Router route pattern.

        Returns True if the path should be handled by Vue Router (SPA),
        False if it's a real 404 that should be handled by HAProxy.
        """
        import re

        # Exact routes in Vue Router
        exact_routes = {
            "/",
            "/setup",
            "/login",
            "/register",
            "/verify-email",
            "/accept-invitation",
            "/dashboard",
            "/trash",
            "/starred",
            "/recent",
            "/shared",
            "/account",
            "/admin",
        }

        if path in exact_routes:
            return True

        # Routes with dynamic parameters
        # /sso/callback/:providerId - matches /sso/callback/ followed by any non-slash chars
        if re.match(r"^/sso/callback/[^/]+", path):
            return True

        # /share/:token - matches /share/ followed by any non-slash chars
        if re.match(r"^/share/[^/]+", path):
            return True

        # /vaultspace/:id - matches /vaultspace/ followed by any non-slash chars
        if re.match(r"^/vaultspace/[^/]+", path):
            return True

        return False

    @app.errorhandler(404)
    def serve_vue_app_for_404(e):
        """Serve Vue.js SPA for 404 errors (Vue Router will handle client-side routing)."""
        from flask import request, send_file, jsonify, make_response, current_app

        # Return JSON for API endpoints
        if request.path.startswith("/api/"):
            current_app.logger.error(
                f"404 for API endpoint: {request.path} {request.method}",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "full_url": request.url,
                    "headers": dict(request.headers),
                },
            )
            # Check if route exists in url_map
            matching_rules = [
                rule
                for rule in current_app.url_map.iter_rules()
                if rule.rule == request.path
                or request.path.startswith(
                    rule.rule.replace("<file_id>", "").replace("<link_token>", "")
                )
            ]
            if matching_rules:
                current_app.logger.debug(
                    f"Matching rules found: {[r.rule for r in matching_rules]}"
                )
            else:
                current_app.logger.debug(f"No matching rules found for {request.path}")
            return jsonify({"error": "Not found", "path": request.path}), 404

        # Don't intercept static files
        if request.path.startswith("/static/"):
            return e

        # Check if this is a valid SPA route (should be handled by Vue Router)
        dist_index = static_dir / "index.html"
        if dist_index.exists():
            # Use the same logic as serve_vue_app_root to inject <base> tag for HTTP
            from flask import make_response
            import re

            with open(dist_index, "r", encoding="utf-8") as f:
                html_content = f.read()

            should_force_http = not _is_secure_request(request) and _is_ip_host(
                request.headers.get("Host") or request.host
            )
            if should_force_http:
                # Replace any absolute HTTPS URLs with HTTP URLs or relative URLs
                html_content = re.sub(
                    r'https://([^"\'<>]+)(/static/[^"\'<>]+)',
                    rf"http://\1\2",
                    html_content,
                    flags=re.IGNORECASE,
                )
                # Also replace any absolute HTTP URLs that might be converted to HTTPS
                # by making them relative if they point to the same origin
                current_origin = f"{request.scheme}://{request.host}"
                html_content = re.sub(
                    rf'{re.escape(current_origin)}(/static/[^"\'<>]+)',
                    r"\1",
                    html_content,
                    flags=re.IGNORECASE,
                )
                # Inject <base> tag with HTTP protocol to force all relative URLs to use HTTP
                if "<base" not in html_content.lower():
                    scheme = "https" if _is_secure_request(request) else request.scheme
                    base_url = f"{scheme}://{request.host}"
                    html_content = re.sub(
                        r"(<head[^>]*>)",
                        rf'\1\n    <base href="{base_url}/">',
                        html_content,
                        count=1,
                        flags=re.IGNORECASE,
                    )

            response = make_response(html_content)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers.pop("Strict-Transport-Security", None)

            if _is_spa_route(request.path):
                # Valid SPA route - serve index.html with 200 so Vue Router can handle it
                return response
            else:
                # Invalid route - serve index.html with 404 so HAProxy can intercept
                # This allows HAProxy to intercept and serve its custom 404 page
                response.status_code = 404
                return response

        # Return original 404
        return e

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler - return JSON for API routes, HTML for others."""
        # Import traceback here to avoid importing at module level if not needed
        import traceback
        from flask import request, jsonify, current_app
        from werkzeug.exceptions import HTTPException

        # Handle Werkzeug HTTPException
        if isinstance(e, HTTPException):
            if request.path.startswith("/api/"):
                return jsonify({"error": e.description or str(e)}), e.code
            return e

        # Check for database-related errors that indicate race conditions
        error_str = str(e).lower()
        error_type = type(e).__name__.lower()

        is_db_error = False
        is_retryable = False

        # Check for PostgreSQL deadlock errors
        if "deadlock" in error_str or "deadlock_detected" in error_str:
            is_db_error = True
            is_retryable = True
            current_app.logger.warning(
                f"[DB DEADLOCK] Deadlock detected in {request.path}: {e}. "
                "Consider using db_transaction() with retry for this operation."
            )

        # Check for concurrent update errors
        if (
            "tuple concurrently updated" in error_str
            or "could not serialize access" in error_str
            or "serialization failure" in error_str
        ):
            is_db_error = True
            is_retryable = True
            current_app.logger.warning(
                f"[DB CONCURRENCY] Concurrent update error in {request.path}: {e}. "
                "Consider using db_transaction() with retry for this operation."
            )

        # Check for transaction aborted errors
        if (
            "infailedsqltransaction" in error_type
            or "transaction is aborted" in error_str
        ):
            is_db_error = True
            is_retryable = True
            current_app.logger.warning(
                f"[DB TRANSACTION] Transaction aborted in {request.path}: {e}. "
                "This may indicate a race condition between workers."
            )

        # Determine if we're in production mode
        is_production = current_app.config.get("IS_PRODUCTION", True)

        # Log the error with full details (always log details server-side)
        if is_db_error and is_retryable:
            # For retryable DB errors, log as warning (they should be handled by db_transaction)
            error_details = f"Database error (retryable): {e}\n{traceback.format_exc()}"
            current_app.logger.warning(error_details)
        else:
            error_details = f"Unhandled exception: {e}\n{traceback.format_exc()}"
            current_app.logger.error(error_details)

        # If this is an API route, return JSON error
        if request.path.startswith("/api/"):
            # In production, return generic error message to avoid information disclosure
            if is_production:
                error_message = "An internal error occurred"
            else:
                error_message = str(e) if str(e) else "An internal error occurred"

            status_code = getattr(e, "code", 500)
            if not isinstance(status_code, int) or status_code < 400:
                status_code = 500
            return jsonify({"error": error_message}), status_code

        # For non-API routes, let Flask handle it (will show HTML error page)
        # But we still want to log it
        return e

    # CRITICAL LICENSE VALIDATION: Verify robots.txt is present and correct
    # This file is legally required to prevent external indexing/resale
    robots_file = vault_dir / "static" / "icons" / "robots.txt"
    try:
        # Get logger from app config if available
        validation_logger = app.config.get("LOGGER")
        if validation_logger is None:
            # Fallback to standard logging if FileLogger not yet initialized
            import logging

            validation_logger = logging.getLogger(__name__)

            # Create a wrapper to match FileLogger interface
            class LoggerWrapper:
                def log(self, msg: str) -> None:
                    logging.getLogger(__name__).info(msg)

            validation_logger = LoggerWrapper()

        if robots_file.exists():
            file_content = robots_file.read_text(encoding="utf-8")
            if "Disallow: /" not in file_content:
                validation_logger.log(
                    "[ERROR] CRITICAL LICENSE VIOLATION: robots.txt exists but does not contain 'Disallow: /'. "
                    "This violates license terms prohibiting external indexing. "
                    f"File location: {robots_file}. "
                    "The route will serve correct content, but please fix the file."
                )
            else:
                if db_initialized_by_this_worker:
                    validation_logger.log(
                        "[INIT] robots.txt validated: properly configured to disallow all indexing"
                    )
        else:
            validation_logger.log(
                "[WARNING] robots.txt file not found at expected location. "
                "Route will serve generated content, but please create the file: "
                f"{robots_file}"
            )
    except Exception as e:
        # Fallback logger in case of error
        import logging

        logging.getLogger(__name__).error(
            f"Error validating robots.txt during startup: {e}. "
            "Route will serve correct content as fallback."
        )

    return app


# For Gunicorn
application = create_app()


__all__ = ["create_app", "application"]
