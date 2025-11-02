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

### Changed

- Updated the Compose builder, orchestrator configuration loader, and plugin registry to import shared helpers from `leyzen_common.env` instead of maintaining local copies.
- Refactored `RotationService` to delegate metrics collection and snapshot handling to the new `RotationTelemetry` helper while preserving rotation logic and Docker interactions.

### Fixed

- Modified the entrypoint to dynamically import the orchestrator configuration module after resolving the package path,
  ensuring it runs correctly in both CI and container environments.
- Preserved defensive error handling and static-analysis hints for ConfigurationError.

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
