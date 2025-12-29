#!/bin/sh
# PostgreSQL initialization script
# Creates the database if it doesn't exist

set -eu

POSTGRES_USER="${POSTGRES_USER:-leyzen}"
POSTGRES_DB="${POSTGRES_DB:-leyzen_vault}"

log() {
  printf '%s\n' "[postgres-init] $*" >&2
}


until pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
  log "Waiting for PostgreSQL to be ready..."
  sleep 1
done

log "PostgreSQL is ready"

# Check if database exists (connect to 'postgres' database to list all databases)
# Use PGDATABASE to avoid defaulting to user's name
export PGDATABASE=postgres
if psql -U "$POSTGRES_USER" -d postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$POSTGRES_DB"; then
  log "Database '$POSTGRES_DB' already exists"
else
  log "Creating database '$POSTGRES_DB'..."
  # Use PGDATABASE to avoid defaulting to user's name when creating database
  PGDATABASE=postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB" 2>/dev/null || {
    log "Failed to create database (may already exist or insufficient permissions)"
  }
  log "Database '$POSTGRES_DB' created successfully"
fi

log "Initialization complete"
