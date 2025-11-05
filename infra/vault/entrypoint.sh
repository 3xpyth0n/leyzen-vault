#!/bin/sh
set -eu

log() {
  printf '%s\n' "[vault-entrypoint] $*" >&2
}

# Synchronize from source to local storage if source exists
if [ -d "/data-source" ] && [ "$(ls -A /data-source 2>/dev/null)" ]; then
  log "Synchronizing from source to local storage..."
  rsync -a --update /data-source/ /data/ || {
    log "Warning: Failed to synchronize from source"
  }
fi

log "Starting Leyzen Vault backend..."
exec "$@"

