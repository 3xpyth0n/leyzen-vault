<p align="center">
  <img src="https://leyzen.com/images/vault-text-logo.png" alt="Leyzen Vault logo" height="30" /> 
</p>
<p align="center">
  <i>A secure alternative to traditional cloud storage, for people who hate configuring cloud storage.</i>
  <br/>
  <img width="1640" style="border-radius: 12px;" alt="Vault dashboard" src="https://leyzen.com/images/vault-dashboard.png">
</p>
<p align="center">
  <a href="https://github.com/prettier/prettier">
    <img src="https://img.shields.io/badge/code_style-prettier-ff69b4.svg" alt="Prettier">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml">
    <img src="https://github.com/3xpyth0n/leyzen-vault/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/issues">
    <img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg" alt="Contributions welcome">
  </a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/commits/main">
  <img src="https://img.shields.io/github/last-commit/3xpyth0n/leyzen-vault" alt="Last commit">
</a>
  <a href="https://github.com/3xpyth0n/leyzen-vault/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-BSL--1.1-0A7AA6" alt="License">
  </a>
</p>

## Overview

Leyzen Vault is a self-hosted, end-to-end encrypted file storage solution. We built it because we wanted security, but we also really, really hate spending our weekends configuring servers.

## Requirements

**Only Docker**. If you can run containers, you can run Leyzen Vault.

## 1. Deployment for the Laziest Among Us

Let's be honest: you don't want to edit `.env` files. You don't want to generate secrets manually. You just want it to work.

We get it. That's why we automated the boring work for you. FYI: you don't have to touch your _.env_.

**Clone. Install. Run.**

```bash
git clone https://github.com/3xpyth0n/leyzen-vault.git
cd leyzen-vault
./install.sh
```

### Configuration

If you insist on changing something, please don't open a text editor,
Use the CLI, typing one line is faster than finding a config file, for example :

```bash
./leyzenctl config set SMTP_HOST mx1.mycompany.com
```

Don't know what a variable does? Don't open the documentation. Just ask:

```bash
./leyzenctl config explain
```

## 2. Integrated HAProxy

We included a custom, pre-configured HAProxy container to simplify deployment:

- **Single Entry Point**: Acts as the sole gateway for your cluster, handling **TLS termination** and isolating backend services from direct internet exposure.
- **No Manual Config**: Replaces the need for an external reverse proxy like Nginx. It configures itself automatically based on your environment.
- **Environment Driven**: Change ports or enable SSL directly via the CLI, without editing complex configuration files.

## 3. Moving Target Defense (Experimental)

We are actively exploring **Moving Target Defense (MTD)**. This strategy involves rotating backend containers periodically to limit the attack surface.

- **Objective**: By constantly shifting the infrastructure, we aim to **limit attacker dwell time** and prevent persistence. It makes it significantly harder for threats to establish a foothold.

This feature is opt-in for those who want to test proactive defense strategies. If you enable it, please **share your feedback**. We are refining this technology to make it a standard "set and forget" security layer.

## Documentation

For when you actually want to read things:
[docs.leyzen.com](https://docs.leyzen.com)

## Contributing

Found a bug? Have a lazy idea? Contributions are welcome! We love code that makes our lives easier.

## License

It's under the Business Source License 1.1 (BSL 1.1).
Check the [`LICENSE`](LICENSE) file for more info.
