# Leyzen Vault Security Policy

Leyzen Vault is a modular moving-target defense orchestrator. We take the security of the platform and of downstream
operators seriously and appreciate responsible disclosures.

## Supported Versions

The `main` branch and the most recent tagged release receive security patches. Older tags and forks may remain available
for reference but do not receive fixes. When in doubt, upgrade to the latest release before requesting support.

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

## Additional Reading

For runtime hardening details, see [`orchestrator/SECURITY_RUNTIME.md`](orchestrator/SECURITY_RUNTIME.md). Operational practices and CLI usage
are documented in the [Quickstart](https://github.com/3xpyth0n/leyzen-vault/wiki/Quickstart) and [`leyzenctl`](https://github.com/3xpyth0n/leyzen-vault/wiki/leyzenctl) wiki pages.
