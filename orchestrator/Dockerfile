# Stage 1: Build Tailwind CSS
FROM node:20-alpine AS tailwind-builder
WORKDIR /build
COPY . .
RUN npm ci && npx tailwindcss -i ./styles/tailwind.css -o ./tailwind.output.css --minify

# Stage 2: Final Python image
FROM python:3.11-alpine
WORKDIR /app
RUN apk add --no-cache curl
COPY requirements.in requirements.txt ./
# Capture the dependency manifest hash so Docker invalidates this layer when
# pinned versions change.
RUN sha256sum requirements.txt > requirements.txt.sha \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt.sha
RUN apk add --no-cache su-exec \
    && adduser -D orchestrator \
    && mkdir -p /app/logs \
    && chown -R orchestrator:orchestrator /app
COPY . .

# Copy compiled CSS only
COPY --from=tailwind-builder /build/tailwind.output.css ./static/tailwind.css
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python3", "app.py"]
