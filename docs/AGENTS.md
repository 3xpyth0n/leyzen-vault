# Leyzen Vault — Agent Guidelines

Welcome! This repository powers the Leyzen Vault proof-of-concept stack. Use this
reference to understand the layout, preferred coding styles, and the sanity
checks we expect before shipping changes.

## Repository map

**Organization logic**: `src/` contains complex Python applications with substantial codebases, while `infra/` contains minimal services, configuration files, and Dockerfiles for infrastructure components.

**Path conventions**: All paths in this document are relative to the repository root unless explicitly stated otherwise. For example:

- `src/orchestrator/` refers to the `orchestrator/` directory inside the `src/` directory at the repository root
- `infra/docker-proxy/` refers to the `docker-proxy/` directory inside the `infra/` directory at the repository root
- When referencing files in code examples or documentation, paths starting with `src/` or `infra/` are relative to the repository root
- When referencing files within Python code (e.g., imports), paths are relative to the Python module structure (e.g., `from common.env import ...` refers to `src/common/env.py`)

- `src/orchestrator/` — Flask application that exposes the admin dashboard and  
  coordinates container rotation. Houses most Python code, HTML templates, JS,  
  and CSS.
- `infra/docker-proxy/` — Minimal Flask service that brokers authenticated, allowlisted
  requests to the Docker Engine socket.
- `infra/haproxy/` — Static HAProxy configuration and error pages that front every
  HTTP service.
- `src/vault/` — Leyzen Vault secure file storage application with end-to-end encryption.
  Vue.js SPA frontend with Flask REST API backend. Uses PostgreSQL for metadata storage.
- `src/common/` — Shared Python modules (`env.py`, `exceptions.py`) used across
  services. Mounted at `/common` in containers.
- `src/compose/` — Python build scripts that generate `docker-generated.yml` and HAProxy
  configuration from environment variables.
- `tools/cli/` — Go source code for the `leyzenctl` CLI tool. The CLI provides an
  interactive TUI (Terminal User Interface) built with Bubbletea and Lipgloss,
  plus headless mode for automation.
- `infra/monitoring/` — Monitoring infrastructure components (currently empty, reserved for future use).
- `infra/queue/` — Queue infrastructure components (currently empty, reserved for future use).
- `leyzenctl` — Deployment helper (Go CLI binary compiled by `install.sh`).

## Python guidelines

### Orchestrator & Docker Proxy (`src/orchestrator/`, `infra/docker-proxy/`)

- **Typing & style**: Keep `from __future__ import annotations` at the top of new
  modules. Add precise type hints, docstrings, and descriptive variable names.
  Follow the existing preference for helper functions and small, focused
  methods. Use dataclasses or typed dictionaries instead of loosely typed
  structures when practical.
- **Imports**: Group standard library, third-party, and local imports separately
  (see existing modules for ordering). Avoid introducing new dependencies unless
  they are already declared in `requirements.in` / `requirements.txt`.
- **Dev dependencies**: Development dependencies (`requirements-dev.in`) are maintained
  separately for `src/orchestrator/` and `infra/docker-proxy/`. Each service maintains
  its own development dependencies independently. If files are moved, ensure relative
  paths in these files are updated accordingly.
- **Configuration access**: Read request-scoped objects through Flask’s
  `current_app.config` helpers (see `blueprints/auth.py`). Avoid storing global
  mutable state outside the orchestrator service classes.
- **Timezone awareness**: Use the timezone stored in `Settings.timezone` for all
  timestamps; `datetime.now(settings.timezone)` is the established pattern.
- **Logging**: Route operational logs through `FileLogger` and keep secrets out
  of log messages. Prefer `.log()` for structured entries; use `.warning()` only
  for noteworthy anomalies.
- **HTTP clients**: Reuse the shared `httpx.Client` in the Docker proxy;
  instantiate new clients only when caching or lifetimes demand it.
