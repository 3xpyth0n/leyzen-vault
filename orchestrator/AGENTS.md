# AGENTS – Leyzen Vault Orchestrator

## Scope

These instructions cover all files inside `orchestrator/`, including Python sources, HTML templates, JavaScript, CSS, static assets, and container build artifacts.

## Platform & dependencies

- The Docker build pipeline compiles Tailwind CSS with Node.js 20 in the first stage, then assembles the runtime on Python 3.11 Alpine.
- Python dependencies live in `requirements.txt`.
- Front-end tooling is managed via `npm ci` and the `build:css` script defined in `package.json`.

## Environment variables & runtime contracts

- The app requires `VAULT_USER`, `VAULT_PASS`, and `VAULT_SECRET_KEY`.
- Rotation behavior depends on `VAULT_WEB_CONTAINERS`, `VAULT_ROTATION_INTERVAL`, and `TIMEZONE`.
- Docker access uses `docker.from_env()`; update docs if socket handling changes.

## Local setup

1. `python3.11 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `npm ci`
4. `npm run build:css`
5. Export the environment variables, then run `python vault_orchestrator.py`.

## Backend conventions

- Use the `log()` helper instead of `print()`.
- Keep container rotation and health logic consistent.
- Background threads start in the `__main__` section — don’t remove them.
- Validate `api_control()` guards before adding new commands.

## Security & endpoints

- Keep cookies `HTTPOnly` + `SameSite=Lax`.
- All routes must remain protected with `login_required`.
- CSP and violation reporting must stay strict.
- SSE endpoints must retain correct headers (`Cache-Control`, etc.).

## Front-end contract

- Keep element IDs and meta tags consistent with `dashboard.js`.
- All forms must include hidden CSRF tokens.
- The logs interface relies on stable element IDs (`refreshBtn`, `log`, etc.).

## Assets & build artefacts

- Edit `styles/tailwind.css`, not `static/tailwind.css`.
- Update `tailwind.config.js` if you add new HTML/JS paths.
- Static assets must maintain cache headers.

## Observability & troubleshooting

- Logs are available under `/orchestrator/logs` and `/orchestrator/logs/raw`.
- Log timestamps must follow `[YYYY-MM-DD HH:MM:SS]`.

## Pre-PR checklist

- Format Python code (PEP 8/Black).
- Rebuild Tailwind if styles or templates change.
- Test auth, CSRF, CSP, and SSE locally.
- Document any new environment variable or script.
