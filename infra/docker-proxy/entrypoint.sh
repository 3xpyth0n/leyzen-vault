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
                    log "[docker-proxy] Created group '${TEMP_GROUP}' with GID ${SOCK_GID} for Docker socket access"
                else
                    # If creation failed, check again (maybe another process created it)
                    EXISTING_GROUP=$(find_group_by_gid "$SOCK_GID")
                    if [ -z "$EXISTING_GROUP" ]; then
                        log "[docker-proxy] WARNING: Failed to create group with GID ${SOCK_GID} and no existing group found"
                        log "[docker-proxy] WARNING: Docker socket access may fail. The default group '${DEFAULT_GROUP}' will be used"
                        log "[docker-proxy] WARNING: Please check Docker socket permissions if you encounter access issues"
                    else
                        log "[docker-proxy] Found existing group '${EXISTING_GROUP}' with GID ${SOCK_GID} (created by another process)"
                    fi
                fi
            fi

            # If we have a group (existing or newly created), add dockerproxy to it
            if [ -n "$EXISTING_GROUP" ]; then
                # Add dockerproxy user to the group (|| true to avoid errors if already member)
                if addgroup "$PROXY_USER" "$EXISTING_GROUP" >/dev/null 2>&1; then
                    log "[docker-proxy] Added user '${PROXY_USER}' to group '${EXISTING_GROUP}' for Docker socket access"
                else
                    log "[docker-proxy] User '${PROXY_USER}' is already a member of group '${EXISTING_GROUP}' (or addgroup failed)"
                fi
                TARGET_GROUP="$EXISTING_GROUP"
            else
                log "[docker-proxy] WARNING: Unable to match socket GID ${SOCK_GID} to any group; continuing with default group '${DEFAULT_GROUP}'"
                log "[docker-proxy] WARNING: Docker socket access may fail. Please verify Docker socket permissions"
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
    log "[docker-proxy] ERROR: su-exec not available; cannot drop privileges safely"
    log "[docker-proxy] This container requires su-exec to run securely as a non-root user"
    log "[docker-proxy] Please ensure su-exec is installed in the Docker image"
    exit 1
fi

# Build command arguments dynamically
# If the first argument is "uvicorn", inject the log-level from DOCKER_PROXY_LOG_LEVEL
if [ "$1" = "uvicorn" ]; then
    LOG_LEVEL="${DOCKER_PROXY_LOG_LEVEL:-warning}"
    # Convert to lowercase for uvicorn compatibility
    LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')
    
    # First, check if --log-level already exists in arguments
    HAS_LOG_LEVEL=false
    for arg in "$@"; do
        if [ "$arg" = "--log-level" ]; then
            HAS_LOG_LEVEL=true
            break
        fi
    done
    
    # Build new arguments array, replacing or adding --log-level
    TEMP_ARGS=""
    SKIP_NEXT=false
    ARG_COUNT=0
    
    for arg in "$@"; do
        ARG_COUNT=$((ARG_COUNT + 1))
        if [ "$SKIP_NEXT" = true ]; then
            SKIP_NEXT=false
            continue
        fi
        if [ "$arg" = "--log-level" ]; then
            # Replace existing --log-level with the one from environment
            TEMP_ARGS="$TEMP_ARGS --log-level $LOG_LEVEL"
            SKIP_NEXT=true
        else
            TEMP_ARGS="$TEMP_ARGS $arg"
            # If we've processed the second argument, haven't found --log-level yet, and it doesn't exist, insert it
            if [ "$HAS_LOG_LEVEL" = false ] && [ $ARG_COUNT -eq 2 ]; then
                TEMP_ARGS="$TEMP_ARGS --log-level $LOG_LEVEL"
            fi
        fi
    done
    
    # Rebuild the argument list
    eval "set -- $TEMP_ARGS"
fi

# Execute as dockerproxy user with the target group (either the socket's group or default)
exec "$SU_EXEC_BIN" "${PROXY_USER}:${TARGET_GROUP}" "$@"
