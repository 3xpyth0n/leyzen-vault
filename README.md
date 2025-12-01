# Leyzen Vault 🛰️

**Version 2.3.0**

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](https://github.com/3xpyth0n/leyzen-vault/blob/main/LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](https://github.com/3xpyth0n/leyzen-vault/issues)

> **Modular Moving-Target Defense Orchestrator — Enterprise-Grade Secure File Storage**
>
> Licensed under the **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE) for details.

Leyzen Vault automates ephemeral container rotation for a secure file storage system with enterprise-grade features. A hardened Flask orchestrator coordinates Docker lifecycle operations through an allowlisted proxy, while HAProxy front-ends every request with strict security headers. The system demonstrates how moving-target defense principles can be applied to real-world stacks without sacrificing observability or operator experience.

**Version 2.3.0 Highlights**: Preview support for video, audio, text, and markdown files, enhanced UI with VaultSpace pinning, dynamic icon system, conflict resolution, and multiple bug fixes. See [`CHANGELOG.md`](CHANGELOG.md) for full details.

**End-to-End Encryption (E2EE)**: Files are encrypted client-side using the Web Crypto API (AES-GCM) before being uploaded to the server. The server stores only encrypted data and never has access to encryption keys or decrypted content. Decryption happens entirely in the user's browser when downloading files. This ensures that even if the server is compromised, file contents remain protected.

## Author

