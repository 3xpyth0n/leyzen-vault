#!/bin/bash
# Licensed under the Business Source License 1.1 (see LICENSE).
# Copyright (c) 2025 Saad Idrissi.
set -euo pipefail
IFS=$'\n\t'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="docker-compose.generated.yml"


now() {
    local msg="$1"
    echo -e "$(date '+%Y-%m-%d %H:%M:%S')  $msg"
}

ensure_manifest() {
    python3 compose/build.py
}

start() {
    ensure_manifest
    now "🚀 Starting Leyzen Docker stack..."
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
    now "✅ Leyzen started successfully."
}

stop() {
    ensure_manifest
    now "🛑 Stopping Leyzen..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans
    now "✅ Leyzen stopped."
}

build() {
    ensure_manifest
    now "🧱 Rebuilding containers..."
    docker compose -f "$COMPOSE_FILE" up -d --build --remove-orphans
    now "✅ Build completed and stack running."
}

status() {
    now "📊 Current container status:"
    docker ps --format "table {{.Names}}\t{{.RunningFor}}\t{{.Status}}\t{{.Ports}}"
}

usage() {
    cat <<EOF

Commands:
  build     🧱 Build or rebuild all containers, then start the stack.
             Use this when you modify Dockerfiles or dependencies.

  start     🚀 Start all services in detached mode.
             If containers don’t exist yet, they will be created automatically.

  stop      🛑 Stop and remove all running containers and networks.
             Volumes are preserved.

  restart   🔁 Restart the stack by stopping and starting it again.
             Useful after configuration changes.

  status    📊 Display the current state of all containers
             (running, exited, ports, etc.).

Examples:
  $0 start        # Start the stack
  $0 stop         # Stop all containers
  $0 build        # Rebuild everything
  $0 restart      # Restart the stack cleanly
  $0 status       # View container status
EOF
}

case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        ensure_manifest
        now "🔁 Restarting Leyzen..."
        docker compose -f "$COMPOSE_FILE" down --remove-orphans
        docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
        now "✅ Leyzen restarted."
        ;;
    build)
        build
        ;;
    status)
        status
        ;;
    *)
        usage
        exit 1
        ;;
esac

