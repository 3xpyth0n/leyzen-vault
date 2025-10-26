# Leyzen Vault ⚙️

> **Dynamic Moving-Target Infrastructure — Proof of Concept**
>
> A self-rotating, self-healing environment built to demonstrate _ephemeral compute security_ through automated container polymorphism.

---

## 📖 Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Reference Architecture](#reference-architecture)
4. [Prerequisites](#prerequisites)
5. [Quick Start](#quick-start)
6. [Service Endpoints](#service-endpoints)
7. [Operations](#operations)
8. [Design Highlights](#design-highlights)
9. [Project Status](#project-status)
10. [Credits](#credits)

---

## Overview 🧩

Leyzen Vault is a **proof-of-concept for moving-target defense**, applying infrastructure polymorphism to containerized applications. The orchestrator continuously rotates _Paperless-ngx_ backends while maintaining a seamless user experience. Each container’s lifecycle is ephemeral — born, used, and destroyed — minimizing the attack persistence window.

---

## Core Components ⚙️

| Component                 | Description                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Vault Orchestrator**    | Python-based orchestrator handling container rotation, metrics, and dashboard rendering.          |
| **Paperless-ngx Cluster** | Trio of document management containers rotated polymorphically.                                   |
| **HAProxy**               | Reverse proxy exposed on port **8080**, routing users to Paperless or the Orchestrator dashboard. |
| **Redis & PostgreSQL**    | Persistent backends for Paperless-ngx.                                                            |
| **Shared Volumes**        | Docker volumes ensuring persistent user data and media across rotations.                          |

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
  │  Orchestrator   │            │   Paperless-ngx    │
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

| Service                          | URL / Port                                                               | Description                          |
| -------------------------------- | ------------------------------------------------------------------------ | ------------------------------------ |
| **HAProxy**                      | `:8080`                                                                  | Routes to Paperless and Orchestrator |
| **Paperless-ngx**                | [http://localhost:8080/](http://localhost:8080/)                         | Document management UI               |
| **Vault Orchestrator Dashboard** | [http://localhost:8080/orchestrator](http://localhost:8080/orchestrator) | Real-time monitoring and control     |
| **Redis**                        | `6379`                                                                   | Used internally by Paperless         |
| **PostgreSQL**                   | `5432`                                                                   | Used internally by Paperless         |

---

## Operations 🔄

- Entirely sandboxed within a **Docker bridge network** — only HAProxy is exposed.
- Health checks ensure uptime and auto-recovery.
- The **Python Orchestrator** performs randomized rotation cycles.
- **Shared volumes** preserve Paperless data between container lifespans.

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
