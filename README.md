# Leyzen Vault 🛰️

**Version 2.4.0**

[![CI](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-0A7AA6)](https://github.com/3xpyth0n/leyzen-vault/blob/main/LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](https://github.com/3xpyth0n/leyzen-vault/issues)

> **Modular Moving-Target Defense Orchestrator - Enterprise-Grade Secure File Storage**  
> **The first open-source file vault designed to stay ahead of attackers - by never standing still.**  
> Licensed under **Business Source License 1.1 (BSL 1.1)**. See [`LICENSE`](LICENSE).

## Version 2.4.0 Highlights

**Unlock Enterprise-Grade Storage Flexibility and Mobile Excellence**

Leyzen Vault 2.4.0 introduces three game-changing features that transform how you store, protect, and access your encrypted files:

### 🌐 S3-Compatible External Storage Integration

Break free from local storage limitations with native support for AWS S3, MinIO, and any S3-compatible service. Seamlessly synchronize your encrypted files bidirectionally between local storage and cloud infrastructure, enabling true hybrid deployments. Configure everything securely through the intuitive admin interface-your credentials are encrypted and stored safely. Whether you need cloud redundancy, distributed storage, or complete cloud-based deployments, Leyzen Vault now scales with your infrastructure needs while maintaining end-to-end encryption.

### 💾 Encrypted Database Backup & Restore System

Never lose your critical data again. Leyzen Vault 2.4.0 includes a comprehensive backup solution that protects your entire database with the same military-grade Argon2id encryption used for your files. Schedule automated backups with flexible cron-based scheduling, store them locally or in S3-compatible storage, and restore your entire system in one click directly from the setup page. All backups remain encrypted at rest-because security shouldn't be an afterthought, even for backups. Configure retention policies to automatically manage your backup history, keeping storage clean while preserving essential recovery points.

### 📱 Revolutionary Mobile Mode

Experience Leyzen Vault like never before on mobile devices. Our brand-new mobile-optimized interface features a sleek bottom navigation bar, responsive single-column layouts, and touch-optimized interactions designed specifically for small screens. Toggle between mobile and desktop modes with a single tap, giving you the perfect experience on any device. Every screen has been reimagined for mobile-from file browsing to sharing, everything feels natural and intuitive on your phone or tablet. Your encrypted files, now in your pocket.

**End-to-End Encryption (E2EE)**: All features maintain our zero-trust security model. Files are encrypted client-side using the Web Crypto API (AES-GCM) before being uploaded. The server only stores ciphertext.

See [`CHANGELOG.md`](CHANGELOG.md) for full release notes.

## Overview

Leyzen Vault is a **next-generation secure file storage platform** built around a fully automated **Moving-Target Defense (MTD)** model.
Instead of relying on static, predictable infrastructures, it continuously rotates its backend containers, refreshes surface exposure, and isolates components - making targeted attacks dramatically harder.

It combines:

- a hardened Python orchestrator,
- a Go-based CLI,
- a Vue.js interface with modern UX,
- HAProxy security-focused ingress,
- full client-side E2EE.

This project aims to **bridge real-world usability and advanced cybersecurity research**, offering an infrastructure that is understandable to operators yet significantly more resilient than traditional file storage solutions.

## What Leyzen Vault Is For

Leyzen Vault is designed for:

- individuals and teams needing **confidential, encrypted, and private file storage**,
- security-conscious users wanting **client-side encryption with zero-trust architecture**,
- developers and researchers exploring **practical implementations of moving-target defense**,
- operators looking for a **self-hosted, auditable, enterprise-grade alternative** to mainstream cloud services.

All encryption and decryption happen in the browser - servers never access plaintext.

## Why It Matters

Traditional self-hosted storage solutions, even encrypted ones, rely on static servers and predictable topologies. Attackers can perform recon, prepare exploits, and maintain persistence.

Leyzen Vault breaks this model by providing:

- **ephemeral backends that constantly rotate**,
- **strict proxy boundaries**,
- **hardened service orchestration**,
- **auditable secure defaults**,
- **client-encrypted data only**,
- **zero exposure of keys, even on compromise**.

This significantly reduces the feasibility of long-term intrusion, data exfiltration, and targeted exploitation.

## How Leyzen Vault Differs From Other Solutions

Leyzen Vault is **not** just another file storage tool. It differentiates itself through:

### 1. Moving-Target Defense (MTD) at its core

Most platforms run static containers. Leyzen Vault continuously rotates, regenerates, and re-attests its components.  
Attackers cannot rely on stable targets.

### 2. End-to-End Encryption by design

Files are encrypted with **Web Crypto AES-GCM** before leaving the client.  
Nothing is ever readable server-side.

### 3. Full-stack security alignment

HAProxy, orchestrator, Docker engine access, authentication and proxy boundaries are all designed to minimize trust and reduce attack surface.

### 4. Modular, transparent, and auditable architecture

Each service is isolated, documented, reproducible, and observable - offering a realistic, modern security-oriented reference architecture.

### 5. Enterprise features without vendor lock-in

SSO, audit logs, admin dashboard, device management, and REST API v2 - without subscriptions or proprietary dependencies.

## Author

**Saad Idrissi** - French cybersecurity student passionate about secure systems, automation, and digital defense.  
Creator of **Leyzen Vault**, exploring real-world implementations of MTD concepts.  
🌐 https://portfolio.leyzen.com

## Feature Highlights

### Core Features

- Dynamic stack composition
- Rotation-aware control plane
- Defense-in-depth defaults
- VaultSpaces (workspace-specific keys)

### Enterprise Features

- SSO (SAML, OAuth2, OIDC)
- REST API v2
- Admin dashboard

### Security & Privacy

- PostgreSQL secure metadata storage
- JWT authentication
- Hierarchical key management
- Email verification & device management
- Audit logging with automatic cleanup

## Documentation

### 📚 Official Documentation

https://docs.leyzen.com

Includes Quickstart, Architecture, Security Model, CLI, CI/CD, Developer Guide, FAQ.

### Repository Documentation

Developer & contributor documentation available in `docs/`.

## Getting Started

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
cp env.template .env
./install.sh
./leyzenctl start
```

First-run setup is available at `/setup` until a superadmin is created.

**PostgreSQL Required**: Version 2.0.0 requires PostgreSQL 16 for production deployments.

**Configuration**: You can override the default `.env` file location with `LEYZEN_ENV_FILE`.

## Architecture at a Glance

Leyzen Vault v2.3.0 includes:

- Go CLI
- Flask backend & orchestrator
- Vue.js frontend
- HAProxy reverse proxy
- Docker proxy
- PostgreSQL database

See Architecture section in documentation for diagrams and detailed flow.

## Security & Compliance

Security disclosures follow the process documented in `docs/SECURITY.md`.
Runtime protections include CSP enforcement, captcha, CSRF, trust boundaries, and Docker proxy allowlists.

## Contributing

Contributions are welcome.
Start with the Developer Guide and `docs/CONTRIBUTING.md`.
Please follow the Code of Conduct before submitting.

## Support & Contact

- Issues: [https://github.com/3xpyth0n/leyzen-vault/issues](https://github.com/3xpyth0n/leyzen-vault/issues)
- Security reports: see `docs/SECURITY.md`
- Release history: `CHANGELOG.md`

## Repository Structure

- `src/` - orchestrator, builder, vault backend
- `infra/` - HAProxy, Docker proxy
- `tools/cli/` - `leyzenctl` Go CLI
- `docs/` - developer documentation
- root - generated compose file (do not edit manually)

## Activity

![Alt](https://repobeats.axiom.co/api/embed/dacac14edc54fdcb66274584d1ba09544c99d929.svg "Repobeats analytics image")

## License

Source code is available under the **Business Source License 1.1 (BSL 1.1)**.