- **Error handling**: Raise custom exceptions that inherit from the local error
  base classes (e.g., `DockerProxyError`) and surface human-readable messages to
  the dashboard. Guard asynchronous worker loops with targeted `try/except`
  blocks—see `_orchestrator_loop()` for reference.
- **Unit boundaries**: Keep background threads, SSE streaming, and rotation
  mechanics inside `RotationService`. Blueprints should remain thin adapters
  between Flask routes and service methods.
- **Environment file parsing**: The codebase maintains separate `.env` parsers in
  Python (`src/common/env.py`) and Go (`tools/cli/internal/env.go`) for linguistic
  reasons. Both implementations must stay synchronized to avoid configuration
  inconsistencies. When modifying parsing logic, update both implementations.
  See `src/common/env.py` for detailed notes on the duplication.
- **Shared module naming**: The `src/common/` directory contains shared Python modules
  (`env.py`, `exceptions.py`) used across services. In Docker containers, this
  directory is mounted as `/common` to match the import convention
  `from common.*`. Use `from common.*` imports consistently across all Python code.
- **Python path bootstrap**: When importing `common.*` modules from
  entry points outside the `src/` directory, you must first bootstrap the Python path.
  The standard pattern is:
  1. Add `src/` to `sys.path` manually (this enables importing `common.path_setup`)
  2. Import `bootstrap_entry_point` from `common.path_setup`
  3. Call `bootstrap_entry_point()` to configure all paths (idempotent)
  4. Then import other `common.*` modules

  **Note**: The repository uses `bootstrap_entry_point()` from `src/common/path_setup.py`
  as the standard bootstrap pattern. This function encapsulates the complete bootstrap
  sequence needed for entry points outside the `src/` directory.

  This pattern is used in `src/orchestrator/app.py`, `infra/docker-proxy/proxy.py`, and
  `src/compose/build.py`. See these files for reference implementations. The bootstrap is
  necessary because these entry points are not executed from the `src/` directory, so
  Python's default import resolution cannot find the `common` modules.

  For internal modules within `src/`, you can use `bootstrap_src_path()` or `setup_python_paths()`
  directly if you need to configure paths before importing other modules.

### Common Services (`src/common/services/`)

The `src/common/services/` directory contains shared services used across multiple components:

