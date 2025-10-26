# Leyzen Vault ⚙️

> **Dynamic Moving-Target Infrastructure — Proof of Concept**
>
> A self-rotating, self-healing environment built to demonstrate _ephemeral compute security_ through automated container polymorphism.

---

## Overview 🧩

Leyzen Vault is a **proof-of-concept for moving-target defense**, applying infrastructure polymorphism to containerized applications. The orchestrator continuously rotates _Filebrowser_ backends while maintaining a seamless user experience. Each container’s lifecycle is ephemeral — born, used, and destroyed — minimizing the attack persistence window.

---

## Core Components ⚙️

| Component               | Description                                                                                         |
| ----------------------- | --------------------------------------------------------------------------------------------------- |
| **Vault Orchestrator**  | Python-based orchestrator handling container rotation, metrics, and dashboard rendering.            |
| **Filebrowser Cluster** | Trio of lightweight file-manager containers rotated polymorphically.                                |
| **HAProxy**             | Reverse proxy exposed on port **8080**, routing users to Filebrowser or the Orchestrator dashboard. |
| **Shared Volume**       | Single Docker volume (`filebrowser-data`) ensuring persistent user files across rotations.          |

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

- Entirely sandboxed within a **Docker bridge network** — only HAProxy is exposed.
- Health checks ensure uptime and auto-recovery.
- The **Python Orchestrator** performs randomized rotation cycles.
- **Shared volume** (`filebrowser-data:/srv`) preserves Filebrowser uploads between container lifespans.
- Filebrowser runs without external databases or caches, simplifying the demo stack.
- Container lifecycle commands flow through the secured `docker-proxy` API (`DOCKER_PROXY_URL`), replacing direct socket mounts.

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
