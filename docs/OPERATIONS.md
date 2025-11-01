# Leyzen Vault Operations Guide

This document summarizes the supported operational workflow for Leyzen Vault. All lifecycle actions are mediated by
`./service.sh`, which ensures configuration assets are regenerated before Docker is invoked.

---

## Operational Principles

- **Always use `service.sh`.** Do not run `docker compose` directly or invoke the Python builder manually. The script calls the
  builder, regenerates `docker-compose.generated.yml` and `haproxy/haproxy.cfg`, and then executes the requested action.
- **Treat `.env` as the source of truth.** Update variables such as `VAULT_SERVICE`, `VAULT_WEB_REPLICAS`, and
  `VAULT_WEB_HEALTHCHECK_PATH` there before running commands.
- **Review generated artifacts when troubleshooting.** If a command fails, inspect the latest `docker-compose.generated.yml` and
  `haproxy/haproxy.cfg` produced by the script for clues.

---

## Common Commands

```bash
./service.sh build     # Build or rebuild container images
./service.sh start     # Generate configs and launch the stack
./service.sh restart   # Regenerate configs, stop, and start containers
./service.sh stop      # Stop containers and clean up runtime resources
```

Additional helper actions are documented by running `./service.sh help`.

---

## Recommended Workflow

1. Update `.env` with the desired plugin and replica counts.
2. Execute `./service.sh build` to refresh images and regenerate configuration.
3. Start or restart the stack using `./service.sh start` or `./service.sh restart`.
4. Validate access via `http://localhost:8080/` (plugin UI) and `http://localhost:8080/orchestrator` (dashboard).
5. Use `./service.sh stop` for graceful shutdowns; volumes remain intact for the next session.

Following this process keeps the generated Compose manifest and HAProxy configuration synchronized with your environment
variables, ensuring consistent deployments across machines and automation pipelines.