- **`file_promotion_service.py`** — `FilePromotionService` — Unified service for promoting validated files from tmpfs (`/data`) to persistent storage (`/data-source`) with strict validation. This service validates files using `SyncValidationService` (checks file ID exists in database AND hash matches) before promoting them. It also handles cleanup of orphaned files (files that don't exist in database). Used by both the vault (after each upload) and the orchestrator (during rotation).

- **`sync_validation_service.py`** — `SyncValidationService` — Service for validating files before synchronization to prevent malware persistence. Validates that files exist in the database and that their hash matches before allowing promotion to persistent storage. Maintains a whitelist of legitimate files and thumbnails loaded from the database.

- **`logging.py`** — `FileLogger` — Shared logging service used across services. Provides structured logging with file rotation and timezone awareness. Routes operational logs through `FileLogger` and keeps secrets out of log messages. Prefer `.log()` for structured entries; use `.warning()` only for noteworthy anomalies.

### Vault Application (`src/vault/`)

The Vault application follows similar Python guidelines with additional considerations:

- **Database**: Uses PostgreSQL via SQLAlchemy. Database initialization happens in `create_app()`.
  The application requires PostgreSQL in production mode but allows fallback in development.
- **Background workers**: Background threads handle periodic tasks (e.g., audit log cleanup, orphaned file cleanup, periodic file promotion).
  Workers are started as daemon threads in `create_app()` and use `FilePromotionService` and `SyncValidationService` from `src/common/services/`.
- **Service initialization**: Services are initialized with timezone awareness and registered in
  `app.config`. Services like `AuditService`, `ShareService`, and `RateLimiter` use the timezone
  from `VaultSettings.timezone`.
- **IP Enrichment**: `IPEnrichmentService` is initialized at startup and used by `AuditService` to enrich IP addresses with geolocation and threat intelligence data from free public APIs.
- **File Promotion and Validation**: `FilePromotionService` and `SyncValidationService` from `src/common/services/` are used in background workers to validate and promote files from tmpfs to persistent storage. These services ensure files are validated against the database before promotion to prevent malware persistence.
- **Error handling**: Global exception handlers return JSON for API routes and HTML for SPA routes.
  Production mode hides error details from clients for security.
- **Configuration fallback**: The application supports fallback configuration for development/testing,
  but production mode requires valid configuration and will fail fast if misconfigured.
- **Internal API token**: The `INTERNAL_API_TOKEN` is derived deterministically from `SECRET_KEY` using `common.token_utils.derive_internal_api_token()` if not explicitly set in environment variables. This token is used for orchestrator-to-vault communication and ensures both services use the same token without requiring database access or manual configuration.

## Flask blueprints & templates

### Orchestrator Blueprints (`src/orchestrator/blueprints`, `src/orchestrator/templates`)

- Blueprints should only call into services or helpers defined under
  `src/orchestrator/services` and `src/orchestrator/blueprints/utils.py`. Do not access
  Docker or filesystem resources directly from the views.
- Prefer returning dictionaries and letting Flask/Jinja render templates; keep
  inline HTML minimal.
- Templates are hand-authored HTML. Respect the existing semantic layout and
  accessibility cues (ARIA attributes, alt text, button labels). Keep inline
  scripts out of templates; place JS in `static/js` modules.
- When exposing new context variables, update the template, JS bootstrap data,
  and `dashboard` blueprint together.

**Current blueprints:**

- `auth_bp` — Authentication and CAPTCHA routes
- `dashboard_bp` — Dashboard and API routes for container management

### Vault Blueprints (`src/vault/blueprints`)

The Vault application uses a Vue.js SPA frontend with Flask REST API backend. Blueprints are organized into API endpoints and legacy routes.

**API Blueprints (JWT-based authentication):**

- `admin_api_bp` — Admin API endpoints
- `auth_api_bp` — JWT-based authentication API
- `config_api_bp` — Configuration API for exposing public vault settings to frontend (endpoint `/api/v2/config`)
- `files_api_bp` — Advanced files API v2 (upload, download, metadata)
- `file_events_api_bp` — File events API for real-time file synchronization via SSE (Server-Sent Events), endpoint `/api/v2/files/events`
- `internal_api_bp` — Internal API for orchestrator operations
- `search_api_bp` — Search API endpoints
- `sso_api_bp` — SSO API (SAML, OAuth2, OIDC)
- `trash_api_bp` — Trash API v2
- `quota_api_v2_bp` — Quota API v2
- `sharing_api_bp` — Advanced Sharing API v2
- `thumbnail_api_bp` — Thumbnail API v2
- `vaultspace_api_bp` — VaultSpaces API

**Legacy Blueprints:**

- `auth_bp` — Legacy session-based authentication (for CAPTCHA/logout until fully migrated)
- `security_bp` — Security statistics endpoints

**Additional blueprints** (may be used internally or for specific features):

- `account.py`, `folders.py`, `preview.py`, `quotas.py`, `vaultspaces.py`

**Architecture notes:**

- The Vault application serves a Vue.js SPA from `/` and handles client-side routing
- API endpoints are prefixed with `/api/`
- Static files are served from `/static/` with fallback logic (dist/ → static/)
- CSP nonces are generated per-request for inline scripts
- CORS is restrictively configured with origin validation

### Vault Middleware (`src/vault/middleware/`)

The Vault application uses middleware components for authentication, authorization, and input validation:

- **`jwt_auth.py`** — JWT authentication middleware providing:
  - `@jwt_required` decorator for protecting routes with JWT authentication
  - `get_current_user()` function to retrieve the authenticated user from the JWT token
  - Origin/Referer validation for additional security
  - JWT token validation and replay protection via `jti` (JWT ID) tracking

- **`rbac.py`** — Role-Based Access Control (RBAC) middleware providing:
  - `@require_role(role_name)` decorator for role-based authorization
  - `@require_permission(permission_name)` decorator for permission-based authorization
  - Integration with user roles and permissions stored in the database

- **`input_validation.py`** — Input validation middleware providing validation decorators and helpers:
  - `validate_uuid_param()` — Validates UUID parameters
  - `validate_file_id_param()` — Validates file ID parameters
  - `validate_vaultspace_id_param()` — Validates VaultSpace ID parameters
  - `validate_pagination()` — Validates pagination parameters (page, per_page)
  - `validate_email_param()` — Validates email parameters
  - `validate_json_request()` — Validates JSON request body structure

All middleware components are imported from `vault.middleware` and used as decorators on blueprint routes.

## Front-end assets

### Orchestrator Front-end (`src/orchestrator/static`, `src/orchestrator/styles`)

- **JavaScript**: Modules live under `src/orchestrator/static/js/` and use modern ES modules.
  Stick with `const`/`let`, async/await, and `fetch`. Shared utilities belong in
  `static/js/core/` or `static/js/charts/`. Avoid mutating the vendor bundles in
  `static/js/vendor/`; replace them only by downloading a new upstream build.
- **Styling**: Tailwind utilities are compiled from `src/orchestrator/styles/tailwind.css` via
  `npm run build:css`. Update source styles there rather than editing the
  generated `static/tailwind.css`. Custom component styles live in
  `static/index.css`, `static/dashboard.css`, etc.—keep selectors BEM-like and
  responsive.
- **Assets**: In templates, reference files using the Flask static URL path `/orchestrator/static/...`
  (this is the HTTP URL path, not the filesystem path). The Flask app is configured with
  `static_url_path="/orchestrator/static"` in `src/orchestrator/__init__.py`, which maps to the
  filesystem directory `src/orchestrator/static/` in the repository. Always ensure cache-busting
  via `asset_version` when adding new bundles.

  **Note**: There is an important distinction between filesystem paths and URL paths:
  - Filesystem path: `src/orchestrator/static/dashboard.css` (used in Python code)
  - URL path: `/orchestrator/static/dashboard.css` (used in HTML templates)

  The Flask `static_url_path` configuration maps the URL path prefix to the filesystem directory
  automatically, so you should never mix these two in templates or code.

### Vault Front-end (`src/vault/static`)

The Vault application uses a Vue.js Single Page Application (SPA) architecture:

- **Build output**: Compiled Vue.js application is located in `src/vault/static/dist/`
- **Static file serving**: Flask serves static files with fallback logic:
  1. First checks `static/dist/` (production build)
  2. Falls back to `static/` (development/legacy files)
- **SPA routing**: All routes are handled by Vue Router on the client side. Flask serves `index.html`
  for all non-API routes, and Vue Router handles client-side navigation.
- **API communication**: The frontend communicates with Flask REST API endpoints prefixed with `/api/`
- **CSP nonces**: Content Security Policy nonces are generated per-request and injected into templates
  for inline scripts. The nonce is available in templates via `g.csp_nonce`.
- **CORS**: Restrictive CORS policy with origin validation. Only allowed origins (configured via
  `VAULT_ALLOWED_ORIGINS`) can make API requests.
- **Cache headers**: Static assets include long-term cache headers (1 year) for optimal performance.

**Architecture notes:**

- The application serves `index.html` for the root route (`/`) and all SPA routes
- API endpoints return JSON; non-API 404s serve `index.html` for Vue Router handling
- Static files (CSS, JS, images) are served with cache headers
- Background workers handle audit log cleanup automatically

## Service Startup Order

Services must start in a specific order to ensure dependencies are available:

1. **Base Infrastructure**: Docker networks and volumes are created first (handled by Docker Compose)
2. **Control Plane Services**:
   - `docker-proxy` starts first (required by orchestrator for container lifecycle operations)
   - `orchestrator` starts second and connects to docker-proxy
3. **Vault Services**: Orchestrator manages Vault container startup after establishing control plane connectivity
4. **Front-end Layer**: `haproxy` starts last and connects to active containers via backend configuration

The orchestrator reads container names from the environment (injected by docker-compose via `build.py`). Container names are auto-generated from `WEB_REPLICAS` if not explicitly provided. The orchestrator starts Vault containers up to the configured replica count, waiting for health checks to pass before marking them as ready.

**Background Workers**: After startup, the Vault application starts several background worker threads (daemon threads) for periodic tasks:

- **Audit log cleanup worker**: Runs every hour to clean up old audit log entries based on retention policy
- **Orphaned files cleanup worker**: Runs every hour to clean up orphaned files from persistent storage (files that don't exist in the database)
- **Periodic file promotion worker**: Runs every 5 minutes to promote files from tmpfs to persistent storage, ensuring files are persisted even if immediate promotion during upload fails

These workers use `FilePromotionService` and `SyncValidationService` from `src/common/services/` to validate and promote files safely. Workers are started automatically in `create_app()` and run as daemon threads.

See [`docs/ARCHITECTURE.md`](ARCHITECTURE.md#service-startup-order) for detailed sequence diagrams and startup flow documentation.

## Services Architecture

### Orchestrator Services (`src/orchestrator/services`)

The orchestrator uses a service-oriented architecture where business logic is encapsulated in service classes:

- `docker_proxy.py` — `DockerProxyService` — Manages communication with the Docker proxy service
- `rotation.py` — `RotationService` — Handles container rotation, health checks, and lifecycle management
- `storage_cleanup.py` — `StorageCleanupService` — Manages cleanup of orphaned storage
- `file_promotion_service.py` — Handles file promotion from temporary to persistent storage
- `rotation_telemetry.py` — Collects and reports rotation metrics
- `security_metrics_service.py` — Collects security-related metrics
- `sync_service.py` — Handles synchronization operations

Services are registered in `app.config` and accessed via `current_app.config` in blueprints.

### Vault Services (`src/vault/services`)

The Vault application has an extensive service layer covering various functionality:

**Core Services:**

- `audit.py` — `AuditService` — Audit logging and retention with IP enrichment
- `file_service.py` — `FileService` — File operations and metadata
- `file_event_service.py` — `FileEventService` — File events service for real-time file synchronization, manages event streams and SSE connections
- `encryption_service.py` — End-to-end encryption operations
- `key_management.py` — Key management and rotation
- `ip_enrichment.py` — `IPEnrichmentService` — IP enrichment service using free public APIs to enrich IP addresses with geolocation and threat intelligence data

**Storage Layer:**

- `storage.py` (in `src/vault/`) — `FileStorage` — Storage abstraction layer for file operations

**Authentication & Authorization:**

- `auth_service.py` — Authentication logic
- `sso_service.py` — SSO integration (SAML, OAuth2, OIDC)
- `totp_service.py` — TOTP-based 2FA
- `api_key_service.py` — API key management
- `device_service.py` — Device management
- `db_password_service.py` — Database password management for the `leyzen_app` role, handles encrypted password storage in SystemSecrets table

**Sharing & Collaboration:**

- `share_link_service.py` — `ShareService` — Share link generation and management
- `advanced_sharing_service.py` — Advanced sharing features
- `invitation_service.py` — User invitations

**Search & Indexing:**

- `search_service.py` — Search functionality
- `search_index_service.py` — Search index management
- `searchable_encryption.py` — Encrypted search operations

**Quota & Storage:**

- `quota_service.py` — Quota management
- `cache_service.py` — Caching layer
- `cache_promotion_service.py` — Cache promotion logic
- `storage_reconciliation_service.py` — Storage reconciliation

**Security & Compliance:**

- `zero_trust_service.py` — Zero-trust security model
- `behavioral_analysis_service.py` — Behavioral analysis
- `rate_limiter.py` — `RateLimiter` — Rate limiting
- `security_bp` — Security statistics

**Additional Services:**

- `admin_service.py`, `backup_service.py`, `domain_service.py`, `email_service.py`,
  `email_verification_service.py`, `log_filter.py`, `memory_cleanup_service.py`,
  `mtd_compatibility.py`, `preview.py`, `template_service.py`,
  `thumbnail_service.py`, `vaultspace_service.py`, `webhook_service.py`, `workflow_service.py`,
  `zip_service.py`

**Note**: `sync_validation_service.py` has been moved to `src/common/services/` as a shared service used by both vault and orchestrator.

Services are registered in `app.config` (e.g., `VAULT_STORAGE`, `VAULT_AUDIT`, `VAULT_SHARE`, `VAULT_RATE_LIMITER`)
and accessed via `current_app.config` in blueprints.

### Vault Utilities (`src/vault/utils/`)

The Vault application includes utility modules for common operations:

- **`constant_time.py`** — Constant-time comparison functions for security-critical operations (prevents timing attacks)
- **`file_validation.py`** — File validation utilities for validating file types, sizes, and content
- **`log_sanitizer.py`** — Log sanitization utilities to prevent information leakage in logs (removes sensitive data)
- **`mime_type_detection.py`** — MIME type detection utilities for identifying file types
- **`password_validator.py`** — Password validation utilities with strength checking
- **`safe_json.py`** — Safe JSON parsing utilities with error handling and validation
- **`valid_icons.py`** — Icon validation utilities for validating icon names and formats
- **`validate_db_schema.py`** — Database schema validation utilities for verifying database structure

These utilities are used throughout the Vault application for common operations and should be imported from `vault.utils`.

### Supporting Services

- `infra/docker-proxy/proxy.py` enforces bearer-token authentication and a strict
  endpoint allowlist. Maintain the pattern of compiling regular expressions at
  import time and validating headers in dedicated helpers.
- HAProxy templates should preserve the security headers already in place.
  Update both the config and error-page snippets if you tweak status handling.
- `infra/vault/entrypoint.sh` handles Vault container initialization; keep it POSIX sh compatible.

## Dockerfile Patterns

The repository uses different Dockerfile patterns depending on the service requirements.

### Multi-Stage Builds (Orchestrator)

The orchestrator service uses a multi-stage Dockerfile because it requires build-time dependencies (Node.js, npm) to compile front-end assets (Tailwind CSS, JavaScript bundles) that are not needed at runtime.

**Why multi-stage for orchestrator:**

- **Build-time dependencies**: The orchestrator requires npm and Node.js to compile Tailwind CSS from `styles/tailwind.css` into `static/tailwind.css`. These tools are only needed during the build phase.
- **Image size optimization**: The production runtime only needs Python, so separating build tools reduces final image size significantly (~200MB vs ~500MB with build tools).
- **Security**: Fewer packages in the production image means a smaller attack surface.
- **Layer caching**: Build tools change infrequently, so build-stage layers cache well and speed up subsequent builds.

**Pattern**: The build stage installs npm dependencies and compiles CSS, then a final stage copies only the compiled artifacts and Python runtime dependencies.

**Implementation**: `src/orchestrator/Dockerfile` uses a multi-stage build to compile Tailwind CSS before the final Python image. The `entrypoint.sh` script is copied explicitly via `COPY entrypoint.sh /app/entrypoint.sh` followed by `RUN chmod +x` to ensure it's executable regardless of source permissions. This pattern is suitable when build-time assets (like compiled CSS) need to be generated.

### Single-Stage Builds (Docker Proxy, Vault)

Minimal services like `docker-proxy` and infrastructure components use single-stage Dockerfiles because they have no build-time dependencies—they're pure Python applications that can run directly from source.

**Why single-stage for minimal services:**

- **No build-time dependencies**: These services don't require compilation or asset bundling.
- **Simplicity**: Single-stage Dockerfiles are easier to maintain and understand.
- **Performance**: Faster build times without the overhead of multi-stage coordination.
- **Size**: Already minimal, so no benefit from separating stages.

**Implementation examples:**

- **`infra/docker-proxy/Dockerfile`**: Uses a single-stage build with explicit `COPY entrypoint.sh /entrypoint.sh` followed by `RUN chmod +x`. This ensures the entrypoint script is executable regardless of source permissions. This pattern is preferred for services that don't require multi-stage builds.

- **`infra/vault/Dockerfile`**: Uses a single-stage build with explicit COPY and chmod for the entrypoint, similar to docker-proxy. This pattern is suitable for Python applications that run directly from source.

### Entrypoint Script Patterns

Entrypoint scripts handle container initialization and user privilege management:

- **`src/orchestrator/entrypoint.sh`**: Simple script that ensures the `orchestrator` user owns the log directory when running as root, then drops privileges using `su-exec`. This pattern is suitable when the service doesn't need special filesystem permissions.

- **`infra/docker-proxy/entrypoint.sh`**: Complex script that dynamically detects the Docker socket's group ownership and configures the `dockerproxy` user to access it. This is necessary because Docker socket permissions vary across different host configurations. The script:
  1. Detects the socket's group ID (GID)
  2. Finds or creates a group with that GID
  3. Adds the dockerproxy user to that group
  4. Executes the service as the dockerproxy user with the correct group

  This pattern is required when services need to access host resources (like Docker sockets) with varying permissions.

- **`infra/vault/entrypoint.sh`**: Handles Vault container initialization and ensures proper permissions for data directories; keeps it POSIX sh compatible.

**Best practices:**

- When creating new entrypoint scripts, prefer the simple pattern unless the service needs dynamic permission configuration.
- Always use `su-exec` (not `su`) for dropping privileges in Alpine-based images, as it's designed for containers and doesn't require a full shell.
- When creating new Dockerfiles, prefer the explicit `COPY entrypoint.sh /path/entrypoint.sh` followed by `RUN chmod +x` pattern for entrypoint scripts to ensure consistent behavior across different build environments.
- Use multi-stage builds only when build-time compilation or asset generation is required.

## Go CLI guidelines (`tools/cli/`)

- **TUI Architecture**: The CLI uses Bubbletea for the interactive interface with
  a view-based architecture. Core components are:
  - `tools/cli/ui/model.go` — State management and model definition
  - `tools/cli/ui/view.go` — Lipgloss rendering and layout
  - `tools/cli/ui/update.go` — Message handling and state transitions
  - `tools/cli/ui/runner.go` — Bubbletea program initialization
- **Commands**: Business logic lives in `tools/cli/cmd/*.go` subcommands. Keep TUI
  code separate from command logic.
- **Styling**: Use Lipgloss for consistent terminal styling. Follow the existing
  color scheme and layout patterns.
- **Imports**: Group standard library, third-party (Bubbletea, Cobra, Lipgloss),
  and local imports separately.

## Verification & validation

- Install and use pre-commit hooks: `pip install pre-commit && pre-commit install`
  The hooks automatically run Ruff, shellcheck, YAML validation, and other checks before each commit.
- For Python syntax safety, run `python -m compileall src/orchestrator infra/docker-proxy`
  before committing.
- When you touch front-end assets, run `npm install` (once) and then
  `npm run build:css` inside `src/orchestrator/` to refresh the generated CSS.
- If you modify docker-compose services or shell scripts, validate them with
  `docker compose -f docker-generated.yml config` and `shellcheck` where available.
- Manual verification: start the stack with `docker compose -f docker-generated.yml up --build` and visit
  the orchestrator dashboard to confirm rotation metrics still stream.

## Environment Variable Naming Conventions

Leyzen Vault follows a standardized naming convention for environment variables to ensure consistency and clarity. All environment variables are documented in `env.template` with their purpose, defaults, and validation rules.

### Naming Prefixes

Environment variables use specific prefixes to indicate their scope and purpose:

- **`VAULT_*`**: Variables specific to Leyzen Vault core functionality only
  - Examples: `VAULT_URL`, `VAULT_MAX_UPLOADS_PER_HOUR`, `VAULT_MAX_FILE_SIZE_MB`
  - Used by: Vault application only

- **`ORCH_*`**: Variables specific to the Orchestrator only
  - Examples: `ORCH_USER`, `ORCH_PASS`, `ORCH_WEB_CONTAINERS`, `ORCH_PORT`
  - Used by: Orchestrator application only

- **`DOCKER_*`**: Variables for Docker/Docker Proxy configuration
  - Examples: `DOCKER_PROXY_URL`, `DOCKER_SOCKET_PATH`
  - Used by: Docker proxy service and orchestrator

- **`LEYZEN_*`**: Variables for Leyzen Vault infrastructure/tooling
  - Examples: `LEYZEN_ENV_FILE`, `LEYZEN_ENVIRONMENT`
  - Used by: Build scripts, CLI tools, and multiple services

- **No prefix**: Variables shared between services or used by infrastructure
  - Examples: `SECRET_KEY`, `PROXY_TRUST_COUNT`, `HTTP_PORT`, `SSL_CERT_PATH`
  - Used by: Multiple services or infrastructure components

### Best Practices

1. **When adding new environment variables**:
   - Choose the appropriate prefix based on scope (VAULT*\*, ORCH*\_, DOCKER\_\_, LEYZEN\_\*, or no prefix)
   - Document the variable in `env.template` with description, defaults, and validation rules
   - Update validation in both Python (`src/*/config.py`) and Go (`tools/cli/cmd/validate.go`) if needed
   - Add the variable to the appropriate settings dataclass (VaultSettings or Settings)

2. **When modifying existing variables**:
   - Maintain backward compatibility when possible
   - Update documentation in `env.template`
   - Update validation logic in both Python and Go implementations
   - Update any references in documentation (README.md, AGENTS.md, etc.)

3. **Validation synchronization**:
   - Python validation: `src/vault/config.py`, `src/orchestrator/config.py`
   - Go validation: `tools/cli/cmd/validate.go`
   - Both implementations must stay synchronized (see `src/common/env.py` for notes on duplication)

### Examples

```python
# Good: Uses VAULT_* prefix for vault-specific settings
VAULT_MAX_FILE_SIZE_MB=100
VAULT_MAX_UPLOADS_PER_HOUR=50

# Good: Uses ORCH_* prefix for orchestrator-specific settings
ORCH_USER=admin
ORCH_PORT=80

# Good: No prefix for shared settings
SECRET_KEY=...
PROXY_TRUST_COUNT=1

# Bad: Inconsistent prefix usage
VAULT_ORCH_USER=admin  # Should be ORCH_USER
ORCH_VAULT_MAX_SIZE=100  # Should be VAULT_MAX_FILE_SIZE_MB
```

## Authentication and Authorization Differences

Leyzen Vault uses different authentication mechanisms for the Vault application (SPA) and the Orchestrator dashboard (server-rendered). See [`docs/AUTHENTICATION.md`](AUTHENTICATION.md) for detailed documentation on:

- Differences between `login_required()` implementations
- CAPTCHA and CSRF token handling
- Authentication flows for both applications
- Best practices for adding authentication to new services

## Documentation & operational notes

- Update `README.md` for user-facing changes. For operational or security
  adjustments, update the relevant pages in the [official documentation](https://docs.leyzen.com).
- Security-sensitive tweaks (auth flow, captcha, CSP reporting) should include a
  short rationale in commit messages or doc updates.
- See [`docs/README.md`](README.md) for a complete documentation map and links to all documentation files.

Happy hacking!
