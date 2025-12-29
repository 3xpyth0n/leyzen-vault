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

COPY --chown=orchestrator:orchestrator . .

# Copy compiled CSS only
COPY --chown=orchestrator:orchestrator --from=tailwind-builder /build/tailwind.output.css ./static/tailwind.css

# Copy entrypoint script explicitly and ensure it's executable
COPY --chown=orchestrator:orchestrator entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "80", "--no-access-log", "--log-level", "warning", "--timeout-graceful-shutdown", "2"]
