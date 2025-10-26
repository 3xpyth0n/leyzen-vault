# Stage 1: Build Tailwind CSS
FROM node:20-alpine AS tailwind-builder
WORKDIR /build
COPY package*.json tailwind.config.js styles/ ./
RUN npm ci && npx tailwindcss -i ./tailwind.css -o ./tailwind.output.css --minify

# Stage 2: Final Python image
FROM python:3.11-alpine
WORKDIR /app
RUN apk add --no-cache docker-cli curl
COPY requirements.in requirements.txt ./
# Capture the dependency manifest hash so Docker invalidates this layer when
# pinned versions change.
RUN sha256sum requirements.txt > requirements.txt.sha \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt.sha
COPY . .

# Copy compiled CSS only
COPY --from=tailwind-builder /build/tailwind.output.css ./static/tailwind.css
CMD ["python3", "vault_orchestrator.py"]

