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
SQLITE3_BIN=${SQLITE3_BIN:-sqlite3}
FILEBROWSER_BIN=${FILEBROWSER_BIN:-filebrowser}

mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$DATABASE_PATH")"

if [ "$STARTUP_DELAY" -gt 0 ]; then
  log "Waiting $STARTUP_DELAY seconds for Filebrowser to initialize."
  sleep "$STARTUP_DELAY"
fi

if [ ! -e "$CONFIG_PATH" ]; then
  log "Initializing Filebrowser configuration at $CONFIG_PATH."
  "$FILEBROWSER_BIN" config init --config "$CONFIG_PATH" --database "$DATABASE_PATH"
fi

HASHED_PASSWORD=$("$FILEBROWSER_BIN" hash "$FILEBROWSER_ADMIN_PASSWORD" | tr -d '\r\n')

install_sqlite3() {
  if command -v apk >/dev/null 2>&1; then
    log "Installing sqlite3 via apk."
    apk add --no-cache sqlite
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    log "Installing sqlite3 via apt-get."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y sqlite3
    apt-get clean
    rm -rf /var/lib/apt/lists/*
    return
  fi

  if command -v microdnf >/dev/null 2>&1; then
    log "Installing sqlite3 via microdnf."
    microdnf install -y sqlite
    microdnf clean all
    return
  fi

  log "sqlite3 is required but no supported package manager was found."
  exit 1
}

ensure_sqlite3() {
  if command -v "$SQLITE3_BIN" >/dev/null 2>&1; then
    return 0
  fi

  install_sqlite3

  if ! command -v "$SQLITE3_BIN" >/dev/null 2>&1; then
    log "sqlite3 installation succeeded but the binary '$SQLITE3_BIN' is still unavailable."
    exit 1
  fi
}

sqlite_escape() {
  printf "%s" "$1" | awk '{gsub(/\047/, "\047\047"); printf "%s", $0}'
}

current_hash() {
  ensure_sqlite3

  escaped_user=$(sqlite_escape "$FILEBROWSER_ADMIN_USER")
  "$SQLITE3_BIN" -batch -noheader "$DATABASE_PATH" \
    "SELECT password FROM users WHERE username = '$escaped_user' LIMIT 1;" \
    | tr -d '\r\n'
}

update_password_with_sqlite() {
  ensure_sqlite3

  escaped_user=$(sqlite_escape "$FILEBROWSER_ADMIN_USER")
  escaped_password=$(sqlite_escape "$HASHED_PASSWORD")

  changes_output=$(
    "$SQLITE3_BIN" -batch -noheader "$DATABASE_PATH" <<SQL
UPDATE users SET password = '$escaped_password' WHERE username = '$escaped_user';
SELECT changes();
SQL
  ) || return 1

  changes=$(printf '%s\n' "$changes_output" | tail -n1 | tr -d '\r\n')

  if [ -z "$changes" ]; then
    return 1
  fi

  if [ "$changes" = "0" ]; then
    return 2
  fi

  printf '%s' "$changes" | grep -q '^[1-9][0-9]*$'
}

ensure_admin_account() {
  existing_hash=$(current_hash)

  if [ -n "$existing_hash" ]; then
    if [ "$existing_hash" = "$HASHED_PASSWORD" ]; then
      log "Admin account '$FILEBROWSER_ADMIN_USER' already has the expected password hash."
      return
    fi

    log "Updating password for admin account '$FILEBROWSER_ADMIN_USER' via sqlite3."
    if update_password_with_sqlite; then
      return
    fi

    sqlite_status=$?
    if [ "$sqlite_status" -ne 2 ]; then
      log "Failed to update password for '$FILEBROWSER_ADMIN_USER' via sqlite3."
      exit 1
    fi
  fi

  log "Admin account '$FILEBROWSER_ADMIN_USER' not present; creating via Filebrowser CLI."
  "$FILEBROWSER_BIN" users add "$FILEBROWSER_ADMIN_USER" "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin --database "$DATABASE_PATH"

  if ! update_password_with_sqlite; then
    log "Failed to synchronize password hash for '$FILEBROWSER_ADMIN_USER' after account creation."
    exit 1
  fi
}

ensure_admin_account

final_hash=$(current_hash)
if [ "$final_hash" != "$HASHED_PASSWORD" ]; then
  log "Failed to set password for '$FILEBROWSER_ADMIN_USER' in $DATABASE_PATH."
  exit 1
fi

log "Starting Filebrowser."
exec "$FILEBROWSER_BIN" --config "$CONFIG_PATH" --database "$DATABASE_PATH" "$@"
