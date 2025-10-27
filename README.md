# Leyzen Vault ⚙️

> **Dynamic Moving-Target Infrastructure — Proof of Concept**
>
> A self-rotating, self-healing environment built to demonstrate _ephemeral compute security_ through automated container polymorphism.

---

## Overview 🧩

Leyzen Vault is a **proof-of-concept for moving-target defense**, applying infrastructure polymorphism to containerized applications. The orchestrator continuously rotates _Filebrowser_ backends while maintaining a seamless user experience. Each container’s lifecycle is ephemeral — born, used, and destroyed — minimizing the attack persistence window.

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

---

## Quick Start 🚀

Clone and install in **3 commands**:

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
sudo ./install.sh
```

Check service status:

```bash
sudo systemctl status leyzen.service
```

Follow live logs:

```bash
journalctl -u leyzen.service -f
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

## Operations 🔄

- Network isolation uses two dedicated bridges: `vault-net` (user-facing services) and `control-net` (docker-proxy control plane). Only HAProxy is exposed publicly.
- Health checks ensure uptime and auto-recovery.
- The **Python Orchestrator** performs randomized rotation cycles.
- **Shared volumes** (`filebrowser-data:/srv`, `filebrowser-database:/database`, `filebrowser-config:/config`) preserve Filebrowser uploads, user accounts, and configuration between container lifespans.
- Filebrowser runs without external databases or caches, simplifying the demo stack.
- Container lifecycle commands flow through the secured `docker-proxy` API (`DOCKER_PROXY_URL`) with a rotating `DOCKER_PROXY_TOKEN`, replacing direct socket mounts.

---

## Control Plane Security 🔐

- `docker-proxy` is attached exclusively to the internal `control-net` bridge. Other services cannot reach the Docker socket unless they are explicitly joined to that network.
- `orchestrator` is dual-homed (`vault-net` + `control-net`) so it can expose the dashboard while still reaching the proxy for lifecycle actions.
- Every proxy call includes the `Authorization: Bearer <DOCKER_PROXY_TOKEN>` header. Rotate this token routinely:
  1. Generate a fresh random string (for example with `openssl rand -hex 32`).
  2. Update the value of `DOCKER_PROXY_TOKEN` in your local `.env` file.
  3. Reload the stack (`docker compose up -d orchestrator docker-proxy`).
  4. Revoke the old token wherever it was stored.

---

## Design Highlights 💡

✅ **Moving Target Defense:** Containers are continuously replaced to prevent persistence attacks.  
✅ **Resilience:** The service remains operational even during rotations.  
✅ **Observability:** `/orchestrator` provides full visibility into states, logs, and uptime metrics.  
✅ **Isolation:** Only HAProxy touches the host network, minimizing the exposed surface.

---

## Project Status 📊

Leyzen Vault is an evolving demonstrator exploring automated ephemeral backends, dynamic routing, and autonomous cyber defense patterns.

---

## Credits 👤

**Author:** Saad Idrissi  
**Concept:** Disposable Compute — _Infrastructure as a Disposable Service_

---

> © 2025 Saad Idrissi — All rights reserved.
