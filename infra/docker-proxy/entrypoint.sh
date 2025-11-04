#!/bin/sh
# Entrypoint script for the docker-proxy service.
#
# Purpose: Dynamically configure the dockerproxy user to access the Docker socket
# by detecting the socket's group ownership and adding the user to that group.
# This allows the service to run as a non-root user while still accessing Docker.
#
# Why this complexity? The Docker socket's group ownership varies across different
# Docker installations and host configurations. Some systems use the "docker" group,
# others use a numeric GID, and some may have no matching group. This script handles
# all cases by:
# 1. Detecting the socket's group ID (GID)
# 2. Finding or creating a group with that GID
# 3. Adding the dockerproxy user to that group
# 4. Executing the service as the dockerproxy user with the correct group

set -eu

SOCKET_PATH="${DOCKER_SOCKET_PATH:-/var/run/docker.sock}"
PROXY_USER="dockerproxy"
DEFAULT_GROUP="dockerproxy"
TARGET_GROUP="$DEFAULT_GROUP"

# Find a group name by its GID. BusyBox (used in Alpine images) doesn't ship `getent`,
# so we parse /etc/group directly using awk.
find_group_by_gid() {
    awk -F: -v gid="$1" '$3 == gid {print $1; exit 0}' /etc/group
}

log() {
    printf '%s\n' "$1" >&2
}

# Attempt to detect and configure Docker socket access
if [ -S "$SOCKET_PATH" ]; then
    # Get the socket's group ID
    if SOCK_GID=$(stat -c '%g' "$SOCKET_PATH" 2>/dev/null); then
        if [ -n "$SOCK_GID" ]; then
            # Try to find an existing group with this GID
            EXISTING_GROUP=$(find_group_by_gid "$SOCK_GID")

            # If no group exists with this GID, try to create one
            if [ -z "$EXISTING_GROUP" ]; then
                TEMP_GROUP="dockersock"
                # Attempt to create a group with the socket's GID
                # This may fail if the GID is already in use by another group
                if addgroup -g "$SOCK_GID" "$TEMP_GROUP" >/dev/null 2>&1; then
                    EXISTING_GROUP="$TEMP_GROUP"
                else
                    # If creation failed, check again (maybe another process created it)
                    EXISTING_GROUP=$(find_group_by_gid "$SOCK_GID")
                fi
            fi

            # If we have a group (existing or newly created), add dockerproxy to it
            if [ -n "$EXISTING_GROUP" ]; then
                # Add dockerproxy user to the group (|| true to avoid errors if already member)
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

# Execute the service as the dockerproxy user using su-exec
# su-exec is a minimal setuid tool that's safer than su for dropping privileges
SU_EXEC_BIN=$(command -v su-exec 2>/dev/null || true)
if [ -z "$SU_EXEC_BIN" ]; then
    log "[docker-proxy] su-exec not available; running command as root"
    exec "$@"
fi

# Execute as dockerproxy user with the target group (either the socket's group or default)
exec "$SU_EXEC_BIN" "${PROXY_USER}:${TARGET_GROUP}" "$@"
