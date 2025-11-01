# Leyzen Vault Technical Guide

This guide describes the internal architecture that powers Leyzen Vault’s modular moving-target defense platform. Use it as a
companion to the high-level overview in the main README and the implementation references in `compose/` and `vault_plugins/`.

---

## Architectural Overview

Leyzen Vault assembles its runtime dynamically from three cooperating subsystems:

1. **Plugin Loader** — The registry under [`vault_plugins/`](../vault_plugins/) discovers modules that subclass
   `VaultServicePlugin`. Each plugin exposes metadata, Compose fragments, and rotation-aware container names.
2. **Compose Builder** — [`compose/build.py`](../compose/build.py) merges the base services with the selected plugin to generate a
   tailored `docker-compose.generated.yml`. It handles dependency ordering, volume aggregation, and environment overrides.
3. **HAProxy Generator** — [`compose/haproxy_config.py`](../compose/haproxy_config.py) renders `haproxy/haproxy.cfg` so that
   frontend routing, health checks, and replica pools align with the active plugin.

These pieces are orchestrated automatically through `service.sh`, ensuring the stack remains self-contained and consistent with
the `.env` configuration.

---

## Workflow

1. **Operator invokes `service.sh`.** Every lifecycle command (`build`, `start`, `restart`, `stop`, etc.) funnels through the
   helper script.
2. **Environment loading.** `service.sh` calls the Compose builder, which reads `.env` via `compose.build.load_environment()` and
   merges the file with any exported shell variables.
3. **Plugin selection.** The builder resolves `VAULT_SERVICE` and loads the matching plugin via the registry. If the variable is
   unset, the default plugin declared in `env.template` is used. An invalid name raises a clear error listing the available
   plugins so operators can correct the value before the stack is modified.
4. **Asset generation.** With a plugin selected, the builder produces two artifacts:
   - `docker-compose.generated.yml` — merged base services plus plugin-defined workloads, volumes, and networks.
   - `haproxy/haproxy.cfg` — front-end configuration that registers each plugin replica as an HAProxy backend, including health
     checks and port overrides.
5. **Execution.** Only after artifacts are rebuilt does `service.sh` delegate to Docker Compose (`docker compose up`, `down`,
   etc.) to perform the requested action.
6. **Routing.** HAProxy automatically routes user traffic to the plugin’s containers while forwarding `/orchestrator` to the
   dashboard. Health probes follow the configuration derived from the plugin metadata and `.env` overrides.

---

## Environment Variables

The following settings drive the plugin workflow:

- `VAULT_SERVICE` — selects which plugin to activate. Invalid values produce a registry error with the canonical list of
  available options.
- `VAULT_WEB_REPLICAS` — scales the number of web containers launched for the active plugin. The builder clamps the value to any
  plugin-defined minimum to maintain rotation guarantees.
- `VAULT_WEB_PORT` — optional override for the plugin’s internal HTTP port. When omitted, the plugin’s default metadata is used.
- `VAULT_WEB_HEALTHCHECK_PATH` (`VAULT_HEALTH_PATH`) — optional path for HAProxy health checks. Defaults to the plugin’s
  recommended endpoint when unset.
- `VAULT_WEB_HEALTHCHECK_HOST` — optional override for the Host header emitted during HAProxy health checks.

Additional variables such as `VAULT_WEB_CONTAINERS`, `VAULT_USER`, and `DOCKER_PROXY_TOKEN` control container allowlists,
dashboard credentials, and Docker proxy authentication. Refer to [`env.template`](../env.template) for the complete catalog.

If the `.env` file is missing required settings, the builder surfaces human-readable errors so operators can correct them before
proceeding. Failure to resolve a plugin halts execution and leaves previously generated artifacts untouched, avoiding accidental
configuration drift.

---

## Error Handling and Fallbacks

- **Unknown plugin names** — The registry raises a `ValueError` listing detected plugins. `service.sh` prints the message and
  exits with a non-zero status so automation can react accordingly.
- **Missing container definitions** — If a plugin returns no web containers, the builder instructs operators to override the
  allowlist with `VAULT_WEB_CONTAINERS`.
- **Replica bounds** — Plugins may enforce minimum replica counts. Requests below the threshold are automatically bumped to the
  safe value.
- **Health checks** — When `VAULT_WEB_HEALTHCHECK_PATH` or `VAULT_WEB_HEALTHCHECK_HOST` is unset, HAProxy falls back to the
  plugin-provided defaults, guaranteeing a functional configuration even when optional overrides are omitted.

---

## Implementing a Plugin

Developers create new plugins under `vault_plugins/<service>/plugin.py`. Each module should:

1. Subclass `VaultServicePlugin` and populate the `metadata` attribute with the display name, default port, and health-check
   defaults.
2. Implement `build_compose(env)` to return a dictionary compatible with Docker Compose schema fragments (`services`, `volumes`,
   `networks`). The builder merges this fragment with the base stack.
3. Provide `get_containers()` so the orchestrator knows which service names participate in rotation.
4. Declare optional `dependencies` for supporting services (for example, databases or caches). Dependencies are inserted before
   the base stack to preserve startup order.

Plugins automatically benefit from the HAProxy generator—any containers returned by `get_containers()` are registered as backend
servers, and scaling with `VAULT_WEB_REPLICAS` adjusts the rendered configuration without further changes. For a detailed
implementation walkthrough, refer to the [Developer Guide](DEVELOPER_GUIDE.md).

---

## Related Resources

- [`compose/build.py`](../compose/build.py) — Compose manifest builder.
- [`compose/haproxy_config.py`](../compose/haproxy_config.py) — HAProxy configuration renderer.
- [`vault_plugins/`](../vault_plugins/) — Plugin modules and registry entry point.
- [`service.sh`](../service.sh) — Operational wrapper that guarantees configuration regeneration before lifecycle actions.

Understanding these components is essential for extending the platform or integrating Leyzen Vault into custom deployment
pipelines.
