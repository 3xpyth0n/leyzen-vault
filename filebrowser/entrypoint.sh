#!/bin/sh
set -eu
# Enable pipefail when supported so failures in pipelines surface immediately.
if set -o pipefail 2>/dev/null; then
  :
fi

log() {
  printf '%s\n' "[filebrowser-entrypoint] $*" >&2
}

require_var() {
  var_name="$1"
  eval "value=\"\${$var_name:-}\""
  if [ -z "$value" ]; then
    log "Environment variable $var_name is required. Set a strong value and rotate it periodically."
    exit 1
  fi
}

require_var FILEBROWSER_ADMIN_USER
require_var FILEBROWSER_ADMIN_PASSWORD

DATABASE_PATH="/database/filebrowser.db"
CONFIG_PATH="/config/settings.json"
STARTUP_DELAY="${FILEBROWSER_STARTUP_DELAY:-10}"
FILEBROWSER_BIN=${FILEBROWSER_BIN:-filebrowser}

filebrowser_cli() {
  "$FILEBROWSER_BIN" --config "$CONFIG_PATH" --database "$DATABASE_PATH" "$@"
}

update_admin_password() {
  if ! update_output=$(filebrowser_cli users update "$FILEBROWSER_ADMIN_USER" --password "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin 2>&1); then
    log "$1"
    printf '%s\n' "$update_output" >&2
    exit 1
  fi
}

mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$DATABASE_PATH")"

if [ "$STARTUP_DELAY" -gt 0 ]; then
  log "Waiting $STARTUP_DELAY seconds for Filebrowser to initialize."
  sleep "$STARTUP_DELAY"
fi

if [ ! -e "$CONFIG_PATH" ]; then
  log "Initializing Filebrowser configuration at $CONFIG_PATH."
  filebrowser_cli config init >/dev/null
fi

ensure_admin_account() {
  find_status=0
  find_output=$(filebrowser_cli users find "$FILEBROWSER_ADMIN_USER" 2>&1) || find_status=$?

  if [ "$find_status" -eq 0 ]; then
    log "Updating password for admin account '$FILEBROWSER_ADMIN_USER'."
    update_admin_password "Failed to update admin account '$FILEBROWSER_ADMIN_USER'."
    return
  fi

  if printf '%s' "$find_output" | grep -Fq "the resource does not exist"; then
    log "Admin account '$FILEBROWSER_ADMIN_USER' not present; creating via Filebrowser CLI."
    if ! create_output=$(filebrowser_cli users add "$FILEBROWSER_ADMIN_USER" "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin 2>&1); then
      if printf '%s' "$create_output" | grep -Fq "the resource already exists"; then
        log "Admin account '$FILEBROWSER_ADMIN_USER' was created concurrently; ensuring password is up to date."
        update_admin_password "Failed to update admin account '$FILEBROWSER_ADMIN_USER' after concurrent creation."
        return
      fi
      log "Failed to create admin account '$FILEBROWSER_ADMIN_USER'."
      printf '%s\n' "$create_output" >&2
      exit 1
    fi
    return
  fi

  log "Failed to query admin account '$FILEBROWSER_ADMIN_USER' (exit status $find_status)."
  printf '%s\n' "$find_output" >&2
  exit 1
}

ensure_admin_account

log "Starting Filebrowser."
exec "$FILEBROWSER_BIN" --config "$CONFIG_PATH" --database "$DATABASE_PATH" "$@"
