# Leyzen Vault ⚙️

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](LICENSE)

> **Dynamic Moving-Target Infrastructure — Proof of Concept**
>
> Licensed under the **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE) for details.
>
> A self-rotating, self-healing environment built to demonstrate _ephemeral compute security_ through automated container polymorphism.

---

## Table of Contents

- [Overview](#overview-)
- [Key Features](#key-features-)
- [Core Components](#core-components-)
- [Reference Architecture](#reference-architecture-)
- [Prerequisites](#prerequisites-)
- [Installation](#installation-)
- [Configuration](#configuration-)
- [Usage](#usage-)
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

Leyzen Vault is a **proof-of-concept for moving-target defense**, applying infrastructure polymorphism to containerized applications. The orchestrator continuously rotates _Filebrowser_ backends while maintaining a seamless user experience. Each container’s lifecycle is ephemeral — born, used, and destroyed — minimizing the attack persistence window.

---

## Key Features 🔑

- **Autonomous container rotation** keeps workloads shifting to shrink the attacker dwell time window.
- **Self-healing deployment** restarts components automatically when health checks fail.
- **Centralized observability** exposes live orchestrator metrics and audit logs.
- **Security-first defaults** rely on minimal network exposure and enforced credential rotation.

---

## Core Components ⚙️

| Component               | Description                                                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Vault Orchestrator**  | Python-based orchestrator handling container rotation, metrics, and dashboard rendering.                                                    |
| **Filebrowser Cluster** | Trio of lightweight file-manager containers rotated polymorphically.                                                                        |
| **HAProxy**             | Reverse proxy exposed on port **8080**, routing users to Filebrowser or the Orchestrator dashboard.                                         |
| **Shared Volumes**      | Docker volumes (`filebrowser-data`, `filebrowser-database`, `filebrowser-config`) persisting uploads, users, and settings across rotations. |

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
  ┌─────────────────┐            ┌────────────────────┐
  │  Orchestrator   │            │    Filebrowser     │
  │   (dashboard)   │            │ (dynamic rotation) │
  └─────────────────┘            └────────────────────┘
```

---

## Prerequisites 🧰

- Docker Engine + Compose plugin
- Git
- `sudo` privileges for installation
- Ability to create system users and assign them to the `docker` group (the installer provisions a dedicated `leyzen` account).

---

## Installation 🧭

Clone the repository and bootstrap the Docker services:

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
```

Review `.env` before the first launch and set strong secrets. Then start the full stack using the helper script:

```bash
./service.sh start
```

> 💡 **If you’re testing the stack over plain HTTP (`http://localhost:8080`)**: set `VAULT_SESSION_COOKIE_SECURE=false` in your `.env` file (see the documented block in [`.env`/`env.template`](env.template)). Without this setting, the session cookie’s `Secure` attribute prevents it from being sent without TLS, causing a login loop.

If the stack is managed through `systemd`, run the installer to provision the service unit:

```bash
sudo ./install.sh
sudo systemctl enable --now leyzen.service
```

The installer provisions a dedicated `leyzen` system user and adds it to the `docker` group so the service can interact with the Docker Engine without running as `root`. Ensure the `docker` group exists (it is created automatically by Docker packages) and that your administrator account can manage group membership.

> ⚠️ **Security reminder:** Set `FILEBROWSER_ADMIN_PASSWORD` to a long, random value and rotate it regularly.

---

## Configuration 🧪

### Environment variables

Environment variables are loaded from `.env`. Restrict the file’s permissions (for example, `chmod 600 .env`) and keep it out of shared locations to prevent credential leakage. Key entries include:

- `VAULT_USER` / `VAULT_PASS` — dashboard credentials; never commit real values.
- `VAULT_SECRET_KEY` — Flask secret key (use `openssl rand -hex 32`).
- `FILEBROWSER_ADMIN_USER` / `FILEBROWSER_ADMIN_PASSWORD` — Filebrowser administrator credentials.
- `VAULT_ROTATION_INTERVAL` — rotation interval (seconds) for backend containers.
- `VAULT_SESSION_COOKIE_SECURE` — mark orchestrator session cookies as `Secure` when HTTPS terminates upstream (enabled by default).
- `VAULT_SERVICE` — selects the active web stack plugin (`filebrowser`, `paperless`, or custom implementations under `vault_plugins/`).
- `VAULT_WEB_REPLICAS` — desired number of front-end replicas for the active plugin; values below the plugin minimum are automatically clamped.
- `VAULT_WEB_CONTAINERS` — optional comma-separated override for the rotation allowlist; when omitted the orchestrator derives the list from `VAULT_SERVICE`.
- `DOCKER_PROXY_URL` and `DOCKER_PROXY_TOKEN` — access details for the secured Docker proxy.
- `PROXY_TRUST_COUNT` — number of upstream proxies whose forwarded headers should be trusted (`0` when serving requests directly, `1` when HAProxy fronts the stack); see [`env.template`](env.template) for additional guidance.

Consult [`env.template`](env.template) for the full list and documentation of supported variables. When provisioning the optional systemd unit via `install.sh`, the installer automatically enforces the restrictive `.env` permissions so service deployments stay aligned with these recommendations.

### Docker resources

The generated `docker-compose.generated.yml` manifest declares the volumes required by the active plugin. For the default Filebrowser stack ensure the Docker daemon user can access:

- `filebrowser-data`
- `filebrowser-database`
- `filebrowser-config`

When switching to the Paperless plugin the following additional volumes are created for its Postgres/Redis dependencies:

- `paperless-postgres`
- `paperless-redis`
- `paperless-data`
- `paperless-media`
- `paperless-export`

### Service plugins

Leyzen Vault’s web layer is now delivered through dynamically discovered plugins under [`vault_plugins/`](vault_plugins/). The helper script invokes [`compose/build.py`](compose/build.py) before every lifecycle action to generate `docker-compose.generated.yml`, merge the base stack with the selected plugin, and populate dependency allowlists for the orchestrator and Docker proxy. Set `VAULT_SERVICE` in `.env` (default: `filebrowser`) to switch stacks; `paperless` provisions Paperless-ngx along with Redis and Postgres sidecars. Additional plugins can be added by dropping a `vault_plugins/<name>/plugin.py` module that subclasses `VaultServicePlugin`. Each plugin exposes its web-facing container names through `get_containers()` so the orchestrator can rotate them automatically, and honours `VAULT_WEB_REPLICAS` to scale the number of front-end clones (subject to plugin-specific minimums).

---

## Usage 🛠️

The `service.sh` helper centralizes day-to-day operations:

```bash
./service.sh start    # Launch all containers in detached mode
./service.sh stop     # Stop and remove running containers (volumes are preserved)
./service.sh build    # Rebuild images and restart the stack
./service.sh restart  # Stop then start the stack again
./service.sh status   # Display container states and exposed ports
```

To manage the optional systemd unit:

```bash
sudo systemctl status leyzen.service      # Inspect service health
journalctl -u leyzen.service -f           # Follow live logs
```

---

## Security 🔐

Leyzen Vault ships with layered safeguards intended to shrink the attack surface while keeping the demo stack operable:

- **Browser protections** — The orchestrator templates enforce a locked-down Content Security Policy (CSP) and embed CSRF tokens so that authenticated actions cannot be replayed from foreign origins.
- **Abuse defenses** — Login flows require CAPTCHA completion and throttle repeated attempts, limiting credential stuffing windows.
- **Network isolation** — Administrative Docker operations are gated behind the separate [`docker-proxy`](docker-proxy) service, ensuring the Docker socket is never exposed directly to end users.
- **Secrets hygiene** — All credentials and API tokens reside in a local `.env` file with restrictive permissions (`chmod 600 .env` recommended) and must be provisioned before first launch.

Operationally critical settings include:

- `VAULT_SESSION_COOKIE_SECURE` — Keep this enabled in production so session cookies are transmitted only over HTTPS; disable temporarily **only** for local HTTP testing.
- `DOCKER_PROXY_TOKEN` — Rotate the proxy bearer token regularly and update any automation that references it.
- `.env` permissions — Ensure only the service account (and trusted administrators) can read secrets by locking down the file system access bits.

For a deeper walkthrough of the threat model and mitigations, consult the dedicated [Security Policy](SECURITY.md) and extended [Technical Guide](docs/TECHNICAL_GUIDE.md).

---

## Service Endpoints 🌐

| Service                          | URL / Port                                                               | Description                                                                     |
| -------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| **HAProxy**                      | `:8080`                                                                  | Routes to Filebrowser and Orchestrator                                          |
| **Docker Proxy**                 | internal (`docker-proxy:2375`)                                           | Mediates container lifecycle calls                                              |
| **Active web service**           | [http://localhost:8080/](http://localhost:8080/)                         | Filebrowser UI by default; switches to Paperless when `VAULT_SERVICE=paperless` |
| **Vault Orchestrator Dashboard** | [http://localhost:8080/orchestrator](http://localhost:8080/orchestrator) | Real-time monitoring and control                                                |

---

## Further Documentation 📚

For operational procedures, security controls, and advanced configuration, see the [Technical Guide](docs/TECHNICAL_GUIDE.md).

---

## License 📄

This project is distributed under the [Business Source License 1.1](LICENSE). Until the change date of **2030-01-01**, the Additional Use Grant permits personal, educational, and non-commercial internal use; other uses require a commercial license. On the change date, the code automatically converts to **AGPLv3**. For more context, consult the [BSL FAQ](https://mariadb.com/bsl-faq/).
Notices for bundled third-party assets are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

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

Leyzen Vault is an evolving demonstrator exploring automated ephemeral backends, dynamic routing, and autonomous cyber defense patterns.

Automated GitHub Actions CI runs [`python -m compileall orchestrator docker-proxy`](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml) on every push and pull request to catch syntax issues early in both Python services.

---

## Credits 👤

**Author:** Saad Idrissi  
**Concept:** Disposable Compute — _Infrastructure as a Disposable Service_

---

> © 2025 Saad Idrissi — Licensed under the Business Source License 1.1.
