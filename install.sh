#!/bin/bash
set -e
set -o pipefail

# Color definitions
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

# Logging helpers
info(){ printf "%b\n" "${BLUE}ℹ️  $1${RESET}"; }
success(){ printf "%b\n" "${GREEN}✅ $1${RESET}"; }
warn(){ printf "%b\n" "${YELLOW}⚠️  $1${RESET}"; }
error(){ printf "%b\n" "${RED}❌ $1${RESET}"; }

trap 'error "An error occurred. See the last executed command."; exit 1' ERR

# Banner
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
║                  Leyzen Vault — Installation Script                    ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
BANNER

# Root privileges check
if [ "$EUID" -ne 0 ]; then
    error "This script must be run with root privileges."
    info "👉 Run: sudo ./install.sh"
    exit 1
fi

info "🔹 Checking prerequisites…"

# Check for Docker
if ! command -v docker &>/dev/null; then
    error "Docker is not installed. Please install it first."
    exit 1
else
    info "Docker detected: $(docker --version 2>/dev/null)"
fi

# Check for Docker Compose
if ! docker compose version &>/dev/null; then
    error "Docker Compose is not installed or not accessible via 'docker compose'."
    exit 1
else
    info "Docker Compose detected"
fi


# Check for systemd
if ! pidof systemd &>/dev/null; then
    error "Systemd not detected. This installation method requires a Linux host with systemd."
    exit 1
fi

if [ ! -f .env ]; then
    error "Missing .env file. Copy env.template to .env and configure strong credentials before installation."
    info "👉 Ensure FILEBROWSER_ADMIN_USER and FILEBROWSER_ADMIN_PASSWORD are long, random, and rotated regularly."
    exit 1
fi

get_env_value() {
    local key="$1"
    sed -n "s/^${key}=//p" .env | tail -n 1
}

ADMIN_USER=$(get_env_value "FILEBROWSER_ADMIN_USER")
ADMIN_PASS=$(get_env_value "FILEBROWSER_ADMIN_PASSWORD")

if [ -z "$ADMIN_USER" ] || [ -z "$ADMIN_PASS" ]; then
    error "FILEBROWSER_ADMIN_USER and FILEBROWSER_ADMIN_PASSWORD must be set in .env with strong, regularly rotated values."
    exit 1
fi

chmod +x service.sh
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="/etc/systemd/system/leyzen.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Leyzen Vault PoC - Orchestrator and Docker infrastructure
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/service.sh start
ExecStop=$PROJECT_DIR/service.sh stop
Restart=on-failure
KillMode=control-group
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

info "🔹 Enabling Leyzen service…"
systemctl daemon-reload
systemctl enable leyzen.service

success "Leyzen Vault successfully installed!"
echo ""
echo -e "${BOLD}Usage:${RESET}"
echo -e "  • Start service : ${YELLOW}sudo systemctl start leyzen${RESET}"
echo -e "  • Stop service  : ${YELLOW}sudo systemctl stop leyzen${RESET}"
echo -e "  • Logs          : ${YELLOW}journalctl -u leyzen -f${RESET}"
echo ""
info "Access the dashboard via: http://localhost:8080/orchestrator"
