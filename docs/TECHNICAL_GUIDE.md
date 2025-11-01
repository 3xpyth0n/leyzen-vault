# Leyzen Vault Technical Guide

This guide documents the internal architecture behind Leyzen Vault's modular moving-target defense orchestrator. It complements
the high-level overview in the [README](../README.md), the operational procedures in the
[Operations Guide](OPERATIONS.md), and the plugin authoring instructions in the [Developer Guide](DEVELOPER_GUIDE.md).

---

## Architecture Overview

Leyzen Vault assembles an ephemeral stack tailored to the active plugin. The workflow is coordinated through
[`service.sh`](../service.sh) and the following subsystems:

1. **Plugin Registry** — Packages under [`vault_plugins/`](../vault_plugins/) expose subclasses of `VaultServicePlugin` with
   metadata, Compose fragments, and rotation-aware container identifiers.
2. **Compose Builder** — [`compose/build.py`](../compose/build.py) loads `.env`, merges plugin fragments with the base stack, and
   emits `docker-compose.yml`.
3. **HAProxy Configuration Generator** — [`compose/haproxy_config.py`](../compose/haproxy_config.py) renders
   `haproxy/haproxy.cfg` to route traffic across orchestrator services and plugin replicas.
4. **Orchestrator Dashboard** — [`orchestrator/`](../orchestrator/) is a Flask application that authenticates operators, manages
   rotation policies, and exposes runtime telemetry.
5. **Docker Proxy** — [`docker-proxy/`](../docker-proxy/) gates all Docker Engine access through a hardened HTTP API to avoid
   exposing the raw socket.

These components are designed to be modular: plugins can ship additional services, while the builder and HAProxy generator
translate those definitions into a unified runtime configuration.

---

## Lifecycle Sequence

Every lifecycle command flows through `service.sh`:

1. **Command dispatch** — Operators run `./service.sh <action>`. The script validates prerequisites, loads helpers, and invokes
   the Compose builder.
2. **Environment resolution** — `compose.build.load_environment()` combines values from `.env` and exported shell variables.
   Required entries produce actionable errors when missing.
3. **Plugin selection** — `VAULT_SERVICE` identifies the plugin module. Invalid names raise a registry error that enumerates the
   discovered plugins.
4. **Artifact generation** — The builder emits an updated `docker-compose.yml` and HAProxy generator creates
   `haproxy/haproxy.cfg`. Existing artifacts remain untouched if validation fails, preventing accidental drift.
5. **Docker Compose execution** — Only after artifacts are refreshed does `service.sh` call `docker compose` with the requested
   action (`build`, `up`, `down`, etc.).
6. **Runtime coordination** — HAProxy forwards `/orchestrator` traffic to the dashboard, and plugin-specific requests to the
   generated backend pool. Health checks reuse metadata from the active plugin and any overrides from `.env`.

Because all lifecycle operations share this sequence, operators never need to call Docker commands directly.

---

## Configuration Inputs

Leyzen Vault centralizes configuration in environment variables. Key inputs include:

- `VAULT_SERVICE` — Selects the active plugin directory. Defaults are declared in `env.template`.
- `VAULT_WEB_REPLICAS` — Number of application replicas. Plugins may enforce a minimum via `min_replicas`.
- `VAULT_WEB_PORT` — Optional override for the plugin's HTTP port; otherwise the plugin metadata default is used.
- `VAULT_WEB_HEALTHCHECK_PATH` (alias `VAULT_HEALTH_PATH`) — Health-check path for HAProxy.
- `VAULT_WEB_HEALTHCHECK_HOST` — Optional host header used by HAProxy health checks.
- `VAULT_WEB_CONTAINERS` — Explicit override for the container names returned to the orchestrator when the plugin does not
  expose web workloads automatically.
- `DOCKER_PROXY_TOKEN`, `VAULT_USER`, `VAULT_PASSWORD`, and other secrets that secure the dashboard and Docker proxy.

Refer to [`env.template`](../env.template) for the complete list of supported variables. Validation errors surface directly in
`service.sh` output so that automation and CI can fail fast.

---

## Plugin Integration

Plugins subclass `VaultServicePlugin` and implement:

- `metadata` — Declares the display name, slug, default port, and health-check defaults.
- `build_compose(env)` — Returns a dictionary fragment merged by the Compose builder. Services should reuse the shared networks
  (`vault-net`, `control-net`) where possible.
- `get_containers()` — Lists container names eligible for rotation and HAProxy registration.
- Optional helpers such as `dependencies`, `default_environment`, and `min_replicas` to tighten runtime guarantees.

The builder resolves replicas via `resolve_replicas(env)` and ports via `resolve_port(env)` to maintain parity between Compose
services and HAProxy backends. See the [Developer Guide](DEVELOPER_GUIDE.md) for step-by-step authoring guidance.

---

## Error Handling and Observability

- **Registry failures** — Unknown plugin slugs raise descriptive exceptions. `service.sh` prints the list of detected plugins to
  aid selection.
- **Validation errors** — Missing environment variables or malformed Compose fragments cause the build step to exit before Docker
  commands run, leaving prior artifacts intact.
- **Logging** — The orchestrator streams structured logs through the dashboard. Operators can inspect full runtime logs via the
  `/orchestrator/logs` interface.
- **Health checks** — HAProxy backends inherit plugin defaults and support optional overrides via environment variables. Changes
  take effect the next time `./service.sh build` or `./service.sh start` runs.

For runtime security headers, CSP policies, and CSRF protections, review [`orchestrator/SECURITY.md`](../orchestrator/SECURITY.md).

---

## See Also

- [Operations Guide](OPERATIONS.md) — Day-to-day commands using `service.sh`.
- [Developer Guide](DEVELOPER_GUIDE.md) — Plugin authoring and testing practices.
- [Maintainer Guide](MAINTAINER_GUIDE.md) — Issue triage, reviews, and release workflow.
- [Security Policy](../SECURITY.md) — Coordinated vulnerability disclosure process.
