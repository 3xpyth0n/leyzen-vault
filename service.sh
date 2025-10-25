#!/bin/bash
set -e

PROJECT_DIR=$(dirname "$(realpath "$0")")
cd "$PROJECT_DIR"

start() {
    echo "🚀 Starting Docker stack..."
    docker compose up -d
}

stop() {
    echo "🛑 Stopping Leyzen..."
    docker compose down
}

case "$1" in
    start) clear; start ;;
    stop) clear; stop ;;
    restart) clear; stop; start ;;
    *) echo "Usage: $0 {start|stop|restart}"; exit 1 ;;
esac

