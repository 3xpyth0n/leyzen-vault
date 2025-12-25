#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# Color Definitions
# -----------------------------------------------------------------------------
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_ROOT="$(dirname "$(realpath "$0")")"
CLI_DIR="$PROJECT_ROOT/tools/cli"
OUTPUT_BIN="$PROJECT_ROOT/leyzenctl"

clear

echo -e "${BOLD}${BLUE}================================================================${NC}"
echo -e "${BOLD}${BLUE}   LEYZEN VAULT INSTALLER${NC}"
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
echo -e "${BOLD}[1/4] Checking prerequisites...${NC}"

if ! command -v go >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Go is not installed. Please install Go >=1.22 first.${NC}"
    echo -e "Example: ${CYAN}sudo apt install golang${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Go is installed.${NC}"

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Python 3 is not installed. Please install Python 3 first.${NC}"
    echo -e "Example: ${CYAN}sudo apt install python3${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Python 3 is installed.${NC}"

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker is not installed. Please install Docker first.${NC}"
    echo -e "See: https://docs.docker.com/engine/install/${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Docker is installed.${NC}"

if ! docker compose version >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker Compose (plugin) is not installed.${NC}"
    echo -e "${YELLOW}Note: 'docker-compose' (standalone) is not supported. Please install 'docker compose' plugin.${NC}"
    echo -e "See: https://docs.docker.com/compose/install/linux/${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Docker Compose is installed.${NC}"
echo

# -----------------------------------------------------------------------------
# Step 2: Build CLI
# -----------------------------------------------------------------------------
echo -e "${BOLD}[2/4] Building leyzenctl binary...${NC}"

# Remove old binary if exists
if [ -f "$OUTPUT_BIN" ]; then
    rm -f "$OUTPUT_BIN"
fi

cd "$CLI_DIR"
go mod tidy >/dev/null
go build -o "$OUTPUT_BIN"
cd "$PROJECT_ROOT"

if [ ! -f "$OUTPUT_BIN" ]; then
    echo -e "${RED}[ERROR] Compilation failed: binary not found at $OUTPUT_BIN${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Binary built successfully at:${NC} ${CYAN}$OUTPUT_BIN${NC}"
echo

# -----------------------------------------------------------------------------
# Step 3: Global Install (Optional)
# -----------------------------------------------------------------------------
echo -e "${BOLD}[3/4] System installation${NC}"
echo -ne "${YELLOW}Would you like to install leyzenctl globally (requires sudo)? [y/N] : ${NC}"
read -r choice

if [[ "$choice" =~ ^[Yy]$ ]]; then
    echo -e "Installing to /usr/local/bin..."
    sudo cp "$OUTPUT_BIN" /usr/local/bin/leyzenctl
    sudo chmod +x /usr/local/bin/leyzenctl
    sudo leyzenctl completion bash | sudo tee /etc/bash_completion.d/leyzenctl > /dev/null
    echo -e "${GREEN}[OK] Installed globally.${NC}"
else
    echo -e "${CYAN}[INFO] Skipped global install.${NC}"
fi
echo

# -----------------------------------------------------------------------------
# Step 4: Configuration Setup
# -----------------------------------------------------------------------------
echo -e "${BOLD}[4/4] Configuring environment...${NC}"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/env.template" "$PROJECT_ROOT/.env"

    # ---------------------------------------------------------
    # Marketing / Architecture Choice
    # ---------------------------------------------------------
    echo
    echo -e "${BOLD}${CYAN}FEATURE: Moving Target Defense (MTD)${NC}"
    echo -e "MTD periodically rotates backend containers to limit attack surface."
    echo -e "  ${GREEN}[YES]${NC} High Security. 5 containers. Auto-rotation enabled."
    echo -e "  ${YELLOW}[NO]${NC}  Simple Mode. 2 containers. Lightweight & stable. (Default)"
    echo

    echo -ne "${YELLOW}Would you like to enable Moving Target Defense? [y/N] : ${NC}"
    read -r mtd_choice

    # Default to false
    ORCH_ENABLED="false"
    if [[ "$mtd_choice" =~ ^[Yy]$ ]]; then
        ORCH_ENABLED="true"
    fi

    # Generate secrets
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -base64 32)
    ORCH_PASS=$(openssl rand -base64 12)

    # Update .env file using sed
    sed -i "s|SECRET_KEY=|SECRET_KEY=$SECRET_KEY|" "$PROJECT_ROOT/.env"
    sed -i "s|POSTGRES_PASSWORD=|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" "$PROJECT_ROOT/.env"
    sed -i "s|ORCH_PASS=|ORCH_PASS=$ORCH_PASS|" "$PROJECT_ROOT/.env"
    sed -i "s|ORCH_USER=|ORCH_USER=admin|" "$PROJECT_ROOT/.env"

    # Set Orchestrator Mode based on user choice
    # We use a different delimiter (#) here to handle the value safely
    sed -i "s|ORCHESTRATOR_ENABLED=false|ORCHESTRATOR_ENABLED=$ORCH_ENABLED|" "$PROJECT_ROOT/.env"

    echo -e "${GREEN}[OK] Configuration file (.env) created.${NC}"
    echo -e "${GREEN}[OK] Secure secrets generated automatically.${NC}"

    if [ "$ORCH_ENABLED" = "true" ]; then
        echo -e "${CYAN}[INFO] Mode: Orchestrator (MTD Enabled)${NC}"
        echo
        echo -e "${BOLD}Orchestrator Credentials (Save these!):${NC}"
        echo -e "  User:     ${CYAN}admin${NC}"
        echo -e "  Password: ${BOLD}${YELLOW}$ORCH_PASS${NC}"
    else
        echo -e "${CYAN}[INFO] Mode: Simple (Single Container) - Orchestrator disabled.${NC}"
    fi
else
    echo -e "${CYAN}[INFO] Configuration file (.env) already exists. Skipping generation.${NC}"
fi
echo

# -----------------------------------------------------------------------------
# Completion
# -----------------------------------------------------------------------------
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo -e "${BOLD}${GREEN}INSTALLATION COMPLETE${NC}"
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo

echo -ne "${YELLOW}Do you want to start Leyzen Vault now? [y/N] : ${NC}"
read -r start_choice

if [[ "$start_choice" =~ ^[Yy]$ ]]; then
    echo
    echo -e "${CYAN}[INFO] Starting Leyzen Vault...${NC}"
    ./leyzenctl start
else
    echo
    echo -e "You can start the stack later with:"
    echo -e "  ${BOLD}${CYAN}./leyzenctl start${NC}"
    echo
    echo -e "To open the interactive dashboard:"
    echo -e "  ${BOLD}${CYAN}./leyzenctl${NC}"
fi
echo