**Saad Idrissi** — a French cybersecurity student passionate about secure systems, automation, and digital defense.
He created **Leyzen Vault** as a personal initiative to explore advanced moving-target defense concepts and practical infrastructure hardening.
🌐 [portfolio.leyzen.com](https://portfolio.leyzen.com)

## Feature Highlights

### Core Features

- **Dynamic stack composition** – `leyzenctl` regenerates Docker Compose and HAProxy artifacts on every lifecycle command so configuration always reflects the current setup.
- **Rotation-aware control plane** – The orchestrator promotes one healthy replica at a time, keeps rotation state auditable, and exposes SSE telemetry for dashboards and automations.
- **Defense-in-depth defaults** – CAPTCHA-backed authentication, CSP reporting, proxy trust limits, and bearer-token Docker access are enabled from the first boot.
- **VaultSpaces** – Workspace system with personal spaces, each with its own encryption keys.

### Enterprise Features

- **Single Sign-On (SSO)** – SSO support with SAML, OAuth2, and OIDC providers.
- **REST API v2** – Comprehensive RESTful API with JWT authentication for all operations.
- **Search** – Encrypted search functionality with searchable encryption for secure, privacy-preserving file search.
- **Admin Dashboard** – Comprehensive admin dashboard with user management, system settings, and analytics.

### Security & Privacy

- **PostgreSQL Database** – Secure database storage for all metadata, users, and system data.
- **JWT Authentication** – JWT-based authentication for API endpoints with token refresh and blacklist support.
- **Hierarchical Key Management** – VaultSpace keys and file keys, all encrypted with user master keys.
- **Email Verification** – Email verification system for new user accounts.
- **Device Management** – Device registration and management for enhanced security.
- **Audit Logging** – Enhanced audit logging with PostgreSQL storage and automatic cleanup.

## Documentation

**Documentation Map**: Leyzen Vault maintains two types of documentation:

- **📚 Official Documentation** - For operators, users, and day-to-day usage. Contains guides on installation, configuration, CLI usage, architecture overview, and operational procedures. Available at [https://docs.leyzen.com](https://docs.leyzen.com).
- **Repository `docs/` directory** - For developers and contributors. Contains coding standards, security policies, contribution guidelines, and code-level implementation details.

If you're **using** Leyzen Vault, start with the [Quickstart guide](https://docs.leyzen.com/getting-started/quickstart). If you're **contributing** code, start with [`docs/AGENTS.md`](docs/AGENTS.md) and [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

### 📚 Official Documentation (User & Operational Guides)

Primary user-facing and operational documentation is maintained at [https://docs.leyzen.com](https://docs.leyzen.com):

- [Home](https://docs.leyzen.com/)
- [Quickstart](https://docs.leyzen.com/getting-started/quickstart)
- [Architecture Overview](https://docs.leyzen.com/architecture/overview)
- [Security Model](https://docs.leyzen.com/security/security-model)
- [`leyzenctl` CLI](https://docs.leyzen.com/cli/leyzenctl)
- [Vault Service & VaultSpaces](https://docs.leyzen.com/vaultspaces/vault)
- [Telemetry & Monitoring](https://docs.leyzen.com/orchestrator/telemetry)
- [CI/CD Workflows](https://docs.leyzen.com/ci-cd)
- [Developer Guide](https://docs.leyzen.com/developer-guide)
- [FAQ](https://docs.leyzen.com/faq)

### Repository Documentation (Code & Policies)

Repository-level documentation for developers and contributors:

- [`docs/AGENTS.md`](docs/AGENTS.md) — Code style and architecture guidelines for AI assistants and contributors
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture, service startup order, and component communication
- [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) — Complete REST API v2 documentation
- [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) — Authentication architecture and implementation details
- [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) — Developer guide for contributing to the project
- [`docs/SECURITY.md`](docs/SECURITY.md) — Security policy and vulnerability reporting
- [`docs/SECURITY_RUNTIME.md`](docs/SECURITY_RUNTIME.md) — Runtime security controls and implementation details
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — Contribution workflow and commit conventions
- [`docs/CODE_OF_CONDUCT.md`](docs/CODE_OF_CONDUCT.md) — Community standards
- [`CHANGELOG.md`](CHANGELOG.md) — Release history and changes

## Getting Started

Clone the repository, copy `env.template` to `.env`, and build the CLI with `./install.sh`. Full installation, configuration, and first-run steps are documented in the [Quickstart guide](https://docs.leyzen.com/getting-started/quickstart).

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
./install.sh
./leyzenctl start
```

**First Run Setup**: On first startup, visit `/setup` to create your superadmin account. The system will check if any users exist in the PostgreSQL database. If none are found, the setup endpoint will be available. After creating the first user, the setup endpoint is automatically disabled for security.

**PostgreSQL Required**: Version 2.0.0 requires PostgreSQL 16 for production deployments. The database schema is automatically created on first startup. Ensure PostgreSQL is running and configured before starting the application.

**Configuration**: You can override the default `.env` file location by setting the `LEYZEN_ENV_FILE` environment variable to an absolute or relative path. This is useful for managing multiple environments or CI/CD pipelines. See `env.template` for all available configuration options.

**Note**: The `docker-generated.yml` file in the repository root is automatically generated by `src/compose/build.py`. Do not edit it manually; it will be regenerated by `leyzenctl` commands or when running the build script directly.

## Architecture at a Glance

Leyzen Vault v2.3.0 comprises:

- **Go CLI** (`leyzenctl`) for container lifecycle management
- **Python Backend** (Flask) with PostgreSQL database and REST API v2
- **Vue.js Frontend** (SPA) with modern UI/UX
- **HAProxy** front-end reverse proxy with strict security headers
- **Docker Proxy** for authenticated Docker Engine API access
- **Flask Orchestrator** with rotation telemetry and SSE streaming
- **PostgreSQL** database for all metadata, users, and system data

Review the [Architecture Overview](https://docs.leyzen.com/architecture/overview) page for diagrams, rotation flow, and component responsibilities. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detailed technical documentation.

## Security & Compliance

Security disclosures follow the process documented in [`docs/SECURITY.md`](docs/SECURITY.md). Runtime protections—including CSP enforcement, captcha, CSRF, proxy trust, and Docker proxy allowlists—are detailed in the [Security Model](https://docs.leyzen.com/security/security-model).

## Contributing

We welcome pull requests and feature ideas! Start with the [Developer Guide](https://docs.leyzen.com/developer-guide) for repository conventions, then review [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) and the [Code of Conduct](docs/CODE_OF_CONDUCT.md) before opening an issue or PR.

## Support & Contact

- File bugs or feature requests in [GitHub Issues](https://github.com/3xpyth0n/leyzen-vault/issues).
- Security reports should be submitted privately per [`docs/SECURITY.md`](docs/SECURITY.md).
- For release history, consult [`CHANGELOG.md`](CHANGELOG.md).

## Repository Structure

The repository is organized as follows:

- **`leyzen-vault/`** - Main Leyzen Vault project (core moving-target defense orchestrator)
  - `src/` - Python source code (orchestrator, compose builder, vault application, common utilities)
  - `infra/` - Infrastructure components (HAProxy config, Docker proxy, vault Dockerfile)
  - `tools/cli/` - Go CLI source code (`leyzenctl`)
  - `docs/` - Developer documentation and policies

## Activity

![Alt](https://repobeats.axiom.co/api/embed/dacac14edc54fdcb66274584d1ba09544c99d929.svg "Repobeats analytics image")

## License

Source code is available under the Business Source License 1.1 (BSL 1.1).
