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
# Note: .dockerignore excludes src/vault/static/dist/ to prevent overwriting the build
# Copy the entire src directory, but dist/ is excluded by .dockerignore
COPY src/ /app/src/
# Docker automatically invalidates cache when source files change (content-based hashing)
# The RUN command below ensures cache invalidation by creating a marker based on file content
RUN find /app/src -type f \( -name "*.py" -o -name "*.js" -o -name "*.html" \) -exec sha256sum {} \; | sha256sum > /tmp/.src_hash 2>/dev/null || echo "0" > /tmp/.src_hash

# Create non-privileged user for running the application
RUN adduser -D -u 1000 vault

# Copy entrypoint
COPY infra/vault/entrypoint.sh /usr/local/bin/vault-entrypoint.sh
RUN chmod +x /usr/local/bin/vault-entrypoint.sh

# Create data directories and set ownership
RUN mkdir -p /data /data-source && \
    chown -R vault:vault /data /data-source /app

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_APP=vault.app:create_app

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=1s --timeout=5s --retries=10 \
    CMD curl -f http://localhost/healthz || exit 1

# Entrypoint
ENTRYPOINT ["/usr/local/bin/vault-entrypoint.sh"]

# Run the application
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:80", "--workers", "2", "--timeout", "120", "--chdir", "/app/src", "vault.app:application"]

