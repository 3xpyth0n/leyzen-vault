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

# Check storage mode early to determine if synchronization is needed
STORAGE_MODE=""
if [ -f "/app/infra/vault/check_storage_mode.py" ] && command -v python3 >/dev/null 2>&1; then
  # Try to get storage mode from database using dedicated script
  # Capture stdout (mode) and stderr (errors) separately
  SCRIPT_OUTPUT=$(python3 /app/infra/vault/check_storage_mode.py 2>&1)
  STORAGE_MODE=$(echo "$SCRIPT_OUTPUT" | grep -v "^\[check_storage_mode\]" | head -n 1 || echo "")
  # Log any errors from the script
  SCRIPT_ERRORS=$(echo "$SCRIPT_OUTPUT" | grep "^\[check_storage_mode\]" || true)
  if [ -n "$SCRIPT_ERRORS" ]; then
    # Only log if it's not a connection error (database may not be ready yet)
    if ! echo "$SCRIPT_ERRORS" | grep -q "Failed to check storage mode after"; then
      log "Storage mode check: $SCRIPT_ERRORS"
    fi
  fi
fi

# Synchronize from source to local storage if source exists and not in S3-only mode
# Note: This will run as root if we're root, but files will be owned by vault user
# after the chown above. The sync happens before dropping privileges so we have
# the necessary permissions.
# In S3-only mode, skip synchronization as files are stored exclusively in S3.
if [ -d "/data-source" ]; then
  if [ "$STORAGE_MODE" != "s3" ] && [ "$(ls -A /data-source 2>/dev/null)" ]; then
    log "Synchronizing from source to local storage..."
    # Count files before sync for logging
    source_file_count=$(find /data-source -type f 2>/dev/null | wc -l)
    log "Found ${source_file_count} files in /data-source"
    
    rsync -a --update /data-source/ /data/ || {
      log "Error: Failed to synchronize from source (exit code: $?)"
      log "This may indicate a permission or filesystem issue"
    }
    
    # Count files after sync
    data_file_count=$(find /data -type f 2>/dev/null | wc -l)
    log "Synchronized ${data_file_count} files to /data"
    
    # Ensure vault user owns synced files
    if [ "$(id -u)" = "0" ]; then
      chown -R "${VAULT_USER}:${VAULT_USER}" /data 2>/dev/null || {
        log "Warning: Failed to change ownership of synced files"
      }
    fi
  elif [ "$STORAGE_MODE" = "s3" ]; then
    # S3-only mode is enabled: always display message regardless of volume contents
    log "S3-only mode is enabled. No files will be written to local disk."
    log "Note: You can modify this setting from the admin interface, Integrations tab."
  elif [ ! "$(ls -A /data-source 2>/dev/null)" ]; then
    # Empty directory in local/hybrid mode
    log "Source directory /data-source exists but is empty"
    log "This is normal on first startup or if no files have been promoted yet"
  fi
else
  log "Warning: /data-source directory does not exist"
  log "Persistent storage volume may not be mounted correctly"
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

