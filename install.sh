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
# Step 2: Download CLI
# -----------------------------------------------------------------------------
echo -e "${BOLD}[2/4] Downloading leyzenctl binary...${NC}"

# Parse optional --version flag
VERSION_TAG=""
for arg in "$@"; do
    if [[ "$arg" == --version=* ]]; then
        VERSION_TAG="${arg#--version=}"
    fi
done

# Detect OS and ARCH
UNAME_S="$(uname -s || echo "")"
UNAME_M="$(uname -m || echo "")"
OS="linux"
ARCH="amd64"
case "$UNAME_S" in
    Linux) OS="linux" ;;
    Darwin) OS="darwin" ;;
    *) OS="linux" ;;
esac
case "$UNAME_M" in
    x86_64) ARCH="amd64" ;;
    amd64) ARCH="amd64" ;;
    arm64) ARCH="arm64" ;;
    aarch64) ARCH="arm64" ;;
    *) ARCH="amd64" ;;
esac

REPO="3xpyth0n/leyzen-vault"

resolve_latest_stable() {
    curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | sed -n 's/.*\"tag_name\": \"\([^\"]*\)\".*/\1/p' | head -n1
}

TAG="${VERSION_TAG}"
if [ -z "$TAG" ]; then
    STABLE="$(resolve_latest_stable || true)"
    if [ -n "$STABLE" ]; then
        TAG="${STABLE}-nightly"
    else
        TAG="nightly"
    fi
elif [ "$TAG" = "nightly" ]; then
    STABLE="$(resolve_latest_stable || true)"
    if [ -n "$STABLE" ]; then
        TAG="${STABLE}-nightly"
    fi
fi

ASSET_BASE="leyzenctl-${OS}-${ARCH}"
ASSET_VER="${ASSET_BASE}_${TAG}_${OS}_${ARCH}"
BIN_URL_VER="https://github.com/${REPO}/releases/download/${TAG}/${ASSET_VER}"
CHECKSUM_URL_VER="https://github.com/${REPO}/releases/download/${TAG}/checksums.txt"
BIN_URL_LEGACY="https://github.com/${REPO}/releases/download/${TAG}/${ASSET_BASE}"
CHECKSUM_URL_LEGACY="$CHECKSUM_URL_VER"

TMP_BIN="${OUTPUT_BIN}.tmp"
TMP_SUM="${PROJECT_ROOT}/checksums.tmp"

download_and_verify() {
    local url_bin="$1" url_sum="$2" name="$3"
    rm -f "$TMP_BIN" "$TMP_SUM"
    curl -fsSL -o "$TMP_BIN" "$url_bin" || return 1
    curl -fsSL -o "$TMP_SUM" "$url_sum" || return 1
    local expected actual
    expected="$(grep " ${name}$" "$TMP_SUM" | awk '{print $1}')"
    if [ -z "$expected" ]; then
        return 1
    fi
    actual="$(sha256sum "$TMP_BIN" | awk '{print $1}')"
    if [ "$expected" != "$actual" ]; then
        return 1
    fi
    return 0
}

resolve_asset_urls() {
    local tag="$1"
    local json
    json="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/tags/${tag}")" || return 1
    local bin_url sum_url
    bin_url="$(echo "$json" | sed -n 's/.*\"browser_download_url\": \"\([^"]*\)\".*/\1/p' | grep "/releases/download/${tag}/" | grep "leyzenctl-${OS}-${ARCH}" | head -n1)"
    sum_url="$(echo "$json" | sed -n 's/.*\"browser_download_url\": \"\([^"]*\)\".*/\1/p' | grep "/releases/download/${tag}/checksums.txt" | head -n1)"
    if [ -n "$bin_url" ] && [ -n "$sum_url" ]; then
        echo "${bin_url}|${sum_url}"
        return 0
    fi
    return 1
}

ASSET_CHOSEN_URLS="$(resolve_asset_urls "$TAG" || true)"
if [ -z "$ASSET_CHOSEN_URLS" ]; then
    if ! download_and_verify "$BIN_URL_VER" "$CHECKSUM_URL_VER" "$ASSET_VER"; then
        if ! download_and_verify "$BIN_URL_LEGACY" "$CHECKSUM_URL_LEGACY" "$ASSET_BASE"; then
            echo -e "${YELLOW}[WARN] Failed to download nightly or checksum mismatch. Falling back to latest stable...${NC}"
            STABLE="$(resolve_latest_stable || true)"
            if [ -z "$STABLE" ]; then
                echo -e "${RED}[ERROR] Unable to resolve latest stable release.${NC}"
                exit 1
            fi
            ASSET_CHOSEN_URLS="$(resolve_asset_urls "$STABLE" || true)"
            if [ -n "$ASSET_CHOSEN_URLS" ]; then
                CHOSEN_BIN_URL="${ASSET_CHOSEN_URLS%|*}"
                CHOSEN_SUM_URL="${ASSET_CHOSEN_URLS#*|*}"
                CHOSEN_NAME="$(basename "$CHOSEN_BIN_URL")"
                if ! download_and_verify "$CHOSEN_BIN_URL" "$CHOSEN_SUM_URL" "$CHOSEN_NAME"; then
                    echo -e "${RED}[ERROR] Download failed or checksum mismatch for ${CHOSEN_NAME}.${NC}"
                    exit 1
                fi
            else
                STABLE_ASSET_VER="${ASSET_BASE}_${STABLE}_${OS}_${ARCH}"
                STABLE_BIN_URL_VER="https://github.com/${REPO}/releases/download/${STABLE}/${STABLE_ASSET_VER}"
                STABLE_CHECKSUM_URL="https://github.com/${REPO}/releases/download/${STABLE}/checksums.txt"
                STABLE_BIN_URL_LEGACY="https://github.com/${REPO}/releases/download/${STABLE}/${ASSET_BASE}"
                if ! download_and_verify "$STABLE_BIN_URL_VER" "$STABLE_CHECKSUM_URL" "$STABLE_ASSET_VER"; then
                    if ! download_and_verify "$STABLE_BIN_URL_LEGACY" "$STABLE_CHECKSUM_URL" "$ASSET_BASE"; then
                        echo -e "${RED}[ERROR] Download failed or checksum mismatch for ${ASSET_BASE}.${NC}"
                        exit 1
                    fi
                fi
            fi
        fi
    fi
else
    CHOSEN_BIN_URL="${ASSET_CHOSEN_URLS%|*}"
    CHOSEN_SUM_URL="${ASSET_CHOSEN_URLS#*|*}"
    CHOSEN_NAME="$(basename "$CHOSEN_BIN_URL")"
    if ! download_and_verify "$CHOSEN_BIN_URL" "$CHOSEN_SUM_URL" "$CHOSEN_NAME"; then
        echo -e "${RED}[ERROR] Download failed or checksum mismatch for ${CHOSEN_NAME}.${NC}"
        exit 1
    fi
fi

mv -f "$TMP_BIN" "$OUTPUT_BIN"
chmod +x "$OUTPUT_BIN"
rm -f "$TMP_SUM"

echo -e "${GREEN}[OK] Binary downloaded and verified at:${NC} ${CYAN}$OUTPUT_BIN${NC}"
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
    # Architecture Choice
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
