# Leyzen Vault Operations Guide

This guide covers daily operations for running Leyzen Vault. All workflows rely on the unified CLI [`service.sh`](../service.sh),
which regenerates configuration artifacts before delegating to Docker Compose. For architecture details see the
[Technical Guide](TECHNICAL_GUIDE.md); for contribution steps see the [Contributing Guide](../CONTRIBUTING.md).

---

## Quick Start

1. **Clone and prepare the repository:**

   ```bash
   git clone https://github.com/3xpyth0n/leyzen-vault.git
   cd leyzen-vault
   cp env.template .env
   ```

2. **Configure `.env`:** update secrets and select a plugin before issuing lifecycle commands.
   - `VAULT_SERVICE` — service plugin to deploy (`filebrowser`, `paperless`, or any installed plugin).
   - `VAULT_WEB_REPLICAS` — number of web containers created for the plugin.
   - `VAULT_WEB_PORT` — optional override for the plugin’s internal HTTP port.
   - `VAULT_WEB_HEALTHCHECK_PATH` (alias `VAULT_HEALTH_PATH`) — optional path for HAProxy health checks (defaults to the plugin’s value).
   - `VAULT_WEB_HEALTHCHECK_HOST` — optional host header for HAProxy health checks when backends enforce allowlists.
   - Credentials (`VAULT_USER`, `VAULT_PASS`, `VAULT_SECRET_KEY`, etc.) and Docker proxy settings as documented in [`env.template`](../env.template).

3. **Run lifecycle commands via `service.sh`:** the helper script is the only supported interface. It rebuilds the Compose manifest and HAProxy configuration before executing the requested action.

   ```bash
   ./service.sh build     # Build images for the orchestrator, plugins, and supporting services
   ./service.sh start     # Generate configs and launch the stack
   ./service.sh restart   # Regenerate configs, then cycle containers
   ./service.sh stop      # Stop containers and clean up resources (volumes persist)
   ```

   Avoid manual `docker compose` or Python builder commands; bypassing `service.sh` will leave configuration artifacts inconsistent with your `.env` selections.

4. **Access the dashboard:** browse to `http://localhost:8080/orchestrator` and sign in with the credentials stored in `.env`.

> 💡 **HTTP testing reminder:** when running without TLS, set `VAULT_SESSION_COOKIE_SECURE=false` so browsers send the session cookie over plain HTTP.

---

## Core Principles

- **Always use `service.sh`.** Direct Docker commands or manual execution of the Compose builder are unsupported and may produce
  stale configuration.
- **Treat `.env` as the source of truth.** Update variables (for example `VAULT_SERVICE` or `VAULT_WEB_REPLICAS`) before running
  any lifecycle command.
- **Inspect generated artifacts.** When troubleshooting, review `docker-compose.yml` and `haproxy/haproxy.cfg` produced
  by the CLI.

---

## Lifecycle Commands

```bash
./service.sh build     # Regenerate Compose and HAProxy configs, rebuild images if needed
./service.sh start     # Generate configs and launch the stack
./service.sh restart   # Regenerate configs, stop existing containers, and start fresh
./service.sh stop      # Gracefully stop containers without removing volumes
./service.sh status    # Display the current state of all containers
```

Run `./service.sh` without arguments to view usage information and command descriptions.

---

## Switching Plugins

1. Edit `.env` and set `VAULT_SERVICE` to the desired plugin slug. Adjust replica counts or ports as needed.
2. Execute `./service.sh build` to regenerate configuration artifacts for the new plugin.
3. Run `./service.sh restart` to cycle the stack with the updated configuration.
4. Validate application access at `http://localhost:8080/` and the orchestrator dashboard at
   `http://localhost:8080/orchestrator`.

The CLI prevents partial deployments by keeping previous artifacts intact if validation fails.

---

## Monitoring and Troubleshooting

- **Dashboard telemetry** — The orchestrator exposes rotation metrics, audit logs, and activity feeds under `/orchestrator`.
- **Container logs** — After running `./service.sh build` to refresh manifests, inspect logs with
  `docker compose -f docker-compose.yml logs --tail=200 <service>`.
- **HAProxy status** — Review `haproxy/haproxy.cfg` and the generated HAProxy statistics endpoint (enabled when configured in
  `.env`).
- **Configuration drift** — Re-run `./service.sh build` after editing `.env` to ensure changes propagate to Compose and HAProxy.

If you encounter persistent issues, capture the CLI output, generated artifacts, and dashboard logs when filing a report (see the
issue templates in `.github/ISSUE_TEMPLATE/`).

---

## Updates and Maintenance

- **Refreshing dependencies** — Pull the latest `main` branch, review release notes, then run `./service.sh build` to rebuild
  images.
- **Backups** — Persist plugin-specific data volumes using Docker's standard tooling or by copying the volume directories defined
  in the generated Compose file.
- **Security updates** — Monitor the [Security Policy](../SECURITY.md) for disclosure timelines and apply patched releases
  promptly.

For maintainer-specific tasks such as tagging releases and triaging contributions, consult the
[Maintainer Guide](MAINTAINER_GUIDE.md).
