#!/bin/bash
set -e

# Chemin vers le projet
PROJECT_DIR=$(dirname "$(realpath "$0")")
cd "$PROJECT_DIR"

# Fonction pour arrêter proprement Docker et le script
cleanup() {
    echo "🛑 Arrêt du service Leyzen…"
    docker compose down
    exit 0
}

# Capture SIGTERM et SIGINT (arrêt par systemd ou Ctrl+C)
trap cleanup SIGTERM SIGINT

echo "🚀 Starting Docker stack..."
docker compose up -d

echo "⚙️ Starting Vault Orchestrator..."
# Lance l'orchestrateur Python
python3 ./orchestrator/vault_orchestrator.py

# Si jamais Python se termine, on fait un cleanup
cleanup

