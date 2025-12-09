# syntax=docker/dockerfile:1
FROM python:3.12-alpine AS vault

WORKDIR /app

# Install system dependencies including Node.js and npm for Vue.js build
# su-exec is needed for dropping privileges to run as non-root user
RUN apk add --no-cache \
    curl \
    rsync \
    nodejs \
    npm \
    su-exec

# Copy requirements
COPY infra/vault/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Build Vue.js application first (for better Docker layer caching)
# Copy package files first for better caching - only rebuild if dependencies change
COPY src/vault/static/package.json src/vault/static/vite.config.js src/vault/static/index.html src/vault/static/vault.css /app/src/vault/static/
WORKDIR /app/src/vault/static
RUN npm install

# Copy Vue.js source files and build
# IMPORTANT: Copy all source files to ensure build uses latest code
COPY src/vault/static/src/ /app/src/vault/static/src/
# Remove any existing dist directory to ensure clean build
RUN rm -rf /app/src/vault/static/dist || true
# Build Vue.js application - dist/ will be created in /app/src/vault/static/dist/
RUN npm run build
# Verify build succeeded and dist directory exists
RUN test -d /app/src/vault/static/dist && echo "Build successful: dist directory exists" || (echo "ERROR: Build failed - dist directory not found" && exit 1)

# Return to app root
WORKDIR /app

# Copy application code (Python and other files)
# Note: Only copy src/vault/ - common/ will be mounted as read-only volume
# This ensures isolation: vault container only has vault code, not orchestrator or compose
COPY src/vault/ /app/src/vault/
# Remove any Python cache files that might have been copied (shouldn't happen due to .dockerignore, but be safe)
RUN find /app/src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/src -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /app/src -type f -name "*.pyo" -delete 2>/dev/null || true
# Docker automatically invalidates cache when source files change (content-based hashing)
# The RUN command below ensures cache invalidation by creating a marker based on file content
RUN find /app/src -type f \( -name "*.py" -o -name "*.js" -o -name "*.html" \) -exec sha256sum {} \; | sha256sum > /tmp/.src_hash 2>/dev/null || echo "0" > /tmp/.src_hash

# Create non-privileged user for running the application
RUN adduser -D -u 1000 vault

# Copy entrypoint and healthcheck script
COPY infra/vault/entrypoint.sh /usr/local/bin/vault-entrypoint.sh
COPY infra/vault/check_storage_mode.py /app/infra/vault/check_storage_mode.py
COPY infra/vault/healthcheck.py /app/infra/vault/healthcheck.py
RUN chmod +x /usr/local/bin/vault-entrypoint.sh && \
    chmod +x /app/infra/vault/check_storage_mode.py && \
    chmod +x /app/infra/vault/healthcheck.py

# Create data directories and set ownership
RUN mkdir -p /data /data-source && \
    chown -R vault:vault /data /data-source

# Set environment variables
# PYTHONPATH includes /app/src for vault code and /common for shared modules
# /common will be mounted as read-only volume at runtime
ENV PYTHONPATH=/app/src:/common
ENV FLASK_APP=vault.app:create_app

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=1s --timeout=2s --retries=2 --start-period=5s \
    CMD python3 /app/infra/vault/healthcheck.py || exit 1

# Entrypoint
ENTRYPOINT ["/usr/local/bin/vault-entrypoint.sh"]

# Run the application
# Use Uvicorn for ASGI support (enables SSE streaming)
# Use shell form to allow environment variable expansion with default value
# Note: Uvicorn uses --app-dir instead of --chdir, and we need to specify the module path
# --no-access-log: Disable access logs (200, 300, 400 responses)
# --log-level error: Only log errors and critical issues
# --timeout-graceful-shutdown: Reduce graceful shutdown timeout to speed up container stops
CMD cd /app/src && uvicorn vault.asgi:app --host 0.0.0.0 --port 80 --workers ${VAULT_WORKERS:-2} --no-access-log --log-level error --timeout-graceful-shutdown 2

