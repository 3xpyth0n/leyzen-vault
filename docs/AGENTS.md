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
- `infra/filebrowser/` — Dockerfile and entrypoint used to run the upstream Filebrowser
  binary with the correct defaults for the demo.
- `src/common/` — Shared Python modules (`env.py`, `exceptions.py`) used across
  services. Mounted at `/common` in containers.
- `src/compose/` — Python build scripts that generate `docker-compose.yml` and HAProxy
  configuration from plugin definitions and environment variables.
- `src/vault_plugins/` — Pluggable service definitions (filebrowser, paperless, etc.)
  that define container configurations and rotation behavior.
- `tools/cli/` — Go source code for the `leyzenctl` CLI tool. The CLI provides an
  interactive TUI (Terminal User Interface) built with Bubbletea and Lipgloss,
  plus headless mode for automation.
- `leyzenctl` — Deployment helper (Go CLI binary compiled by `install.sh`).

## Python guidelines (`src/orchestrator/`, `infra/docker-proxy/`)

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
- **Python path bootstrap**: When importing `common.*` or `vault_plugins.*` modules from
  entry points outside the `src/` directory, you must first bootstrap the Python path.
  The standard pattern is:
  1. Add `src/` to `sys.path` manually (this enables importing `common.path_setup`)
  2. Import `bootstrap_entry_point` from `common.path_setup`
  3. Call `bootstrap_entry_point()` to configure all paths (idempotent)
  4. Then import other `common.*` or `vault_plugins.*` modules

  This pattern is used in `src/orchestrator/app.py`, `infra/docker-proxy/proxy.py`, and
  `src/compose/build.py`. See these files for reference implementations. The bootstrap is
  necessary because these entry points are not executed from the `src/` directory, so
  Python's default import resolution cannot find the `common` and `vault_plugins` modules.

  For internal modules within `src/`, you can use `bootstrap_src_path()` or `setup_python_paths()`
  directly if you need to configure paths before importing other modules.

## Flask blueprints & templates (`src/orchestrator/blueprints`, `src/orchestrator/templates`)

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

## Front-end assets (`src/orchestrator/static`, `src/orchestrator/styles`)

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

## Service Startup Order

Services must start in a specific order to ensure dependencies are available:

1. **Base Infrastructure**: Docker networks and volumes are created first (handled by Docker Compose)
2. **Control Plane Services**:
   - `docker-proxy` starts first (required by orchestrator for container lifecycle operations)
   - `orchestrator` starts second and connects to docker-proxy
3. **Plugin Services**: Orchestrator manages plugin container startup after establishing control plane connectivity
4. **Front-end Layer**: `haproxy` starts last and connects to active containers via backend configuration

The orchestrator reads `VAULT_WEB_CONTAINERS` from the environment and starts plugin containers up to the configured replica count, waiting for health checks to pass before marking them as ready.

See [`docs/ARCHITECTURE.md`](ARCHITECTURE.md#service-startup-order) for detailed sequence diagrams and startup flow documentation.

## Supporting services

- `infra/docker-proxy/proxy.py` enforces bearer-token authentication and a strict
  endpoint allowlist. Maintain the pattern of compiling regular expressions at
  import time and validating headers in dedicated helpers.
- HAProxy templates should preserve the security headers already in place.
  Update both the config and error-page snippets if you tweak status handling.
- `infra/filebrowser/entrypoint.sh` is a thin wrapper; keep it POSIX sh compatible.

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

### Single-Stage Builds (Docker Proxy, Filebrowser)

Minimal services like `docker-proxy` and infrastructure components use single-stage Dockerfiles because they have no build-time dependencies—they're pure Python applications that can run directly from source.

**Why single-stage for minimal services:**

- **No build-time dependencies**: These services don't require compilation or asset bundling.
- **Simplicity**: Single-stage Dockerfiles are easier to maintain and understand.
- **Performance**: Faster build times without the overhead of multi-stage coordination.
- **Size**: Already minimal, so no benefit from separating stages.

**Implementation examples:**

- **`infra/docker-proxy/Dockerfile`**: Uses a single-stage build with explicit `COPY entrypoint.sh /entrypoint.sh` followed by `RUN chmod +x`. This ensures the entrypoint script is executable regardless of source permissions. This pattern is preferred for services that don't require multi-stage builds.

- **`infra/filebrowser/Dockerfile`**: Uses a single-stage build with explicit COPY and chmod for the entrypoint, similar to docker-proxy. Additionally includes checksum verification for downloaded binaries. This pattern is suitable for services that download and install external binaries.

### Entrypoint Script Patterns

Entrypoint scripts handle container initialization and user privilege management:

- **`src/orchestrator/entrypoint.sh`**: Simple script that ensures the `orchestrator` user owns the log directory when running as root, then drops privileges using `su-exec`. This pattern is suitable when the service doesn't need special filesystem permissions.

- **`infra/docker-proxy/entrypoint.sh`**: Complex script that dynamically detects the Docker socket's group ownership and configures the `dockerproxy` user to access it. This is necessary because Docker socket permissions vary across different host configurations. The script:
  1. Detects the socket's group ID (GID)
  2. Finds or creates a group with that GID
  3. Adds the dockerproxy user to that group
  4. Executes the service as the dockerproxy user with the correct group

  This pattern is required when services need to access host resources (like Docker sockets) with varying permissions.

- **`infra/filebrowser/entrypoint.sh`**: Thin wrapper for the upstream Filebrowser binary; keeps it POSIX sh compatible.

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
  `docker compose config` and `shellcheck` where available.
- Manual verification: start the stack with `docker compose up --build` and visit
  the orchestrator dashboard to confirm rotation metrics still stream.

## Documentation & operational notes

- Update `README.md` for user-facing changes. For operational or security
  adjustments, update the relevant pages in the [GitHub Wiki](https://github.com/3xpyth0n/leyzen-vault/wiki).
- Security-sensitive tweaks (auth flow, captcha, CSP reporting) should include a
  short rationale in commit messages or doc updates.

Happy hacking!
