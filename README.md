# Leyzen Vault ⚙️

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](https://github.com/3xpyth0n/leyzen-vault/issues)

> **Modular Moving-Target Defense Orchestrator — Proof of Concept**
>
> Licensed under the **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE) for details.
>
> Leyzen Vault automates ephemeral container rotation, routing, and build orchestration across pluggable service stacks.

---

## Table of Contents

- [Overview](#overview-)
- [Key Capabilities](#key-capabilities-)
- [Core Components](#core-components-)
- [Reference Architecture](#reference-architecture-)
- [Quick Start](#quick-start-)
- [Configuration](#configuration-)
- [Plugin Registry](#plugin-registry-)
- [Security](#security-)
- [Service Endpoints](#service-endpoints-)
- [Further Documentation](#further-documentation-)
- [License](#license-)
- [Support and Contact](#support-and-contact-)
- [Policies and Guidelines](#policies-and-guidelines-)
- [Project Status](#project-status-)
- [Credits](#credits-)

---

## Overview 🧩

Leyzen Vault is a **modular moving-target defense orchestrator** built to showcase automated container polymorphism. Instead of
shipping a single, static application stack, Vault assembles the runtime environment from **service plugins**. Each plugin
describes the containers, dependencies, and routing rules for a particular workload. The orchestration workflow reads your
configuration, loads the requested plugin, and regenerates both Docker Compose and HAProxy artifacts before every lifecycle
operation.

The repository ships with Filebrowser and Paperless plugins as reference implementations. They illustrate the pattern; the
system is designed to host many more services as the plugin catalog grows.

---

## Key Capabilities 🔑

- **Dynamic stack composition** — Docker Compose manifests are generated on demand from the selected plugin, ensuring only the
  required containers are started.
- **Automatic HAProxy configuration** — Backend pools and health checks adapt to the plugin’s replicas and port definitions
  without manual edits.
- **Autonomous container rotation** — The Python orchestrator continuously rotates web-facing containers to shrink attacker dwell
  time.
- **Self-healing deployment** — Health checks restart failing components and keep the stack aligned with the declared replica
  count.
- **Centralized observability** — The orchestrator dashboard exposes rotation metrics, audit logs, and plugin status.

---

## Core Components ⚙️

| Component              | Description                                                                                                    |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Vault Orchestrator** | Python service managing container rotation, metrics, and dashboard rendering.                                  |
| **Service Plugins**    | Modular definitions under [`vault_plugins/`](vault_plugins/) that describe how to run each supported workload. |
| **HAProxy**            | Reverse proxy exposed on port **8080**, regenerated automatically with the correct backends for each plugin.   |
| **Docker Proxy**       | Authenticated control plane for Docker Engine actions invoked by the orchestrator.                             |
| **Shared Volumes**     | Plugin-declared volumes persisting state across ephemeral container rotations.                                 |

---

## Reference Architecture 🧱

```
                   ┌───────────────┐
                   │    Client     │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  HAProxy 8080 │
                   └───────┬───────┘
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
  ┌─────────────────┐            ┌────────────────────────┐
  │  Orchestrator   │            │  Plugin-defined Stack  │
  │   (dashboard)   │            │   (rotating replicas)  │
  └─────────────────┘            └────────────────────────┘
```

---

## Quick Start 🏁

1. **Clone and prepare the repository:**

   ```bash
   git clone https://github.com/3xpyth0n/leyzen-vault.git
   cd leyzen-vault
   cp env.template .env
   ```

2. **Configure `.env`:** set secrets and select a plugin.
   - `VAULT_SERVICE` — service plugin to deploy (`filebrowser`, `paperless`, or any installed plugin).
   - `VAULT_WEB_REPLICAS` — number of web containers created for the plugin.
   - `VAULT_WEB_PORT` — optional override for the plugin’s internal HTTP port.
   - `VAULT_WEB_HEALTHCHECK_PATH` (referenced as `VAULT_HEALTH_PATH` in examples) — optional path for HAProxy health checks
     (defaults to the plugin’s value).
   - Credentials (`VAULT_USER`, `VAULT_PASS`, `VAULT_SECRET_KEY`, etc.) and Docker proxy settings as documented in
     [`env.template`](env.template).

3. **Operate exclusively through `service.sh`:** the helper script is the only supported interface. It rebuilds the Compose
   manifest and HAProxy configuration before executing the requested action.

   ```bash
   ./service.sh build     # Build images for the orchestrator, plugins, and supporting services
   ./service.sh start     # Generate configs and launch the stack
   ./service.sh restart   # Regenerate configs, then cycle containers
   ./service.sh stop      # Stop containers and clean up resources (volumes persist)
   ```

   Avoid manual `docker compose` or Python builder commands; bypassing `service.sh` will leave configuration artifacts
   inconsistent with your `.env` selections.

4. **Access the dashboard:** browse to `http://localhost:8080/orchestrator` and sign in with the credentials stored in `.env`.

> 💡 **HTTP testing reminder:** when running without TLS, set `VAULT_SESSION_COOKIE_SECURE=false` so browsers send the session
> cookie over plain HTTP.

---

## Configuration 🧪

Environment variables live in `.env`. Restrict access (for example, `chmod 600 .env`) and rotate secrets regularly. Key entries:

- `VAULT_SERVICE` — selects the active plugin at runtime. Invalid names trigger a descriptive error listing available plugins.
- `VAULT_WEB_REPLICAS` — scales the number of web-facing containers the plugin exposes.
- `VAULT_WEB_PORT` — overrides the plugin’s internal HTTP port when custom routing is required.
- `VAULT_WEB_HEALTHCHECK_PATH` (`VAULT_HEALTH_PATH`) — optional health-check path emitted by HAProxy (defaults to plugin
  definition).
- `VAULT_USER` / `VAULT_PASS` / `VAULT_SECRET_KEY` — orchestrator credentials and Flask secret key.
- `DOCKER_PROXY_URL` / `DOCKER_PROXY_TOKEN` — access controls for the Docker proxy.
- `PROXY_TRUST_COUNT` — forwarded header trust depth; keep `1` when HAProxy fronts the stack.

Consult [`env.template`](env.template) for the full catalog and inline documentation of each setting.

Shared Docker volumes are declared per plugin in the generated `docker-compose.generated.yml`. When switching plugins, Vault
creates or reuses the volumes specified by the selected module so state persists across rotations without leaking between
services.

---

## Plugin Registry 📦

Plugins reside under [`vault_plugins/<service>/plugin.py`](vault_plugins/). Each module subclasses `VaultServicePlugin` and
implements:

- `metadata` describing the service name and default internal port.
- `build_compose(env)` returning Compose fragments for the plugin’s services and volumes.
- `get_containers()` returning the set of container names eligible for rotation by the orchestrator.

The registry is automatically discovered at runtime. When `VAULT_SERVICE` references a plugin, `service.sh` invokes the builder to
render:

1. `docker-compose.generated.yml` — the merged Compose manifest combining the base stack with the plugin.
2. `haproxy/haproxy.cfg` — backend pools, health checks, and routing logic for the plugin’s replicas.

Filebrowser and Paperless are bundled examples demonstrating the pattern. Contributions adding new plugins are welcome—see the
[Developer Guide](docs/DEVELOPER_GUIDE.md) for implementation details.

---

## Security 🔐

Leyzen Vault ships with layered safeguards intended to shrink the attack surface while keeping the demo stack operable:

- **Browser protections** — Orchestrator templates enforce a strict Content Security Policy (CSP) and embed CSRF tokens so that
  authenticated actions cannot be replayed from foreign origins.
- **Abuse defenses** — Login flows require CAPTCHA completion and throttle repeated attempts, limiting credential stuffing
  windows.
- **Network isolation** — Administrative Docker operations are gated behind the separate [`docker-proxy`](docker-proxy) service,
  ensuring the Docker socket is never exposed directly to end users.
- **Secrets hygiene** — All credentials and API tokens reside in a local `.env` file with restrictive permissions.

Operationally critical settings include:

- `VAULT_SESSION_COOKIE_SECURE` — keep this enabled in production so session cookies are transmitted only over HTTPS; disable
  temporarily **only** for local HTTP testing.
- `DOCKER_PROXY_TOKEN` — rotate the proxy bearer token regularly and update any automation that references it.
- `.env` permissions — ensure only trusted administrators can read secrets by locking down filesystem access bits.

For a deeper walkthrough of the threat model and mitigations, consult the [Security Policy](SECURITY.md) and extended
[Technical Guide](docs/TECHNICAL_GUIDE.md).

---

## Service Endpoints 🌐

| Service                          | URL / Port                                                               | Description                                                       |
| -------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| **HAProxy**                      | `:8080`                                                                  | Routes to the active plugin plus the orchestrator dashboard.      |
| **Docker Proxy**                 | internal (`docker-proxy:2375`)                                           | Mediates authenticated container lifecycle calls.                 |
| **Active web service**           | [http://localhost:8080/](http://localhost:8080/)                         | Plugin-provided UI (Filebrowser, Paperless, or other extensions). |
| **Vault Orchestrator Dashboard** | [http://localhost:8080/orchestrator](http://localhost:8080/orchestrator) | Real-time monitoring and control.                                 |

---

## Further Documentation 📚

- [Technical Guide](docs/TECHNICAL_GUIDE.md) — detailed architecture and workflow reference.
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — how to build and register new service plugins.
- [Operations Guide](docs/OPERATIONS.md) — recommended day-to-day command sequences.

---

## License 📄

This project is distributed under the [Business Source License 1.1](LICENSE). Until the change date of **2030-01-01**, the
Additional Use Grant permits personal, educational, and non-commercial internal use; other uses require a commercial license. On
the change date, the code automatically converts to **AGPLv3**. Notices for bundled third-party assets are listed in
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

## Support and Contact 🤝

Need help or found an issue?

- Open a ticket in the [GitHub issue tracker](https://github.com/3xpyth0n/leyzen-vault/issues).
- For private matters, reach out to the maintainer via the contact options on the [GitHub profile](https://github.com/3xpyth0n).

---

## Policies and Guidelines 📑

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

---

## Project Status 📊

Leyzen Vault is an evolving demonstrator exploring automated ephemeral backends, dynamic routing, and autonomous cyber defense
patterns. Automated GitHub Actions CI runs
[`python -m compileall orchestrator docker-proxy`](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml) on every
push and pull request to catch syntax issues early in both Python services.

---

## Credits 👤

**Author:** Saad Idrissi  
**Concept:** Disposable Compute — _Infrastructure as a Disposable Service_

---

> © 2025 Saad Idrissi — Licensed under the Business Source License 1.1.
