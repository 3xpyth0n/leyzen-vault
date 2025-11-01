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
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:2375", "--timeout", "0", "--graceful-timeout", "5", "--access-logfile", "-", "proxy:app"]
