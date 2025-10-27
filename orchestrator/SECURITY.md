# Security Guidelines

## Network Segmentation

- `vault-net` carries client-facing traffic (HAProxy, Filebrowser, orchestrator dashboard).
- `control-net` isolates the Docker control plane; only `docker-proxy` and `orchestrator` are attached.
- Validate with `docker network inspect` after deployments to ensure no unexpected services join `control-net`.

## Docker Proxy Access Control

- All lifecycle commands traverse the authenticated `docker-proxy` endpoint.
- The orchestrator injects `Authorization: Bearer <DOCKER_PROXY_TOKEN>` on every request; omit the token and requests will fail fast.
- Scope the proxy ACLs (e.g., `CONTAINERS=1`, `POST=1`) to only the verbs required for rotation.

## Token Rotation Procedure

1. Generate a new secret token (`openssl rand -hex 32`).
2. Update `DOCKER_PROXY_TOKEN` inside the local `.env` file.
3. Redeploy the affected services: `docker compose up -d docker-proxy orchestrator`.
4. Invalidate any previous tokens and redistribute securely (e.g., password manager, secret store).

## Secret Storage

- Never commit `.env` with real secrets; only track `env.template`.
- Restrict file permissions on `.env` (`chmod 600 .env`) when running on shared hosts.
- Consider external secret managers for production deployments.
