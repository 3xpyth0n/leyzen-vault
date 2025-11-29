FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apk add --no-cache curl su-exec

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup -S dockerproxy \
    && adduser -S -G dockerproxy -H dockerproxy

COPY . .

# Remove any Python cache files that might have been copied (shouldn't happen due to .dockerignore, but be safe)
RUN find /srv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /srv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /srv -type f -name "*.pyo" -delete 2>/dev/null || true

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2375

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "2375", "--workers", "2", "--timeout-keep-alive", "5", "--log-level", "info"]
