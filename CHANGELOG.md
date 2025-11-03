# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Introduced a shared `leyzen_common.env` module centralizing the `.env` reader and container-name parser helpers for consistent reuse across all services.
- Implemented a dedicated `RotationTelemetry` helper responsible for metrics computation, historical data tracking, and cached snapshot management.
- Expanded the CI workflow to install runtime dependencies, lint with **Ruff**, and run **pytest** for automated regression coverage.
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

- Updated the Compose builder, orchestrator configuration loader, and plugin registry to import shared helpers from `leyzen_common.env` instead of maintaining local copies.
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

---

This is the first public release of Leyzen Vault under the Business Source License 1.1 (BSL 1.1).

## [1.0.0] - 2025-11-01

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
