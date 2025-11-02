#!/bin/bash
set -e

# ───────────────────────────────────────────────
# Leyzen Vault CLI Installer
# Compiles the leyzenctl binary and installs it locally or globally.
# ───────────────────────────────────────────────

PROJECT_ROOT="$(dirname "$(realpath "$0")")"
CLI_DIR="$PROJECT_ROOT/cli"
OUTPUT_BIN="$PROJECT_ROOT/leyzenctl"

echo "───────────────────────────────────────────────"
echo " Leyzen Vault CLI Installer"
echo "───────────────────────────────────────────────"
echo

# Check Go installation
if ! command -v go >/dev/null 2>&1; then
    echo "❌ Go is not installed. Please install Go ≥1.22 first."
    echo "   Example: sudo apt install golang"
    exit 1
fi

# Step 1. Remove old binary if exists
if [ -f "$OUTPUT_BIN" ]; then
    echo "🧹 Removing previous binary..."
    rm -f "$OUTPUT_BIN"
fi

# Step 2. Compile leyzenctl
echo "⚙️  Compiling leyzenctl..."
cd "$CLI_DIR"
go mod tidy >/dev/null
go build -o "$OUTPUT_BIN"
cd "$PROJECT_ROOT"

if [ ! -f "$OUTPUT_BIN" ]; then
    echo "❌ Compilation failed: binary not found at $OUTPUT_BIN"
    exit 1
fi

echo
echo "✅ Binary built successfully:"
echo "   $OUTPUT_BIN"
echo

# Step 3. Optional global install
read -p "Would you like to install leyzenctl globally (requires sudo)? [y/N] " choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    echo "📦 Installing to /usr/local/bin..."
    sudo cp "$OUTPUT_BIN" /usr/local/bin/leyzenctl
    sudo chmod +x /usr/local/bin/leyzenctl
    echo "✅ Installed globally. You can now run it with: leyzenctl --help"
else
    echo "ℹ️  Skipped global install. Use it locally via:"
    echo "   $OUTPUT_BIN --help"
fi

echo
echo "───────────────────────────────────────────────"
echo " Leyzen Vault CLI installation completed."
echo "───────────────────────────────────────────────"
echo "🎯 You can now manage your stack with:"
echo "   ./leyzenctl start"
echo "   ./leyzenctl config wizard"
echo

