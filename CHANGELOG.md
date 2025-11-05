# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **Credentials validation**: Added `LEYZEN_ENVIRONMENT` variable to enforce rejection of default credentials (`admin/admin`) in production mode
- **Rate limiting**: Fixed unlimited uploads for unknown IPs by applying conservative default limit (10 uploads/hour)
- **XSS prevention**: Implemented HTML escaping for all user-supplied data in client-side JavaScript (`files.js`, `security.js`)
- **Hardcoded secrets**: Removed all hardcoded secrets from fallback settings, now requires environment variables
- **File upload validation**: Added strict filename validation with whitelist approach to prevent path traversal attacks
- **Audit log rotation**: Implemented automatic cleanup of audit logs older than retention period (configurable via `VAULT_AUDIT_RETENTION_DAYS`, default: 90 days)
- **CSP improvements**: Enhanced Content Security Policy with `require-trusted-types-for 'script'` and CSP violation reporting to orchestrator
- **Configuration validation**: Added security checklist in `env.template` and validation script `tools/validate-env.py`

### Fixed

- Fixed CLI validation (`leyzenctl config validate`):
  - Removed incorrect deprecation warning for CSP variables (`CSP_REPORT_MAX_SIZE` and `CSP_REPORT_RATE_LIMIT` which are the correct variables used in the code)
  - Fixed required variable `VAULT_SECRET_KEY` → `SECRET_KEY` to match the actual Python code
  - Added missing required variables `ORCH_USER` and `ORCH_PASS` for the orchestrator
  - Fixed cryptographic secrets detection pattern to use `SECRET_KEY` instead of `VAULT_SECRET_KEY`

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
