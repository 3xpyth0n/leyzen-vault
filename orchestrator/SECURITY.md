# Leyzen Vault Orchestrator Security Overview

This document summarizes the defensive controls implemented in the orchestrator
service and highlights considerations for extending the stack safely.

## Deployment assumptions

- The orchestrator is designed to run behind a trusted reverse proxy. Requests
  are normalized through Werkzeug's `ProxyFix` middleware and the number of
  trusted hops is capped by `Settings.proxy_trust_count` to prevent spoofed
  forwarding headers.  
  [`orchestrator/__init__.py:L25-L39`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/__init__.py#L25-L39)  
  [`orchestrator/config.py:L64-L81`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L64-L81)

- Environment variables provide credentials, secrets, and the allowlist of
  containers the orchestrator may control. Startup validation refuses to launch
  when required values are missing or malformed.  
  [`orchestrator/config.py:L43-L60`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L43-L60)  
  [`orchestrator/config.py:L82-L142`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L82-L142)

- Application logs are written to a dedicated file whose location can be
  overridden with `ORCHESTRATOR_LOG_DIR`; the directory is created at startup so
  file permissions can be managed by deployment tooling.  
  [`orchestrator/config.py:L101-L142`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L101-L142)

## Authentication and session protection

- Administrator authentication relies on `werkzeug.security` password hashes
  derived from the configured `VAULT_PASS` secret; plaintext passwords are not
  stored.  
  [`orchestrator/config.py:L122-L138`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L122-L138)

- The login form issues rotating CSRF tokens kept in an in-memory store with a
  configurable TTL. Tokens are required for captcha refreshes and initial login
  POSTs, and are retired immediately after use.  
  [`orchestrator/blueprints/auth.py:L231-L276`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L231-L276)  
  [`orchestrator/blueprints/auth.py:L302-L360`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L302-L360)

- Human verification is enforced through a captcha generator that supports both
  Pillow-backed PNGs and a hardened SVG fallback. Captcha solutions are cached
  server-side and invalidated after verification.  
  [`orchestrator/blueprints/auth.py:L62-L217`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L62-L217)  
  [`orchestrator/blueprints/auth.py:L278-L347`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L278-L347)

- Repeated failures trigger IP-based rate limiting with a five minute backoff
  window, blocking automated guessing attempts.  
  [`orchestrator/blueprints/auth.py:L196-L230`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L196-L230)  
  [`orchestrator/blueprints/auth.py:L321-L360`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L321-L360)

- Sessions are flagged `HttpOnly`, `SameSite=Lax`, and `Secure` by default to
  ensure cookies ride only over HTTPS; background workers are started lazily to
  limit exposure before the first authenticated request. Deployments that run
  entirely on HTTP may toggle `VAULT_SESSION_COOKIE_SECURE` to `false`.
  [`orchestrator/__init__.py:L30-L57`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/__init__.py#L30-L57)
  [`orchestrator/config.py:L43-L180`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/config.py#L43-L180)
  [`orchestrator/app.py:L39-L63`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/app.py#L39-L63)

## Request handling and transport security

- A strict Content Security Policy is injected on every response, forbidding
  inline scripts and third-party origins except for vetted style/font CDNs and
  routing violation reports to a dedicated endpoint.  
  [`orchestrator/__init__.py:L45-L63`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/__init__.py#L45-L63)

- The CSP report collector enforces size limits and per-IP rate caps before
  logging sanitized payload metadata, reducing risk from log-injection or
  flooding attacks.  
  [`orchestrator/blueprints/dashboard.py:L104-L190`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/dashboard.py#L104-L190)

- Static asset routes apply explicit MIME types and cache-control headers while
  keeping the dashboard JS bundle authenticated-only.  
  [`orchestrator/blueprints/dashboard.py:L80-L135`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/dashboard.py#L80-L135)

- Client IP detection respects `X-Forwarded-For` only for routable addresses,
  falling back to Flask's remote address, reducing spoofing risk from private or
  loopback ranges.  
  [`orchestrator/blueprints/utils.py:L11-L40`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/utils.py#L11-L40)

## Docker control plane safeguards

- The orchestrator delegates container lifecycle operations to a
  token-protected docker-proxy service and keeps a strict allowlist of container
  names derived from configuration. Unauthorized requests are logged and
  rejected server-side.  
  [`orchestrator/services/docker_proxy.py:L15-L118`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/services/docker_proxy.py#L15-L118)  
  [`orchestrator/services/docker_proxy.py:L170-L218`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/services/docker_proxy.py#L170-L218)

- Cached `docker inspect` payloads are bounded by a short TTL to avoid leaking
  stale state to operators while still minimizing proxy traffic.  
  [`orchestrator/services/docker_proxy.py:L126-L218`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/services/docker_proxy.py#L126-L218)

- Control endpoints validate state transitions (e.g., disallowing kill when the
  rotation loop is active) and audit every action together with the originating
  client IP.  
  [`orchestrator/blueprints/dashboard.py:L31-L103`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/dashboard.py#L31-L103)

## Logging and observability

- All structured log entries are sanitized to remove control characters before
  writing to disk, mitigating log-forging attacks.  
  [`orchestrator/services/logging.py:L1-L48`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/services/logging.py#L1-L48)

- Authentication, control requests, and CSP reports include contextual metadata
  to help correlate suspicious activity while avoiding sensitive payloads.  
  [`orchestrator/blueprints/auth.py:L314-L360`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/auth.py#L314-L360)  
  [`orchestrator/blueprints/dashboard.py:L31-L190`](https://github.com/3xpyth0n/leyzen-vault/blob/main/orchestrator/blueprints/dashboard.py#L31-L190)

## Known gaps and future hardening

- Session cookies default to `Secure`, but environments without TLS must
  explicitly relax `VAULT_SESSION_COOKIE_SECURE`. Ensure proxies terminate HTTPS
  before disabling this protection.

- The captcha store and login attempt tracker rely on in-memory globals, which
  are reset across process restarts and do not scale horizontally. Consider
  migrating to a shared cache such as Redis.

- The docker-proxy interactions trust the upstream service's TLS termination.
  Add mutual TLS or network-level ACLs when running outside a single docker
  network.

- Implement automated end-to-end tests that exercise the rotation controls and
  CSP reporting to catch regressions in authentication flow or log handling.
