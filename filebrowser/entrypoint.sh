#!/bin/sh
set -eu
# Enable pipefail when supported so failures in pipelines surface immediately.
if set -o pipefail 2>/dev/null; then
  :
fi

log() {
  printf '%s\n' "[filebrowser-entrypoint] $*" >&2
}

# --- Fix potential permission issues on mounted volumes ---
log "Fixing ownership on /config, /database, /srv if needed..."
if [ "$(id -u)" -eq 0 ]; then
  chown -R filebrowser:filebrowser /config /database /srv 2>/dev/null || true
  # Re-drop privileges to the filebrowser user
  exec su-exec filebrowser "$0" "$@"
fi
# -----------------------------------------------------------

ensure_writable_dir() {
  dir="$1"
  if [ ! -d "$dir" ]; then
    log "Directory $dir is missing; ensure the corresponding volume is present."
    exit 1
  fi

  tmp_file="$dir/.filebrowser-permission-test-$$"
  if ! (touch "$tmp_file" 2>/dev/null && rm -f "$tmp_file" 2>/dev/null); then
    log "Directory $dir must be writable by the filebrowser user. Adjust ownership or permissions on the mounted volume."
    exit 1
  fi
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
FILEBROWSER_BIN=${FILEBROWSER_BIN:-filebrowser}

filebrowser_cli() {
  NO_COLOR=1 "$FILEBROWSER_BIN" --config "$CONFIG_PATH" --database "$DATABASE_PATH" "$@"
}

update_admin_password() {
  if ! update_output=$(filebrowser_cli users update "$FILEBROWSER_ADMIN_USER" --password "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin 2>&1); then
    log "$1"
    printf '%s\n' "$update_output" >&2
    exit 1
  fi
}

mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$DATABASE_PATH")"

ensure_writable_dir /config
ensure_writable_dir /database
ensure_writable_dir /srv

if [ ! -e "$CONFIG_PATH" ]; then
  log "Initializing Filebrowser configuration at $CONFIG_PATH."
  filebrowser_cli config init >/dev/null
fi

ensure_admin_account() {
  if filebrowser_cli users find "$FILEBROWSER_ADMIN_USER" >/dev/null 2>&1; then
    log "Updating password for admin account '$FILEBROWSER_ADMIN_USER'."
    update_admin_password "Failed to update admin account '$FILEBROWSER_ADMIN_USER'."
    return
  fi

  log "Admin account '$FILEBROWSER_ADMIN_USER' not present; creating via Filebrowser CLI."
  if ! create_output=$(filebrowser_cli users add "$FILEBROWSER_ADMIN_USER" "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin 2>&1); then
    if printf '%s\n' "$create_output" | grep -Fq "resource already exists"; then
      log "Admin account '$FILEBROWSER_ADMIN_USER' already exists; ensuring password is up to date."
      update_admin_password "Failed to update admin account '$FILEBROWSER_ADMIN_USER' after detecting existing record."
      return
    fi

    if filebrowser_cli users find "$FILEBROWSER_ADMIN_USER" >/dev/null 2>&1; then
      log "Admin account '$FILEBROWSER_ADMIN_USER' detected after creation failure; ensuring password is up to date."
      update_admin_password "Failed to update admin account '$FILEBROWSER_ADMIN_USER' after verifying existence."
      return
    fi

    log "Failed to create admin account '$FILEBROWSER_ADMIN_USER'."
    printf '%s\n' "$create_output" >&2
    exit 1
  fi
}

ensure_admin_account

log "Starting Filebrowser."
exec "$FILEBROWSER_BIN" --config "$CONFIG_PATH" --database "$DATABASE_PATH" "$@"
