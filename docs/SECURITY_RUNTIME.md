# Leyzen Vault Orchestrator Security Overview

This document summarizes the defensive controls implemented in the orchestrator
service and highlights considerations for extending the stack safely.

## Deployment assumptions

- The orchestrator is designed to run behind a trusted reverse proxy. Requests
  are normalized through Werkzeug's `ProxyFix` middleware and the number of
  trusted hops is capped by `Settings.proxy_trust_count` to prevent spoofed
  forwarding headers. See `create_app()` in `src/orchestrator/__init__.py` and
  `load_settings()` in `src/orchestrator/config.py`.

- Environment variables provide credentials, secrets, and the allowlist of
  containers the orchestrator may control. Startup validation refuses to launch
  when required values are missing or malformed. See `Settings` dataclass and
  `load_settings()` function in `src/orchestrator/config.py`.

- Application logs are written to a dedicated file whose location can be
  overridden with `ORCH_LOG_DIR`; the directory is created at startup
  so file permissions can be managed by deployment tooling. See `_determine_log_file()`
  and `load_settings()` in `src/orchestrator/config.py`.

## Authentication and session protection

- Administrator authentication relies on `werkzeug.security` password hashes
  derived from the configured `VAULT_PASS` secret; plaintext passwords are not
  stored. See `load_settings()` in `src/orchestrator/config.py`.

- The login form issues rotating CSRF tokens kept in an in-memory store with a
  configurable TTL. Tokens are required for captcha refreshes and initial login
  POSTs, and are retired immediately after use. See CSRF token generation and
  validation functions in `src/orchestrator/blueprints/auth.py`.

- Human verification is enforced through a captcha generator that supports both
  Pillow-backed PNGs and a hardened SVG fallback. Captcha solutions are cached
  server-side and invalidated after verification. See captcha generation and
  validation functions in `src/orchestrator/blueprints/auth.py`.

- Repeated failures trigger IP-based rate limiting with a five minute backoff
  window, blocking automated guessing attempts. See rate limiting logic in
  `src/orchestrator/blueprints/auth.py`.

- Sessions are flagged `HttpOnly`, `SameSite=Lax`, and `Secure` by default to
  ensure cookies ride only over HTTPS; background workers are started lazily to
  limit exposure before the first authenticated request. Deployments that run
  entirely on HTTP may toggle `SESSION_COOKIE_SECURE` to `false`.
  See `create_app()` in `src/orchestrator/__init__.py` and session configuration
  in `load_settings()`.

## Request handling and transport security

- A strict Content Security Policy is injected on every response, forbidding
  inline scripts and third-party origins except for vetted style/font CDNs and
  routing violation reports to a dedicated endpoint. See CSP header injection
  in `create_app()` in `src/orchestrator/__init__.py`.

- The CSP report collector enforces size limits and per-IP rate caps before
  logging sanitized payload metadata, reducing risk from log-injection or
  flooding attacks. See CSP violation report endpoint in
  `src/orchestrator/blueprints/dashboard.py`.

- Static asset routes apply explicit MIME types and cache-control headers while
  keeping the dashboard JS bundle authenticated-only. See static file serving
  in `src/orchestrator/blueprints/dashboard.py`.

- Client IP detection respects `X-Forwarded-For` only for routable addresses,
  falling back to Flask's remote address, reducing spoofing risk from private or
  loopback ranges. See `get_client_ip()` function in `src/orchestrator/blueprints/utils.py`.

## Docker control plane safeguards

- The orchestrator delegates container lifecycle operations to a
  token-protected docker-proxy service and keeps a strict allowlist of container
  names derived from configuration. Unauthorized requests are logged and
  rejected server-side. See `DockerProxyClient` and `DockerProxyService` classes
  in `src/orchestrator/services/docker_proxy.py`.

- Cached `docker inspect` payloads are bounded by a short TTL to avoid leaking
  stale state to operators while still minimizing proxy traffic. See caching logic
  in `DockerProxyClient` in `src/orchestrator/services/docker_proxy.py`.

- Control endpoints validate state transitions (e.g., disallowing kill when the
  rotation loop is active) and audit every action together with the originating
  client IP. See control endpoint handlers in `src/orchestrator/blueprints/dashboard.py`.

## Logging and observability

- All structured log entries are sanitized to remove control characters before
  writing to disk, mitigating log-forging attacks. See `FileLogger` class and
  `_sanitize_log_value()` function in `src/orchestrator/services/logging.py`.

- Authentication, control requests, and CSP reports include contextual metadata
  to help correlate suspicious activity while avoiding sensitive payloads.
  See logging in authentication handlers (`src/orchestrator/blueprints/auth.py`)
  and dashboard control endpoints (`src/orchestrator/blueprints/dashboard.py`).

## Known gaps and future hardening

- Session cookies default to `Secure`, but environments without TLS must
  explicitly relax `SESSION_COOKIE_SECURE`. Ensure proxies terminate HTTPS
  before disabling this protection.

- The captcha store and login attempt tracker rely on in-memory globals, which
  are reset across process restarts and do not scale horizontally. Consider
  migrating to a shared cache such as Redis.

- The docker-proxy interactions trust the upstream service's TLS termination.
  Add mutual TLS or network-level ACLs when running outside a single docker
  network.

- Consider implementing automated verification that exercises the rotation controls and
  CSP reporting to catch regressions in authentication flow or log handling.
