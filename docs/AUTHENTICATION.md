# Authentication Architecture and Differences

This document explains the authentication architecture and the differences between the Vault and Orchestrator implementations.

## Overview

Leyzen Vault uses different authentication mechanisms for the Vault application (SPA with Vue.js) and the Orchestrator dashboard (server-rendered application). While both use similar CAPTCHA and CSRF protection, the authentication flow and response handling differ to accommodate their respective architectures.

## Key Differences

### 1. `login_required()` Decorator

The `login_required()` decorator behaves differently in vault and orchestrator:

#### Vault (`src/vault/blueprints/utils.py`)

```python
def login_required(view: F) -> F:
    """Decorator to require authentication for a view.

    Returns 401 JSON error for unauthenticated requests.
    All frontend routing is handled by Vue.js, so no redirects to Flask templates.
    """
    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            from flask import jsonify
            return jsonify({"error": "Not authenticated"}), 401
        return view(*args, **kwargs)
    return decorated
```

**Behavior**: Returns a JSON error response (401) for unauthenticated requests.

**Reason**: The Vault application is a Single Page Application (SPA) built with Vue.js. The frontend handles routing and authentication state management. When an API endpoint returns 401, Vue Router intercepts it and redirects to the login page.

#### Orchestrator (`src/orchestrator/blueprints/utils.py`)

```python
def login_required(view: F) -> F:
    """Decorator to require authentication for a view.

    Redirects unauthenticated users to the login page with a next parameter.
    """
    @wraps(view)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return decorated
```

**Behavior**: Redirects unauthenticated users to the login page.

**Reason**: The Orchestrator dashboard is a server-rendered application using Flask templates. Server-side redirects are the standard pattern for this architecture, and the `next` parameter allows users to return to their intended destination after login.

### 2. `get_client_ip()` Function

Both implementations wrap the common `get_client_ip()` function to access application-specific settings:

#### Vault

```python
def get_client_ip() -> str | None:
    """Extract the real client IP address from request headers.

    Respects proxy trust count configuration to determine the correct
    IP address when behind a reverse proxy.
    """
    settings = _settings()
    return _get_client_ip_base(proxy_trust_count=settings.proxy_trust_count)
```

#### Orchestrator

```python
def get_client_ip() -> str | None:
    """Extract the real client IP address from request headers.

    Respects proxy trust count configuration to determine the correct
    IP address when behind a reverse proxy.
    """
    settings = _settings()
    return _get_client_ip_base(proxy_trust_count=settings.proxy_trust_count)
```

**Note**: While both functions are identical, they use different settings types (`VaultSettings` vs `Settings`), which is why they remain as separate wrappers.

### 3. `_settings()` Function

Both implementations provide a `_settings()` helper function that returns application-specific settings:

#### Vault

```python
def _settings() -> VaultSettings:
    """Get application settings from Flask config."""
    return current_app.config["VAULT_SETTINGS"]
```

#### Orchestrator

```python
def _settings() -> Settings:
    """Get application settings from Flask config.

    This is the standard way to access settings across all blueprints.
    Use this function instead of accessing current_app.config["SETTINGS"] directly.
    """
    return current_app.config["SETTINGS"]
```

**Reason**: Different settings types are used because Vault and Orchestrator have different configuration requirements (e.g., Vault has SMTP settings, Orchestrator has rotation settings).

## CAPTCHA Implementation

Both applications use the same CAPTCHA implementation from `common.captcha` and `common.captcha_helpers`, but with different route handling:

### Vault

- CAPTCHA routes: `/captcha-image`, `/captcha-refresh`
- Used for API authentication (JWT-based)
- Supports session-based fallback for API usage

### Orchestrator

- CAPTCHA routes: `/orchestrator/captcha-image`, `/orchestrator/captcha-refresh`
- Used for dashboard authentication (session-based)
- Always requires CSRF token validation

## Authentication Flow

### Vault Authentication Flow

1. User submits credentials via API endpoint (`/api/auth/login`)
2. CAPTCHA verification (required)
3. JWT token generation upon successful authentication
4. Frontend stores JWT token and uses it for subsequent requests
5. `login_required()` returns JSON 401 if token is invalid/missing
6. Vue Router handles redirects based on 401 responses

### Orchestrator Authentication Flow

1. User submits credentials via login form (`/orchestrator/login`)
2. CAPTCHA verification (required)
3. Session creation upon successful authentication
4. Server maintains session state
5. `login_required()` redirects to login page if session is invalid/missing
6. Flask handles redirects server-side

## Best Practices

When adding new authentication-related code:

1. **For Vault**: Use JSON responses and let Vue Router handle redirects
2. **For Orchestrator**: Use server-side redirects and Flask templates
3. **For Common Code**: Use the helper functions from `common.captcha_helpers` and `common.utils`
4. **For Settings**: Always use `_settings()` from the respective `utils.py` file, not `current_app.config` directly

## Migration Notes

If you need to add authentication to a new service:

- **API Service (like Vault)**: Use JSON responses and JWT tokens
- **Dashboard Service (like Orchestrator)**: Use session-based auth and server redirects
- **Shared Logic**: Put common authentication logic in `common.captcha_helpers` or `common.utils`

## References

- `src/vault/blueprints/utils.py` - Vault authentication utilities
- `src/orchestrator/blueprints/utils.py` - Orchestrator authentication utilities
- `src/common/captcha_helpers.py` - Shared CAPTCHA helper functions
- `src/common/utils.py` - Shared utility functions
- `src/common/captcha.py` - CAPTCHA generation and storage
