# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Replaced 'q' key quit binding with CTRL+C requiring double-press confirmation to prevent accidental exits when typing in wizard fields.
- Migrated orchestrator Docker proxy client from `requests` to `httpx` for consistency across HTTP libraries.
- Updated all TUI footer hints and help messages to display CTRL+C instead of 'q' for quitting the application.

### Added

- Added deprecation warnings in `leyzenctl config validate` for deprecated CSP variables (`CSP_REPORT_MAX_SIZE`, `CSP_REPORT_RATE_LIMIT`). Users are advised to migrate to `VAULT_CSP_REPORT_MAX_SIZE` and `VAULT_CSP_REPORT_RATE_LIMIT`. Support for deprecated variables will be removed in a future major version.
- Added optional HTTPS/SSL support for HAProxy through environment variables (`VAULT_ENABLE_HTTPS`, `VAULT_SSL_CERT_PATH`, `VAULT_SSL_KEY_PATH`). When enabled, HAProxy listens on port 443 (container) and terminates TLS before forwarding to backend services. Certificate files are validated at build time with warnings displayed if files are missing. Supports both combined PEM files (cert+key) and separate certificate/key files.
- Added configurable HTTP and HTTPS port mapping for HAProxy via `VAULT_HTTP_PORT` and `VAULT_HTTPS_PORT` environment variables. Defaults to 8080 for HTTP and 8443 for HTTPS to avoid conflicts with standard ports, but can be customized to use standard ports (80/443) or any other valid port range (1-65535). Ports are validated and clamped to valid ranges during configuration generation.

### Fixed

- Removed unused `VAULT_DOCKER_NETWORK` configuration variable from wizard prompts and validators.
- Cleaned up redundant `LEYZEN_ENV_FILE` handling in orchestrator config after `load_env_with_override()` call.
- Standardized on `DOCKER_PROXY_LOG_LEVEL` environment variable (removed fallback to `LOG_LEVEL`).
- Removed inline fallback implementation of `parse_container_names` in `infra/docker-proxy/proxy.py` to prevent code divergence.
- Reorganized imports in `infra/docker-proxy/proxy.py` to comply with AGENTS.md guidelines (stdlib → third-party → local).
- Added warning comment to auto-generated `docker-compose.yml` and documented generation process in README.

## [1.1.0] - 2025-11-03

### Added

- Introduced a shared `src/common/env.py` module centralizing the `.env` reader and container-name parser helpers for consistent reuse across all services.
- Implemented a dedicated `RotationTelemetry` helper responsible for metrics computation, historical data tracking, and cached snapshot management.
- Expanded the CI workflow to install runtime dependencies and lint with **Ruff**.
- Added the Go-based `leyzenctl` CLI for Docker stack lifecycle and environment configuration management, replacing the legacy shell helper.
- Added a Bubbletea- and Lipgloss-powered interactive dashboard to `leyzenctl` when no subcommand is supplied, surfacing live container status, logs, and lifecycle controls.
- Implemented comprehensive view navigation system with `ViewState` enum supporting distinct views: Dashboard, Logs, Action, Config, and Wizard.
- Added interactive configuration wizard fully integrated into TUI with dynamic text input fields supporting all environment variables.
- Added dedicated Config view (`c` key) displaying all environment variables organized by logical categories (Vault, Docker Proxy, Filebrowser, Paperless, CSP, Proxy, General).
- Added password visibility toggle in Config view (Space key) to reveal/hide sensitive values (passwords, secrets, tokens, keys).
- Added scrollable viewport for Config view enabling navigation through long lists of variables with arrow keys and page up/down.
- Implemented automatic return to dashboard after action completion with ephemeral success messages.
- Added wizard navigation with one-field-per-page interface using Previous (`←`) and Next (`→`) arrow keys, with progress indicator.
- Added automatic initialization from `env.template` when `.env` file is empty, copying all template variables to enable immediate configuration.
- Added context-sensitive footer hints that update based on current view (Dashboard, Logs, Config, Wizard).

### Changed

- Updated the Compose builder, orchestrator configuration loader, and plugin registry to import shared helpers from `src/common/env.py` instead of maintaining local copies.
- Refactored `RotationService` to delegate metrics collection and snapshot handling to the new `RotationTelemetry` helper while preserving rotation logic and Docker interactions.
- Default `leyzenctl` execution now launches the interactive TUI while a new `--no-ui` flag preserves headless scripting behaviour for CI and automation use-cases.
- Refactored TUI architecture to use explicit view state transitions with `switchTo*()` methods ensuring clean state management between views.
- Wizard now dynamically loads all environment variables from `.env` file instead of hardcoded fields, supporting unlimited variable configuration.
- Made all wizard fields optional (removed 8-character minimum password requirement) allowing flexible configuration for optional values.
- Enhanced log filtering to remove control characters and malformed artifacts preventing display issues on dashboard.

### Fixed

- Modified the entrypoint to dynamically import the orchestrator configuration module after resolving the package path,
  ensuring it runs correctly in both CI and container environments.
