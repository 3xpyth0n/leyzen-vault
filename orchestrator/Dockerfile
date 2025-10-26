# Stage 1: Build Tailwind CSS
FROM node:20-alpine AS tailwind-builder
WORKDIR /build
COPY package*.json tailwind.config.js styles/ ./
RUN npm ci && npx tailwindcss -i ./tailwind.css -o ./tailwind.output.css --minify

# Stage 2: Final Python image
FROM python:3.11-alpine
WORKDIR /app
RUN apk add --no-cache docker-cli curl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Copy compiled CSS only
COPY --from=tailwind-builder /build/tailwind.output.css ./static/tailwind.css
CMD ["python3", "vault_orchestrator.py"]

