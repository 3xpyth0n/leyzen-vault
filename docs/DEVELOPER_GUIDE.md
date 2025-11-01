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

The package must expose exactly one subclass of `VaultServicePlugin`. Discovery is automatic as long as the directory is a valid
Python package and the subclass is imported in `__init__.py`.

---

## Implementing `VaultServicePlugin`

Every plugin must define the following pieces:

1. **Subclass Declaration**

   ```python
   from vault_plugins import VaultServicePlugin

   class MyServicePlugin(VaultServicePlugin):
       ...
   ```

2. **Metadata** — Populate the `metadata` attribute to describe the plugin:

   ```python
   metadata = VaultServicePlugin.Metadata(
       name="My Service",
       slug="myservice",
       default_port=8080,
       healthcheck_path="/healthz",
   )
   ```

   Metadata powers the CLI selection menu, health checks, and default routing.

3. **`build_compose(self, env)`** — Return a dictionary containing Compose schema fragments (`services`, `volumes`, `networks`).
   Use helper methods like `self.resolve_port(env)` and `self.resolve_replicas(env)` to respect operator overrides.

4. **`get_containers(self)`** — Return an iterable of service names that expose HTTP endpoints. These identifiers feed both the
   orchestrator rotation logic and the HAProxy generator.

5. **Optional Attributes** — Provide `dependencies`, `default_environment`, or `min_replicas` when you need to influence startup
   order, inject environment variables, or enforce scaling requirements.

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
    replicas = self.resolve_replicas(env)
    port = self.resolve_port(env)
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

Always test plugins using `./service.sh`:

1. Export or set `VAULT_SERVICE=<your-plugin>` in `.env`.
2. Run `./service.sh build` to regenerate the Compose manifest and HAProxy configuration.
3. Run `./service.sh start` to launch the stack and confirm the plugin boots.
4. Inspect `docker-compose.yml` and `haproxy/haproxy.cfg` to verify service definitions and backend pools.
5. Use the orchestrator dashboard (`/orchestrator`) to ensure rotation metrics update as expected.

If your plugin modifies documentation, update `docs/` accordingly and cross-link relevant sections.

---

## Submitting Changes

Follow the workflow and commit guidelines in [CONTRIBUTING.md](../CONTRIBUTING.md). Mention any new environment variables,
secrets, or operational considerations in your pull request description so maintainers can update the
[Maintainer Guide](MAINTAINER_GUIDE.md) or [Operations Guide](OPERATIONS.md) as needed.
