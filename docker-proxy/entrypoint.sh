#!/bin/sh
set -eu

SOCKET_PATH="${DOCKER_SOCKET_PATH:-/var/run/docker.sock}"
PROXY_USER="dockerproxy"
DEFAULT_GROUP="dockerproxy"
TARGET_GROUP="$DEFAULT_GROUP"

find_group_by_gid() {
    # BusyBox does not ship `getent`, so fall back to parsing /etc/group.
    awk -F: -v gid="$1" '$3 == gid {print $1; exit 0}' /etc/group
}

log() {
    printf '%s\n' "$1" >&2
}

if [ -S "$SOCKET_PATH" ]; then
    if SOCK_GID=$(stat -c '%g' "$SOCKET_PATH" 2>/dev/null); then
        if [ -n "$SOCK_GID" ]; then
            EXISTING_GROUP=$(find_group_by_gid "$SOCK_GID")

            if [ -z "$EXISTING_GROUP" ]; then
                TEMP_GROUP="dockersock"
                if addgroup -g "$SOCK_GID" "$TEMP_GROUP" >/dev/null 2>&1; then
                    EXISTING_GROUP="$TEMP_GROUP"
                else
                    EXISTING_GROUP=$(find_group_by_gid "$SOCK_GID")
                fi
            fi

            if [ -n "$EXISTING_GROUP" ]; then
                addgroup "$PROXY_USER" "$EXISTING_GROUP" >/dev/null 2>&1 || true
                TARGET_GROUP="$EXISTING_GROUP"
            else
                log "[docker-proxy] unable to match socket gid ${SOCK_GID}; continuing with default group"
            fi
        fi
    else
        log "[docker-proxy] failed to stat ${SOCKET_PATH}; continuing as ${PROXY_USER}:${DEFAULT_GROUP}"
    fi
else
    log "[docker-proxy] docker socket ${SOCKET_PATH} not present; running with default permissions"
fi

SU_EXEC_BIN=$(command -v su-exec 2>/dev/null || true)
if [ -z "$SU_EXEC_BIN" ]; then
    log "[docker-proxy] su-exec not available; running command as root"
    exec "$@"
fi

exec "$SU_EXEC_BIN" "${PROXY_USER}:${TARGET_GROUP}" "$@"
