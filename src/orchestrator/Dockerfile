# Stage 1: Build Tailwind CSS
FROM node:20-alpine AS tailwind-builder
WORKDIR /build
COPY . .
RUN npm ci && npx tailwindcss -i ./styles/tailwind.css -o ./tailwind.output.css --minify

# Stage 2: Final Python image
FROM python:3.12-alpine
WORKDIR /app

COPY requirements.in requirements.txt ./
# Capture the dependency manifest hash so Docker invalidates this layer when
# pinned versions change.
RUN sha256sum requirements.txt > requirements.txt.sha \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt.sha

RUN apk add --no-cache su-exec curl \
    && adduser -D orchestrator \
    && mkdir -p /app/logs \
    && chown -R orchestrator:orchestrator /app/logs

COPY . .

# Remove any Python cache files that might have been copied (shouldn't happen due to .dockerignore, but be safe)
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /app -type f -name "*.pyo" -delete 2>/dev/null || true

# Copy compiled CSS only
COPY --from=tailwind-builder /build/tailwind.output.css ./static/tailwind.css

# Copy entrypoint script explicitly and ensure it's executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "80", "--no-access-log", "--log-level", "error", "--timeout-graceful-shutdown", "2"]
