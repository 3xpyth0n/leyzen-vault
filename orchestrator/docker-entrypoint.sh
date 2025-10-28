#!/bin/sh
set -e

# Ensure the orchestrator user owns the log directory so it can write logs even
# when a pre-existing volume with root ownership is mounted.
if [ "$(id -u)" = "0" ]; then
    if [ -d /app/logs ]; then
        chown -R orchestrator:orchestrator /app/logs
    fi
    exec su-exec orchestrator "$@"
fi

exec "$@"
