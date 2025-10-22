#!/bin/bash
set -e

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
║                Leyzen Vault PoC — Installation Script                  ║
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

# Check Python
if ! command -v python3 &>/dev/null; then
    error "Python3 is not installed. Please install it first."
    exit 1
else
    info "Python3 detected: $(python3 --version 2>/dev/null)"
fi

# Check pip
if ! command -v pip &>/dev/null; then
    info "🔹 pip not found — installing via ensurepip..."
    python3 -m ensurepip --upgrade
    success "pip installed via ensurepip"
else
    info "pip detected: $(pip --version 2>/dev/null)"
fi

# Check Docker
if ! command -v docker &>/dev/null; then
    error "Docker is not installed. Please install it first."
    exit 1
else
    info "Docker detected: $(docker --version 2>/dev/null)"
fi

# Check Docker Compose (command 'docker compose version')
if ! docker compose version &>/dev/null; then
    error "Docker Compose is not installed or not accessible via 'docker compose'."
    exit 1
else
    info "Docker Compose detected"
fi

info "🔹 Installing required Python packages…"
pip install --upgrade Flask docker --break-system-packages >/dev/null 2>&1 || {
    error "Failed to install Python dependencies."
    exit 1
}

success "Python dependencies installed"

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
systemctl enable leyzen

success "Installation completed successfully!"
echo ""
echo -e "\033[1mNext steps:\033[0m"
echo -e "  To start the service: \033[0;33msudo systemctl start leyzen.service\033[0m"
echo -e "  To check status:      \033[0;33msudo systemctl status leyzen.service\033[0m"
echo ""

