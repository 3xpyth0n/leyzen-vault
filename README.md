# Leyzen Vault 🛰️

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![Go Version](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go)](https://go.dev)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](https://github.com/3xpyth0n/leyzen-vault/issues)

> **Modular Moving-Target Defense Orchestrator — Proof of Concept**
>
> Licensed under the **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE) for details.

Leyzen Vault automates ephemeral container rotation across pluggable workloads. A hardened Flask orchestrator coordinates Docker lifecycle operations through an allowlisted proxy, while HAProxy front-ends every request with strict security headers. The system demonstrates how moving-target defense principles can be applied to real-world stacks without sacrificing observability or operator experience.

## Author

**Saad Idrissi** — a French cybersecurity student passionate about secure systems, automation, and digital defense.
He created **Leyzen Vault** as a personal initiative to explore advanced moving-target defense concepts and practical infrastructure hardening.
🌐 [portfolio.leyzen.com](https://portfolio.leyzen.com)

## Feature Highlights

- **Dynamic stack composition** – `leyzenctl` regenerates Docker Compose and HAProxy artifacts on every lifecycle command so configuration always reflects the active plugin.
- **Rotation-aware control plane** – The orchestrator promotes one healthy replica at a time, keeps rotation state auditable, and exposes SSE telemetry for dashboards and automations.
- **Defense-in-depth defaults** – Captcha-backed authentication, CSP reporting, proxy trust limits, and bearer-token Docker access are enabled from the first boot.
- **Extensible plugin model** – Service definitions live in Python packages under `src/vault_plugins/`, allowing new workloads to slot into the rotation loop with minimal boilerplate.

## Documentation

**Documentation Map**: Leyzen Vault maintains two types of documentation:

- **GitHub Wiki** - For operators, users, and day-to-day usage. Contains guides on installation, configuration, CLI usage, architecture overview, and operational procedures.
- **Repository `docs/` directory** - For developers and contributors. Contains coding standards, security policies, contribution guidelines, and code-level implementation details.

If you're **using** Leyzen Vault, start with the [GitHub Wiki Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart). If you're **contributing** code, start with [`docs/AGENTS.md`](docs/AGENTS.md) and [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

### GitHub Wiki (User & Operational Guides)

Primary user-facing and operational documentation is maintained in the [GitHub Wiki](https://github.com/3xpyth0n/leyzen-vault/wiki):

- [Home](https://github.com/3xpyth0n/leyzen-vault/wiki/Home)
- [Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart)
- [Architecture](https://github.com/3xpyth0n/leyzen-vault/wiki/Architecture)
- [Security Model](https://github.com/3xpyth0n/leyzen-vault/wiki/Security-Model)
- [`leyzenctl` CLI](https://github.com/3xpyth0n/leyzen-vault/wiki/leyzenctl)
- [Plugins](https://github.com/3xpyth0n/leyzen-vault/wiki/Plugins)
- [Telemetry](https://github.com/3xpyth0n/leyzen-vault/wiki/Telemetry)
- [CI/CD](https://github.com/3xpyth0n/leyzen-vault/wiki/CI-CD)
- [Developer Guide](https://github.com/3xpyth0n/leyzen-vault/wiki/Developer-Guide)
- [FAQ](https://github.com/3xpyth0n/leyzen-vault/wiki/FAQ)

### Repository Documentation (Code & Policies)

Repository-level documentation for developers and contributors:

- [`docs/AGENTS.md`](docs/AGENTS.md) — Code style and architecture guidelines for AI assistants and contributors
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System architecture, service startup order, and component communication
- [`docs/SECURITY.md`](docs/SECURITY.md) — Security policy and vulnerability reporting
- [`docs/SECURITY_RUNTIME.md`](docs/SECURITY_RUNTIME.md) — Runtime security controls and implementation details
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — Contribution workflow and commit conventions
- [`docs/CODE_OF_CONDUCT.md`](docs/CODE_OF_CONDUCT.md) — Community standards
- [`CHANGELOG.md`](CHANGELOG.md) — Release history and changes

## Getting Started

Clone the repository, copy `env.template` to `.env`, and build the CLI with `./install.sh`. Full installation, configuration, and first-run steps are documented in the [Quickstart guide](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart).

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
./install.sh
./leyzenctl start
```

**Configuration**: You can override the default `.env` file location by setting the `LEYZEN_ENV_FILE` environment variable to an absolute or relative path. This is useful for managing multiple environments or CI/CD pipelines. See `env.template` for all available configuration options.

**Note**: The `docker-compose.yml` file in the repository root is automatically generated by `src/compose/build.py`. Do not edit it manually; it will be regenerated by `leyzenctl` commands or when running the build script directly.

## Architecture at a Glance

Leyzen Vault comprises a Go CLI, Python builders, HAProxy front end, Docker proxy, and Flask orchestrator with rotation telemetry. Review the [Architecture](https://github.com/3xpyth0n/leyzen-vault/wiki/Architecture) page for diagrams, rotation flow, and component responsibilities.

## Security & Compliance

Security disclosures follow the process documented in [`docs/SECURITY.md`](docs/SECURITY.md). Runtime protections—including CSP enforcement, captcha, CSRF, proxy trust, and Docker proxy allowlists—are detailed in the [Security Model](https://github.com/3xpyth0n/leyzen-vault/wiki/Security-Model).

## Contributing

We welcome pull requests and plugin ideas! Start with the [Developer Guide](https://github.com/3xpyth0n/leyzen-vault/wiki/Developer-Guide) for repository conventions, then review [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) and the [Code of Conduct](docs/CODE_OF_CONDUCT.md) before opening an issue or PR.

## License

Source code is available under the Business Source License 1.1 (BSL 1.1). Commercial use after the change date or alternative licensing terms requires permission from the authors. See [`LICENSE`](LICENSE) and [`docs/TRADEMARKS.md`](docs/TRADEMARKS.md) for details.

## Support & Contact

- File bugs or feature requests in [GitHub Issues](https://github.com/3xpyth0n/leyzen-vault/issues).
- Security reports should be submitted privately per [`docs/SECURITY.md`](docs/SECURITY.md).
- For release history, consult [`CHANGELOG.md`](CHANGELOG.md).

## Repository Structure

The repository is organized as follows:

- **`leyzen-vault/`** - Main Leyzen Vault project (core moving-target defense orchestrator)
  - `src/` - Python source code (orchestrator, compose builder, plugins, common utilities)
  - `infra/` - Infrastructure components (HAProxy config, Docker proxy, filebrowser entrypoint)
  - `tools/cli/` - Go CLI source code (`leyzenctl`)
  - `docs/` - Developer documentation and policies
