# Leyzen Vault Developer Guide

This guide describes how to extend Leyzen Vault by authoring plugins that integrate new services into the orchestrator. It
assumes familiarity with Docker Compose and the structure documented in the [Technical Guide](TECHNICAL_GUIDE.md). Before you
begin, review the [Contributing Guide](../CONTRIBUTING.md) for workflow expectations and commit conventions.

---

## Plugin Directory Layout

Each plugin lives under [`vault_plugins/`](../vault_plugins/) and follows a consistent structure:

```
vault_plugins/
  <service-name>/
    __init__.py
    plugin.py
```

The package must expose exactly one subclass of `VaultServicePlugin`. Discovery is automatic as long as the directory is a
valid Python package; the `__init__.py` file can remain empty because the loader inspects `<service>/plugin.py` directly.

---

## Implementing `VaultServicePlugin`

Every plugin must define the following pieces:

1. **Subclass Declaration**

   ```python
   from vault_plugins import VaultServicePlugin

   class MyServicePlugin(VaultServicePlugin):
       ...
   ```

2. **Core class attributes** — Declare identifiers and defaults that describe the workload:

   ```python
   class MyServicePlugin(VaultServicePlugin):
       name = "myservice"
       replicas = 2
       min_replicas = 1
       web_port = 8080
       healthcheck_path = "/healthz"
       healthcheck_host = "myservice.internal"
       dependencies = ("myservice-db",)
   ```

   These values seed HAProxy configuration, rotation defaults, and startup ordering. The base class enforces
   `min_replicas <= replicas` and normalizes health-check fields.

3. **Optional `setup(self, env)` hook** — Override this method when you need to compute additional state (for example deriving
   per-replica configuration files or reading environment toggles). Always call `super().setup(env)` so environment overrides for
   replicas and health checks are honored before applying custom logic.

   ```python
   def setup(self, env):
       if env.get("MY_SERVICE_STRICT", "").lower() == "true":
           self.healthcheck_path = "/readyz"
       super().setup(env)
   ```

4. **`build_compose(self, env)`** — Return a dictionary containing Compose schema fragments (`services`, `volumes`, `networks`).
   Most plugins call `self.setup(env)` at the start of this method. After setup runs, use `self.active_replicas` for scaling
   values and reference `self.web_port` or other attributes as needed when shaping service definitions.

5. **`get_containers(self)`** — Return an iterable of service names that expose HTTP endpoints. The default implementation uses
   `active_replicas` to enumerate containers named `<plugin>_web1`, `<plugin>_web2`, etc. Override this method when your Compose
   fragment uses different naming conventions.

The [Operations Guide](OPERATIONS.md) explains how operators select plugins at runtime.

---

## Compose Fragment Patterns

`build_compose()` merges directly into the base manifest. Keep fragments self-contained and reuse project resources:

- Attach plugin services to `vault-net` for user traffic and to `control-net` when the orchestrator must reach them.
- Reference secrets and credentials via environment variables loaded from `.env`.
- Declare additional volumes or networks at the root level of the fragment when necessary.
- For stateful dependencies (databases, caches), list their service names in `dependencies` so they bootstrap before the web
  workload.

Example skeleton:

```python
def build_compose(self, env):
    self.setup(env)
    replicas = self.active_replicas
    port = int(env.get("MY_SERVICE_PORT", self.web_port))
    return {
        "services": {
            "myservice-web": {
                "image": "example/myservice:latest",
                "deploy": {"replicas": replicas},
                "environment": {
                    "MY_SERVICE_PORT": port,
                },
                "networks": ["vault-net"],
            },
            "myservice-db": {
                "image": "postgres:16",
                "volumes": ["myservice-db:/var/lib/postgresql/data"],
                "networks": ["vault-net"],
            },
        },
        "volumes": {
            "myservice-db": {},
        },
    }
```

---

## HAProxy and Rotation

The HAProxy configuration is derived automatically from `get_containers()`. You do **not** need to edit `haproxy.cfg`
manually. Ensure the container names you return correspond to services that expose HTTP endpoints. When a plugin exports
multiple endpoints, return each container and manage routing internally within the plugin or by using dedicated frontend
services.

---

## Testing Plugins

Always test plugins using `./leyzenctl`:

1. Export or set `VAULT_SERVICE=<your-plugin>` in `.env`.
2. Run `./leyzenctl build` to regenerate the Compose manifest and HAProxy configuration.
3. Run `./leyzenctl start` to launch the stack and confirm the plugin boots.
4. Inspect `docker-compose.yml` and `haproxy/haproxy.cfg` to verify service definitions and backend pools.
5. Use the orchestrator dashboard (`/orchestrator`) to ensure rotation metrics update as expected.

If your plugin modifies documentation, update `docs/` accordingly and cross-link relevant sections.

---

## Submitting Changes

Follow the workflow and commit guidelines in [CONTRIBUTING.md](../CONTRIBUTING.md). Mention any new environment variables,
secrets, or operational considerations in your pull request description so maintainers can update the
[Maintainer Guide](MAINTAINER_GUIDE.md) or [Operations Guide](OPERATIONS.md) as needed.
