#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"


now() {
    local msg="$1"
    echo -e "$(date '+%Y-%m-%d %H:%M:%S')  $msg"
}

start() {
    now "🚀 Starting Leyzen Docker stack..."
    docker compose up -d --remove-orphans
    now "✅ Leyzen started successfully."
}

stop() {
    now "🛑 Stopping Leyzen..."
    docker compose down --remove-orphans
    now "✅ Leyzen stopped."
}

build() {
    now "🧱 Rebuilding containers..."
    docker compose up -d --build --remove-orphans
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
        stop
        start
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

