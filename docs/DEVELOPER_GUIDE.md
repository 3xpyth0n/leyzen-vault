# Leyzen Vault Developer Guide

This guide explains how to extend Leyzen Vault by adding new service plugins to the dynamic orchestration system. Familiarity
with Docker Compose and the existing plugin layout is assumed.

---

## Directory Layout

Plugins live under [`vault_plugins/`](../vault_plugins/). Each service occupies its own directory:

```
vault_plugins/
  <service-name>/
    __init__.py
    plugin.py
```

`plugin.py` must export a subclass of `VaultServicePlugin`. The registry automatically discovers modules using Python package
metadata, so no additional wiring is required once the directory structure matches the pattern above.

---

## Required Interface

Every plugin must implement the following pieces:

1. **Subclass declaration**

   ```python
   from vault_plugins import VaultServicePlugin

   class MyServicePlugin(VaultServicePlugin):
       ...
   ```

2. **Metadata** — populate the `metadata` attribute to declare the plugin name, default port, health-check defaults, and optional
   description used by operator tooling.

   ```python
   metadata = VaultServicePlugin.Metadata(
       name="My Service",
       slug="myservice",
       default_port=8080,
       healthcheck_path="/healthz",
   )
   ```

3. **`build_compose(self, env)`** — return a dictionary containing Compose fragments. Typical keys are `services`, `volumes`, and
   `networks`. The Compose builder merges this fragment with the base stack, so keep service names unique and reuse shared
   networks (`vault-net`, `control-net`) when appropriate.

4. **`get_containers(self)`** — return an iterable of service names that expose the web application. These names are used both for
   orchestrator rotation and for HAProxy backend generation.

5. **Optional attributes**:
   - `dependencies` — ordered list of service names that should start before the plugin’s main workload (for example databases or
     caches).
   - `min_replicas` — enforce a minimum number of `VAULT_WEB_REPLICAS` for stability.
   - `default_environment` — additional environment variables injected into the plugin services.

---

## Handling Ports and Replicas

`VaultServicePlugin` exposes helper methods to honour operator overrides:

- Call `self.resolve_port(env)` to apply `VAULT_WEB_PORT` if present, otherwise fall back to `metadata.default_port`.
- Use `self.resolve_replicas(env)` to derive the number of web containers, respecting `VAULT_WEB_REPLICAS` and any plugin minimum.

When scaling containers, ensure your Compose fragment uses the resolved replica count for both service definitions and any
supporting constructs (for example, HAProxy labels or init containers).

---

## Volumes and Dependencies

Plugins may declare additional Docker volumes or external services. Add them to the dictionaries returned by `build_compose()`:

```python
def build_compose(self, env):
    replicas = self.resolve_replicas(env)
    port = self.resolve_port(env)
    return {
        "services": {
            "myservice-web": {
                "image": "example/myservice:latest",
                "deploy": {"replicas": replicas},
                "ports": [f"{port}:8080"],
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

Declare dependent service names in `dependencies` so that `service.sh` renders them before the orchestrator and HAProxy.

---

## HAProxy Integration

No manual HAProxy edits are required. The generator consumes the containers returned by `get_containers()` and automatically:

- Registers each replica in the backend pool.
- Applies `VAULT_WEB_HEALTHCHECK_PATH` (`VAULT_HEALTH_PATH`) and `VAULT_WEB_HEALTHCHECK_HOST` overrides when set.
- Points health checks to the plugin’s default port unless `VAULT_WEB_PORT` specifies a custom value.

If your workload exposes multiple HTTP entry points, consider returning dedicated container names for each entry point and handle
routing inside the plugin (for example through an internal load balancer).

---

## Testing a Plugin

1. Add the plugin directory and implementation.
2. Update `.env` with `VAULT_SERVICE=<your-plugin>` and any custom settings.
3. Run `./service.sh build` followed by `./service.sh start` to generate new Compose and HAProxy artifacts.
4. Inspect `docker-compose.generated.yml` and `haproxy/haproxy.cfg` to confirm your services and backends appear as expected.

Because `service.sh` orchestrates configuration regeneration, avoid invoking the Python builder or Docker Compose directly during
plugin development.

---

## Contributing

Submit pull requests with new plugins or enhancements to the base orchestration system. Provide documentation describing the
service, default credentials (if any), and security considerations so operators can deploy the plugin confidently.
