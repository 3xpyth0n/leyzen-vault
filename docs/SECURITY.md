# Leyzen Vault Security Policy

Leyzen Vault is a modular moving-target defense orchestrator. We take the security of the platform and of downstream
operators seriously and appreciate responsible disclosures.

## Supported Versions

The `main` branch and tagged releases receive security patches. When in doubt, upgrade to the latest release before requesting support.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately using one of the channels below:

- [GitHub Security Advisories](https://github.com/3xpyth0n/leyzen-vault/security/advisories/new) — preferred for providing
  encrypted communication and tracking remediation.

Please do not open public GitHub issues, pull requests, or discussions for security reports. We will coordinate with you on
fix timelines and public disclosure after a mitigation is available.

## What to Include

To help us triage quickly, share:

- A description of the issue and the potential impact.
- Steps to reproduce, including the `./leyzenctl` commands or configuration used.
- Any logs, stack traces, or proof-of-concept exploits that demonstrate the vulnerability.

## Response Expectations

- **Acknowledgement:** Within 2 business days of receiving your report.
- **Initial assessment:** Within 5 business days. We may contact you for additional information or reproduction steps.
- **Fix or mitigation:** Targeted within 30 days for high-impact issues and 90 days for lower-severity findings.

We will keep you informed of our progress and coordinate disclosure once a fix or mitigation is ready.

## Automated Security Scanning

We use automated secret scanning in our CI/CD pipeline to detect accidentally committed credentials, API keys, and other sensitive information. The CI workflow runs [TruffleHog](https://github.com/trufflesecurity/trufflehog) on every push and pull request to scan the repository for potential secrets.

Contributors should never commit secrets, tokens, or credentials to the repository. Use the `.env` file for local development (which is excluded from version control via `.gitignore`) and environment variables or secure secret management systems for deployments.

## Secret Rotation

Regular rotation of secrets, tokens, and passwords is essential for maintaining the security posture of Leyzen Vault deployments. This section outlines recommended rotation procedures for all secrets managed by the platform.

### Core Secrets

#### VAULT_PASS (Dashboard Password)

The orchestrator dashboard password should be rotated periodically (recommended: every 90 days).

**Rotation procedure:**

1. Generate a new strong password using a secure method: `openssl rand -base64 32` or a password manager
2. Update `VAULT_PASS` in your `.env` file with the new value
3. Restart the orchestrator service: `./leyzenctl restart`
4. Verify you can log in with the new password
5. Securely destroy the old password

**Impact:** Brief service interruption during restart. Existing sessions may be invalidated.

#### SECRET_KEY (Flask Session Encryption Key)

The Flask secret key is used for session encryption and CSRF token generation. Rotate this key quarterly (recommended: every 90 days).

**Rotation procedure:**

1. Generate a new secret key: `openssl rand -hex 32`
2. Update `SECRET_KEY` in your `.env` file
3. Restart the orchestrator: `./leyzenctl restart`
4. Verify authentication still works

**Impact:** All existing user sessions will be invalidated. Users will need to log in again.

#### DOCKER_PROXY_TOKEN (Docker Proxy Authentication Token)

The token used to authenticate requests between the orchestrator and docker-proxy service. Rotate this key quarterly (recommended: every 90 days).

**Rotation procedure:**

1. Generate a new token: `openssl rand -hex 32`
2. Update `DOCKER_PROXY_TOKEN` in your `.env` file
3. Restart both services: `./leyzenctl restart`
4. Verify container operations still function correctly from the dashboard

**Impact:** Brief interruption in container operations during restart. Ensure the orchestrator and docker-proxy restart in sequence to avoid authentication failures.

### Rotation Best Practices

1. **Schedule rotations:** Set calendar reminders for regular secret rotation cycles
2. **Rotate after incidents:** Immediately rotate all secrets if you suspect a breach or credential leak
3. **Rotate personnel changes:** Rotate secrets when team members with access leave the organization
4. **Document rotations:** Maintain a log (outside the repository) of when secrets were last rotated
5. **Test after rotation:** Always verify that services function correctly after rotating secrets
6. **Stagger rotations:** Avoid rotating all secrets simultaneously to reduce the risk of service disruption

### Emergency Rotation

If you suspect a security incident or credential compromise:

1. Immediately rotate all secrets listed above
2. Review access logs in the orchestrator dashboard for suspicious activity
3. Verify that no unauthorized containers have been created or modified
4. Consider regenerating the entire `.env` file if the breach scope is unknown
5. Report the incident following the vulnerability reporting process in this document

## Additional Reading

For runtime hardening details, see [`docs/SECURITY_RUNTIME.md`](SECURITY_RUNTIME.md). Operational practices and CLI usage
are documented in the [Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart) and [`leyzenctl`](https://github.com/3xpyth0n/leyzen-vault/wiki/leyzenctl) wiki pages.
