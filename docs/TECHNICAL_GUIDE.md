# Leyzen Vault Technical Guide

This document covers operational procedures, security controls, and advanced configuration for the Leyzen Vault proof-of-concept. Use it as a companion to the high-level overview in the main README.

## Operations

- Network isolation uses two dedicated bridges: `vault-net` (user-facing services) and `control-net` (docker-proxy control plane). Only HAProxy is exposed publicly.
- Health checks ensure uptime and auto-recovery.
- The **Python Orchestrator** performs randomized rotation cycles.
- **Service plugins** under [`vault_plugins/`](../vault_plugins/) define the web workload that HAProxy exposes. Filebrowser remains the default plugin, while the Paperless plugin extends the stack with Redis and Postgres sidecars.
- **Shared volumes** are provisioned per plugin. Filebrowser mounts `filebrowser-data`, `filebrowser-database`, and `filebrowser-config`; Paperless adds `paperless-data`, `paperless-media`, `paperless-export`, `paperless-postgres`, and `paperless-redis`.
- When updating the Filebrowser binary (bumping `FILEBROWSER_VERSION` in `filebrowser/Dockerfile`), the Docker build automatically retrieves the matching checksum from the upstream `filebrowser_<version>_checksums.txt` manifest, so no manual refresh is required.
- Container lifecycle commands flow through the secured `docker-proxy` API (`DOCKER_PROXY_URL`) with a rotating `DOCKER_PROXY_TOKEN`, replacing direct socket mounts.

## Control Plane Security

- `docker-proxy` is attached exclusively to the internal `control-net` bridge. Other services cannot reach the Docker socket unless they are explicitly joined to that network.
- `orchestrator` is dual-homed (`vault-net` + `control-net`) so it can expose the dashboard while still reaching the proxy for lifecycle actions.
- Client IP attribution is mediated by Werkzeug's `ProxyFix`. Keep `PROXY_TRUST_COUNT=1` (default) when HAProxy fronts the stack, and switch to `0` if clients hit the orchestrator directly without a proxy.
- HAProxy forwards the original `X-Forwarded-For` chain when provided, sets `X-Forwarded-Proto` for TLS frontends, and only applies HSTS when traffic arrived over HTTPS, keeping plaintext development workflows unaffected.
- Every proxy call includes the `Authorization: Bearer <DOCKER_PROXY_TOKEN>` header. Rotate this token routinely:
  1. Generate a fresh random string (for example with `openssl rand -hex 32`).
  2. Update the value of `DOCKER_PROXY_TOKEN` in your local `.env` file.
  3. Reload the stack (`docker compose up -d orchestrator docker-proxy`).
  4. Revoke the old token wherever it was stored.
- The Docker proxy enforces an explicit container allowlist before any request reaches the Docker socket. The compose builder injects the plugin’s container names by default; set `VAULT_WEB_CONTAINERS` manually only when you need to override the plugin-provided list.

### CSP reporting endpoint protection

- `CSP_REPORT_MAX_SIZE` (default `4096`) rejects oversized Content Security Policy violation reports with HTTP 413 **before** the orchestrator reads the payload.
- `CSP_REPORT_RATE_LIMIT` (default `5`) caps accepted CSP reports per client IP over a rolling 60-second window; further requests receive HTTP 429.
- Browsers capable of the Reporting API are instructed to use the same endpoint via `Report-To`, in addition to the legacy `report-uri`, so CSP telemetry lands at `/orchestrator/csp-violation-report-endpoint` regardless of browser support.

## Secret scanning & credential hygiene

- Run comprehensive secret scans before shipping changes:
  - `trufflehog --json --regex .` to sweep repository history for high-entropy strings and credential patterns.
  - `git secrets --scan` to lint the working tree against common AWS and generic secret signatures.
  - Targeted ripgrep checks (`rg "SECRET"`, `rg "PASSWORD"`, `rg "TOKEN"`) to spot hard-coded configuration values.
- The latest audit (see repository history) reported only high-entropy false positives from the minified vendor bundles (`orchestrator/static/js/vendor/chart.umd.min.js`, `chartjs-plugin-streaming.min.js`, `chartjs-adapter-luxon.min.js`, `echarts.min.js`, `luxon.min.js`) and the `orchestrator/package-lock.json` lockfile; no actionable credentials were identified.
- Keep the committed `env.template` free of real values. Populate secrets solely in the untracked `.env` file and rotate them regularly.

## Plugin architecture

- [`compose/build.py`](../compose/build.py) merges the static HAProxy/orchestrator/docker-proxy stack with the active service plugin and writes `docker-compose.generated.yml`. `service.sh` runs this builder automatically before `start`, `stop`, `build`, or `restart` operations.
- Plugins live under [`vault_plugins/`](../vault_plugins/) and must provide a `plugin.py` module exporting a subclass of `VaultServicePlugin`. The orchestrator and compose builder load plugins via `pkgutil.walk_packages`, so new stacks can be added without touching the base code.
- Each plugin implements `build_compose(env)` to declare its Docker services and `get_containers()` to expose the names eligible for rotation. Optional `dependencies` ensure supporting services (for example Postgres/Redis) appear ahead of the base stack in the generated manifest. `VAULT_WEB_REPLICAS` controls the number of web clones instantiated for the active plugin, clamped to plugin-defined minimums to preserve rotation guarantees.
- Set `VAULT_SERVICE` in `.env` to choose the plugin at runtime (`filebrowser` by default, `paperless` for Paperless-ngx). When unset, the registry falls back to Filebrowser for backward compatibility.
