# Leyzen Vault — Agent Guidelines

Welcome! This repository powers the Leyzen Vault proof-of-concept stack. Use this
reference to understand the layout, preferred coding styles, and the sanity
checks we expect before shipping changes.

## Repository map

- `orchestrator/` — Flask application that exposes the admin dashboard and
  coordinates container rotation. Houses most Python code, HTML templates, JS,
  and CSS.
- `docker-proxy/` — Minimal Flask service that brokers authenticated, allowlisted
  requests to the Docker Engine socket.
- `haproxy/` — Static HAProxy configuration and error pages that front every
  HTTP service.
- `filebrowser/` — Dockerfile and entrypoint used to run the upstream Filebrowser
  binary with the correct defaults for the demo.
- `leyzenctl` — Deployment helper (Go CLI binary compiled by `install.sh`).

## Python guidelines (`orchestrator/`, `docker-proxy/`)

- **Typing & style**: Keep `from __future__ import annotations` at the top of new
  modules. Add precise type hints, docstrings, and descriptive variable names.
  Follow the existing preference for helper functions and small, testable
  methods. Use dataclasses or typed dictionaries instead of loosely typed
  structures when practical.
- **Imports**: Group standard library, third-party, and local imports separately
  (see existing modules for ordering). Avoid introducing new dependencies unless
  they are already declared in `requirements.in` / `requirements.txt`.
- **Configuration access**: Read request-scoped objects through Flask’s
  `current_app.config` helpers (see `blueprints/auth.py`). Avoid storing global
  mutable state outside the orchestrator service classes.
- **Timezone awareness**: Use the timezone stored in `Settings.timezone` for all
  timestamps; `datetime.now(settings.timezone)` is the established pattern.
- **Logging**: Route operational logs through `FileLogger` and keep secrets out
  of log messages. Prefer `.log()` for structured entries; use `.warning()` only
  for noteworthy anomalies.
- **HTTP clients**: Reuse the shared `httpx.Client` in the Docker proxy;
  instantiate new clients only when caching or lifetimes demand it.
- **Error handling**: Raise custom exceptions that inherit from the local error
  base classes (e.g., `DockerProxyError`) and surface human-readable messages to
  the dashboard. Guard asynchronous worker loops with targeted `try/except`
  blocks—see `_orchestrator_loop()` for reference.
- **Unit boundaries**: Keep background threads, SSE streaming, and rotation
  mechanics inside `RotationService`. Blueprints should remain thin adapters
  between Flask routes and service methods.

## Flask blueprints & templates (`orchestrator/blueprints`, `orchestrator/templates`)

- Blueprints should only call into services or helpers defined under
  `orchestrator/services` and `orchestrator/blueprints/utils.py`. Do not access
  Docker or filesystem resources directly from the views.
- Prefer returning dictionaries and letting Flask/Jinja render templates; keep
  inline HTML minimal.
- Templates are hand-authored HTML. Respect the existing semantic layout and
  accessibility cues (ARIA attributes, alt text, button labels). Keep inline
  scripts out of templates; place JS in `static/js` modules.
- When exposing new context variables, update the template, JS bootstrap data,
  and `dashboard` blueprint together.

## Front-end assets (`orchestrator/static`, `orchestrator/styles`)

- **JavaScript**: Modules live under `static/js/` and use modern ES modules.
  Stick with `const`/`let`, async/await, and `fetch`. Shared utilities belong in
  `static/js/core/` or `static/js/charts/`. Avoid mutating the vendor bundles in
  `static/js/vendor/`; replace them only by downloading a new upstream build.
- **Styling**: Tailwind utilities are compiled from `styles/tailwind.css` via
  `npm run build:css`. Update source styles there rather than editing the
  generated `static/tailwind.css`. Custom component styles live in
  `static/index.css`, `static/dashboard.css`, etc.—keep selectors BEM-like and
  responsive.
- **Assets**: Reference files under `/orchestrator/static/...` in templates and
  ensure cache-busting via `asset_version` when adding new bundles.

## Supporting services

- `docker-proxy/proxy.py` enforces bearer-token authentication and a strict
  endpoint allowlist. Maintain the pattern of compiling regular expressions at
  import time and validating headers in dedicated helpers.
- HAProxy templates should preserve the security headers already in place.
  Update both the config and error-page snippets if you tweak status handling.
- `filebrowser/entrypoint.sh` is a thin wrapper; keep it POSIX sh compatible.

## Testing & verification

- For Python syntax safety, run `python -m compileall orchestrator docker-proxy`
  before committing.
- When you touch front-end assets, run `npm install` (once) and then
  `npm run build:css` inside `orchestrator/` to refresh the generated CSS.
- If you modify docker-compose services or shell scripts, validate them with
  `docker compose config` and `shellcheck` where available.
- Manual smoke tests: start the stack with `docker compose up --build` and visit
  the orchestrator dashboard to confirm rotation metrics still stream.

## Documentation & operational notes

- Update `README.md` for user-facing changes. For operational or security
  adjustments, update the relevant pages in the [GitHub Wiki](https://github.com/3xpyth0n/leyzen-vault/wiki).
- Security-sensitive tweaks (auth flow, captcha, CSP reporting) should include a
  short rationale in commit messages or doc updates.

Happy hacking!
