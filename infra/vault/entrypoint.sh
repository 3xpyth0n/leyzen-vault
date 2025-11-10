#!/bin/sh
# Entrypoint script for the vault service.
#
# Purpose: Ensure proper permissions for data directories and drop privileges
# to run as a non-root user (vault) for security.
#
# This script:
# 1. Ensures the vault user owns the data directories (if running as root)
# 2. Synchronizes data from /data-source to /data if needed
# 3. Drops privileges to run as the vault user using su-exec

set -eu

VAULT_USER="vault"

log() {
  printf '%s\n' "[vault-entrypoint] $*" >&2
}

# If running as root, ensure vault user owns data directories
# This handles cases where volumes are mounted with root ownership
if [ "$(id -u)" = "0" ]; then
  if [ -d "/data" ]; then
    chown -R "${VAULT_USER}:${VAULT_USER}" /data 2>/dev/null || {
      log "Warning: Failed to change ownership of /data"
    }
  fi
  if [ -d "/data-source" ]; then
    chown -R "${VAULT_USER}:${VAULT_USER}" /data-source 2>/dev/null || {
      log "Warning: Failed to change ownership of /data-source"
    }
  fi
fi

# Synchronize from source to local storage if source exists
# Note: This will run as root if we're root, but files will be owned by vault user
# after the chown above. The sync happens before dropping privileges so we have
# the necessary permissions.
if [ -d "/data-source" ] && [ "$(ls -A /data-source 2>/dev/null)" ]; then
  log "Synchronizing from source to local storage..."
  rsync -a --update /data-source/ /data/ || {
    log "Warning: Failed to synchronize from source"
  }
  # Ensure vault user owns synced files
  if [ "$(id -u)" = "0" ]; then
    chown -R "${VAULT_USER}:${VAULT_USER}" /data 2>/dev/null || {
      log "Warning: Failed to change ownership of synced files"
    }
  fi
fi

# Drop privileges to vault user if running as root
if [ "$(id -u)" = "0" ]; then
  SU_EXEC_BIN=$(command -v su-exec 2>/dev/null || true)
  if [ -z "$SU_EXEC_BIN" ]; then
    log "Warning: su-exec not available; running command as root"
    log "Starting Leyzen Vault backend..."
    exec "$@"
  fi
  log "Starting Leyzen Vault backend..."
  exec "$SU_EXEC_BIN" "${VAULT_USER}:${VAULT_USER}" "$@"
else
  # Already running as non-root user
  log "Starting Leyzen Vault backend..."
  exec "$@"
fi

