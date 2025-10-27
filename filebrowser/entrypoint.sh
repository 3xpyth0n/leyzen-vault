#!/bin/sh
set -eu

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

USER_LIST=$(filebrowser users list 2>/dev/null || true)
USER_ID=$(printf '%s\n' "$USER_LIST" | awk -v user="$FILEBROWSER_ADMIN_USER" 'NR>1 && $2==user {print $1; exit}')

rm -f database.db
filebrowser config init
if [ -z "$USER_ID" ]; then
  log "Creating admin account '$FILEBROWSER_ADMIN_USER'."
  filebrowser users add "$FILEBROWSER_ADMIN_USER" "$FILEBROWSER_ADMIN_PASSWORD" --perm.admin
else
  log "Updating password for admin account '$FILEBROWSER_ADMIN_USER' (id: $USER_ID)."
  filebrowser users update "$USER_ID" --password "$FILEBROWSER_ADMIN_PASSWORD"
fi

log "Starting Filebrowser."
exec filebrowser
