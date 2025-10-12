#!/bin/bash
set -e

if [ -t 1 ]; then
  RED="\033[0;31m"
  GREEN="\033[0;32m"
  YELLOW="\033[0;33m"
  BLUE="\033[0;34m"
  BOLD="\033[1m"
  RESET="\033[0m"
else
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  BOLD=""
  RESET=""
fi

# Fonctions d'affichage
info(){ printf "%b\n" "${BLUE}ℹ️  $1${RESET}"; }
success(){ printf "%b\n" "${GREEN}✅ $1${RESET}"; }
warn(){ printf "%b\n" "${YELLOW}⚠️  $1${RESET}"; }
error(){ printf "%b\n" "${RED}❌ $1${RESET}"; }

# Trap pour afficher l'erreur si le script échoue
trap 'error "Une erreur est survenue. Voir la commande précédemment exécutée."; exit 1' ERR

# Bannière
cat <<'BANNER'
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║          ██╗     ███████╗██╗   ██╗███████╗███████╗███╗   ██╗           ║   
║          ██║     ██╔════╝╚██╗ ██╔╝╚══███╔╝██╔════╝████╗  ██║           ║
║          ██║     █████╗   ╚████╔╝   ███╔╝ █████╗  ██╔██╗ ██║           ║
║          ██║     ██╔══╝    ╚██╔╝   ███╔╝  ██╔══╝  ██║╚██╗██║           ║
║          ███████╗███████╗   ██║   ███████╗███████╗██║ ╚████║           ║
║          ╚══════╝╚══════╝   ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═══╝           ║
║                                                                        ║
║                 Leyzen Vault PoC — Script d'installation               ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
BANNER

# Pré-requis root
if [ "$EUID" -ne 0 ]; then
    error "Ce script doit être exécuté avec les privilèges root."
    info "👉 Lancez : sudo ./install.sh"
    exit 1
fi

info "🔹 Vérification des prérequis…"

# Vérifie Python
if ! command -v python3 &>/dev/null; then
    error "Python3 n'est pas installé. Merci de l'installer."
    exit 1
else
    info "Python3 détecté : $(python3 --version 2>/dev/null)"
fi

# Vérifie pip
if ! command -v pip &>/dev/null; then
    info "🔹 pip non trouvé — installation via ensurepip..."
    python3 -m ensurepip --upgrade
    success "pip installé via ensurepip"
else
    info "pip détecté : $(pip --version 2>/dev/null)"
fi

# Vérifie Docker
if ! command -v docker &>/dev/null; then
    error "Docker n'est pas installé. Merci de l'installer."
    exit 1
else
    info "Docker détecté : $(docker --version 2>/dev/null)"
fi

# Vérifie Docker Compose (commande 'docker compose version')
if ! docker compose version &>/dev/null; then
    error "Docker Compose n'est pas installé ou accessible via 'docker compose'."
    exit 1
else
    info "Docker Compose détecté"
fi

info "🔹 Installation des packages Python requis…"
# garde la même commande que l'original
pip install --upgrade Flask docker --break-system-packages >/dev/null 2>&1 || {
    error "Échec de l’installation des dépendances Python."
    exit 1
}

success "Dépendances Python installées"

if [ ! -f service.sh ]; then
    cat <<'EOF' > service.sh
#!/bin/bash
set -e
PROJECT_DIR=$(dirname "$(realpath "$0")")
cd "$PROJECT_DIR"
echo "🚀 Starting Docker stack..."
docker compose up -d
echo "⚙️ Starting Vault Orchestrator..."
exec python3 ./orchestrator/vault_orchestrator.py
EOF
    chmod +x service.sh
    success "service.sh créé et rendu exécutable"
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="/etc/systemd/system/leyzen.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Leyzen Vault PoC - Orchestrateur et infrastructure Docker
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/service.sh start
ExecStop=$PROJECT_DIR/service.sh stop
Restart=always
RestartSec=5
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

info "🔹 Activation du service Leyzen…"
systemctl daemon-reload
systemctl enable leyzen

success "Installation terminée avec succès !"
echo ""
echo -e "\033[1mProchaine étape :\033[0m"
echo -e "  Pour démarrer le service : \033[0;33msudo systemctl start leyzen.service\033[0m"
echo -e "  Pour vérifier l'état :     \033[0;33msudo systemctl status leyzen.service\033[0m"
echo ""