- Preserved defensive error handling and static-analysis hints for ConfigurationError.
- Relaxed Filebrowser entrypoint privilege dropping so the container keeps running when mounted volumes cannot be written by
  the service user, aiding recovery on hosts with restrictive permissions.
- Resolved a regression in the Filebrowser entrypoint privilege probe that triggered `tmp: parameter not set` errors while
  checking mounted volume write access.
- Handled pre-existing Filebrowser databases during configuration initialization so restarts no longer loop when only the
  settings file is absent.
- Ensured `leyzenctl --env-file` propagates the selected environment file to both `compose/build.py` and subsequent Docker
  Compose invocations so alternate `.env` files stay in sync with generated assets.
- Fixed logs and action output polluting dashboard after returning from wizard or action views through comprehensive state cleanup.
- Fixed scroll functionality in Config view by ensuring viewport correctly receives scroll key events (arrow keys, page up/down, home/end).
- Fixed wizard hints appearing on dashboard after wizard completion by explicitly setting footer context on view transitions.
- Fixed state persistence issues when switching between views by implementing proper cleanup of logs, viewport content, and wizard state.
- Fixed rebuild script output appearing in TUI after wizard save by capturing output to silent buffer.

### Documentation

- Consolidated the README and legacy guides to point at the GitHub Wiki `/wiki`.

## Migration from 1.0.0 to 1.1.0

### Breaking Changes

- **VAULT_USER is now required**: The `VAULT_USER` environment variable is now mandatory. Previously, if not set, the system would default to `"admin"`. You must now explicitly set a non-default username in your `.env` file. If you were relying on the default, update your `.env`:

  ```bash
  VAULT_USER=your_username_here
  ```

- **VAULT_DOCKER_NETWORK removed**: The `VAULT_DOCKER_NETWORK` configuration variable has been removed as it was unused. If you have this variable in your `.env` file, you can safely remove it.

- **Plugin replicas no longer hardcoded**: Plugins (filebrowser, paperless) no longer have hardcoded default replica counts. You must explicitly set `VAULT_WEB_REPLICAS` in your `.env` file. The minimum number of replicas is enforced by each plugin (typically 2 for filebrowser and paperless). Example:

  ```bash
  VAULT_WEB_REPLICAS=3
  ```

### Security Enhancements

- **Secret length validation**: Cryptographic secrets (`VAULT_SECRET_KEY`, `DOCKER_PROXY_TOKEN`) must now be at least 12 characters long. Ensure your secrets meet this requirement:

  ```bash
  # Generate secure secrets
  openssl rand -hex 32  # Generates 64-character hex string
  ```

### Configuration Updates

1. **Update your `.env` file**:
   - Add `VAULT_USER` with a non-default value
   - Set `VAULT_WEB_REPLICAS` explicitly (e.g., `VAULT_WEB_REPLICAS=3`)
   - Remove `VAULT_DOCKER_NETWORK` if present
   - Verify `VAULT_SECRET_KEY` and `DOCKER_PROXY_TOKEN` are at least 12 characters

2. **Verify configuration**:
   After updating your `.env`, run `./leyzenctl build` to regenerate Docker Compose configuration and verify there are no errors.

[1.1.0]: https://github.com/3xpyth0n/leyzen-vault/releases/tag/v1.1.0

---

## [1.0.0] - 2025-11-01

This is the first public release of Leyzen Vault under the Business Source License 1.1 (BSL 1.1).

### Added

- Modular plugin architecture with reference Filebrowser and Paperless integrations under `vault_plugins/`.
- Dynamic Docker Compose manifest builder that assembles plugin-defined services alongside the base stack.
- Automatic HAProxy configuration rendering aligned with plugin routing rules and health checks.
- Centralized `leyzenctl` CLI orchestrating build, deploy, restart, and shutdown workflows.
- Security hardening for the orchestrator, including CSP enforcement, CSRF protections, and rate-limited reporting endpoints.
- Observability dashboards and logging pipelines surfaced through the orchestrator UI.

### Changed

- Unified plugin registry, environment loading, and manifest generation to streamline stack composition.
- Refactored HAProxy and Compose generation to regenerate configuration artifacts on every lifecycle event.
- Hardened request handling and session management in the orchestrator to support CSP, CSRF, and authentication controls.
- Adopted the Business Source License 1.1 (BSL 1.1) as the governing license for the public code release.

### Fixed

- Improved health check coordination and startup ordering across orchestrator, proxy, and plugin containers to reduce race conditions.
- Resolved HAProxy validation edge cases by linting generated configurations before reloads.
- Stabilized plugin activation flow to surface descriptive errors when configuration inputs are missing or invalid.

### Documentation

- Rewrote the README to highlight modular architecture, security posture, and operational workflows.
- Added comprehensive guides in `docs/` for developers, operators, and maintainers.
- Published community and security policies (`CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `MAINTAINER_GUIDE.md`).

[1.0.0]: https://github.com/3xpyth0n/leyzen-vault/releases/tag/v1.0.0
