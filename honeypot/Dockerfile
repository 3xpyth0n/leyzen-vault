FROM python:3.13-slim

WORKDIR /app

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy app
COPY . /app

# Install Python deps (Flask, gunicorn)
RUN pip install --no-cache-dir flask gunicorn werkzeug

# Ensure log dir exists
RUN mkdir -p /app && touch /app/honeypot_requests.jsonl && chmod 666 /app/honeypot_requests.jsonl

# Expose Flask port
EXPOSE 5000

# Start with gunicorn supporting PROXY protocol and binding on 0.0.0.0:5000
# 'app:app' assumes honeypot/app.py exposes "app"
CMD gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 120 --forwarded-allow-ips="*" app:app

