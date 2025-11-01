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

Environment variables are loaded from `.env`. Key entries include:

- `VAULT_USER` / `VAULT_PASS` — dashboard credentials; never commit real values.
- `VAULT_SECRET_KEY` — Flask secret key (use `openssl rand -hex 32`).
- `FILEBROWSER_ADMIN_USER` / `FILEBROWSER_ADMIN_PASSWORD` — Filebrowser administrator credentials.
- `VAULT_ROTATION_INTERVAL` — rotation interval (seconds) for backend containers.
- `VAULT_SESSION_COOKIE_SECURE` — mark orchestrator session cookies as `Secure` when HTTPS terminates upstream (enabled by default).
- `VAULT_WEB_CONTAINERS` — comma-separated list of containers eligible for rotation.
- `DOCKER_PROXY_URL` and `DOCKER_PROXY_TOKEN` — access details for the secured Docker proxy.

Consult [`env.template`](env.template) for the full list and documentation of supported variables.

### Docker resources

The stack relies on Docker volumes declared in `docker-compose.yml` for Filebrowser data persistence. Ensure the Docker daemon user can access:

- `filebrowser-data`
- `filebrowser-database`
- `filebrowser-config`

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

## Service Endpoints 🌐

| Service                          | URL / Port                                                               | Description                            |
| -------------------------------- | ------------------------------------------------------------------------ | -------------------------------------- |
| **HAProxy**                      | `:8080`                                                                  | Routes to Filebrowser and Orchestrator |
| **Docker Proxy**                 | internal (`docker-proxy:2375`)                                           | Mediates container lifecycle calls     |
| **Filebrowser**                  | [http://localhost:8080/](http://localhost:8080/)                         | File management UI                     |
| **Vault Orchestrator Dashboard** | [http://localhost:8080/orchestrator](http://localhost:8080/orchestrator) | Real-time monitoring and control       |

---

## Further Documentation 📚

For operational procedures, security controls, and advanced configuration, see the [Technical Guide](docs/TECHNICAL_GUIDE.md).

---

## License 📄

This project is distributed under the [Business Source License 1.1](LICENSE). Usage terms and the conversion date to an open-source license are detailed in the license file.
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
