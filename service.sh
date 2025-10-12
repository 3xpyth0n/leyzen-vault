#!/bin/bash
set -e

PROJECT_DIR=$(dirname "$(realpath "$0")")
cd "$PROJECT_DIR"

start() {
    echo "🚀 Starting Docker stack..."
    docker compose up -d

    echo "⚙️ Starting Vault Orchestrator..."
    # Lance l'orchestrateur Python en arrière-plan et garde le PID
    python3 ./orchestrator/vault_orchestrator.py &
    ORCH_PID=$!
    echo $ORCH_PID > "$PROJECT_DIR/orchestrator.pid"
    wait $ORCH_PID
}

stop() {
    echo "🛑 Stopping Leyzen..."
    docker compose down

    if [ -f "$PROJECT_DIR/orchestrator.pid" ]; then
        ORCH_PID=$(cat "$PROJECT_DIR/orchestrator.pid")
        if kill -0 $ORCH_PID 2>/dev/null; then
            kill $ORCH_PID
            echo "💀 Vault Orchestrator stopped (PID $ORCH_PID)"
        fi
        rm -f "$PROJECT_DIR/orchestrator.pid"
    else
        # Au cas où le fichier PID n'existe pas
        pkill -f vault_orchestrator.py || true
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    *) echo "Usage: $0 {start|stop|restart}"; exit 1 ;;
esac

