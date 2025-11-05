# syntax=docker/dockerfile:1
FROM python:3.11-alpine AS vault

WORKDIR /app

# Install system dependencies
RUN apk add --no-cache \
    curl \
    rsync

# Copy requirements
COPY infra/vault/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/

# Copy entrypoint
COPY infra/vault/entrypoint.sh /usr/local/bin/vault-entrypoint.sh
RUN chmod +x /usr/local/bin/vault-entrypoint.sh

# Create data directories
RUN mkdir -p /data /data-source && \
    chmod 755 /data /data-source

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

