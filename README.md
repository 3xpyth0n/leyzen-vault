# Leyzen Vault ⚙️

> **Dynamic Moving-Target Infrastructure — Proof of Concept**
>
> Licensed under the **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE) for details.
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

Clone, configure your secrets, then install:

```bash
git clone git@github.com:3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
nano .env
sudo ./install.sh
```

> ⚠️ **Security**: Set `FILEBROWSER_ADMIN_PASSWORD` to long, random value and renew it regularly.

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

## Design Highlights 💡

✅ **Moving Target Defense:** Containers are continuously replaced to prevent persistence attacks.
✅ **Resilience:** The service remains operational even during rotations.
✅ **Observability:** `/orchestrator` provides full visibility into states, logs, and uptime metrics.
✅ **Isolation:** Only HAProxy touches the host network, minimizing the exposed surface.

---

## Further Documentation 📚

For operational procedures, security controls, and advanced configuration, see the [Technical Guide](docs/TECHNICAL_GUIDE.md).

---

## Project Status 📊

Leyzen Vault is an evolving demonstrator exploring automated ephemeral backends, dynamic routing, and autonomous cyber defense patterns.

---

## Credits 👤

**Author:** Saad Idrissi  
**Concept:** Disposable Compute — _Infrastructure as a Disposable Service_

---

> © 2025 Saad Idrissi — Licensed under the Business Source License 1.1.
