# Leyzen Vault Maintainer Guide

This guide provides maintainers with shared practices for triaging issues, reviewing pull requests, managing releases, and
coordinating the roadmap. It complements the [Operations Guide](OPERATIONS.md) for day-to-day usage and the
[Security Policy](../SECURITY.md) for vulnerability handling.

---

## Issue Triage

- **First response** — Aim to acknowledge new issues within two business days. Thank the reporter and confirm key details
  (`./leyzenctl` commands run, plugin in use, logs, etc.).
- **Labeling** — Apply labels for type (`bug`, `feature`, `documentation`), component (`plugin`, `builder`, `orchestrator`), and
  priority (`P0`–`P2`). Use `needs-info` when reproduction steps or logs are missing.
- **Duplication** — Link related issues and close duplicates with a pointer to the canonical thread.
- **Security reports** — If a public issue appears to contain security-sensitive information, guide the reporter to the private
  channels listed in [SECURITY.md](../SECURITY.md) and redact details if necessary.

Maintain a pinned discussion or issue titled **"🎯 Future Plugins"**. Use it to collect community ideas and track plugin
concepts that are not yet actionable.

---

## Reviewing Pull Requests

1. **Sanity checks** — Confirm the author followed the branch workflow from [CONTRIBUTING.md](../CONTRIBUTING.md) and included the
   testing evidence requested in the pull request template.
2. **Scope** — Ensure the change aligns with the repository roadmap and that documentation updates accompany behavioral changes.
3. **Testing** — Reproduce the author's steps when feasible: run `./leyzenctl build`, `./leyzenctl start`, and inspect generated
   artifacts relevant to the change.
4. **Style and security** — Watch for deviations from coding standards, missing type hints, or changes that bypass security
   mechanisms described in [`orchestrator/SECURITY.md`](../orchestrator/SECURITY.md).
5. **Feedback** — Provide actionable, respectful comments. Request updates via GitHub suggestions or follow-up commits. Use
   `changes requested` only when blocking issues remain.

Approve and merge once all review comments are addressed, status checks pass, and the maintainer performing the merge has
validated the change locally when possible.

---

## Merging Strategy

- Use **squash merges** for community contributions to preserve a clean history that follows the commit message convention.
- Ensure the final squash commit preserves the required four-line body format summarizing context, change, testing, and impact.
- Update labels and milestones to reflect the release version that will include the change.

---

## Release Management

- **Cadence** — Target a minor release every 6–8 weeks or when a significant plugin or orchestrator feature lands.
- **Tagging** — Create annotated tags (`git tag -a vX.Y.Z`) on the `main` branch once CI passes. Include highlights, notable plugin
  updates, and dependency changes in the tag message and release notes.
- **Artifacts** — Regenerate `docker-compose.yml` and `haproxy/haproxy.cfg` using the default plugin to ensure release
  assets reflect current templates.
- **Communication** — Update the README changelog or release notes and link relevant documentation sections (Operations,
  Technical, Developer guides) for users adopting the release.

Maintain the "🎯 Future Plugins" issue by converting delivered ideas into new roadmap milestones or closing them with references
to the implemented plugins.

---

## Security Coordination

- Monitor the inbox for GitHub Security Advisories.
- Establish a private discussion with the reporter to clarify reproduction steps and severity.
- Track remediation work in a private security advisory draft until a fix is merged.
- Coordinate disclosure timing with the reporter and publish an advisory summarizing impact, patched versions, and mitigation
  guidance.

---

## Roadmap and Community Health

- Review open discussions monthly to identify emerging pain points or plugin requests.
- Curate good first issues by tagging approachable bugs or documentation tasks and ensuring they have clear reproduction steps.
- Encourage contributors to update documentation alongside code by referencing this guide in review feedback.

Maintainers set the tone for the community—consistent communication, prompt reviews, and transparent release notes help Leyzen
Vault thrive as a public project.
