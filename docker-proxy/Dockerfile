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

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2375

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "2375", "--workers", "2", "--timeout-keep-alive", "5", "--log-level", "info"]
