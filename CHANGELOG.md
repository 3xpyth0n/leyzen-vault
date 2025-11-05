# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.0.0] - 2025-11-05

## Initial Release

This is the first official release of Leyzen Vault (Initial Release). Leyzen Vault is a modular moving-target defense orchestrator that automates ephemeral container rotation for a secure file storage system.

This initial release includes:

- End-to-end encryption (E2EE) with client-side encryption using Web Crypto API
- Dynamic stack composition with Docker Compose and HAProxy artifact generation
- Rotation-aware control plane with SSE telemetry
- Defense-in-depth defaults with CAPTCHA authentication, CSP reporting, and proxy trust limits
- Hardened Flask orchestrator with Docker lifecycle coordination
- HAProxy front-end with strict security headers

Licensed under the Business Source License 1.1 (BSL 1.1).
