#!/bin/bash
# Script to audit Python dependencies for security vulnerabilities
#
# This script uses pip-audit to check all requirements.txt files for known
# security vulnerabilities. It should be run regularly and integrated into CI/CD.
#
# Usage:
#   ./tools/audit-dependencies.sh
#
# Requirements:
#   - pip-audit must be installed: pip install pip-audit
#   - Python virtual environment (optional but recommended)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pip-audit is installed
if ! command -v pip-audit &> /dev/null; then
    echo -e "${RED}Error: pip-audit is not installed.${NC}"
    echo "Install it with: pip install pip-audit"
    echo "Or use a virtual environment: python3 -m venv venv && source venv/bin/activate && pip install pip-audit"
    exit 1
fi

echo "Auditing Python dependencies for security vulnerabilities..."
echo ""

# List of requirements files to audit
REQUIREMENTS_FILES=(
    "$REPO_ROOT/infra/vault/requirements.txt"
    "$REPO_ROOT/src/orchestrator/requirements.txt"
    "$REPO_ROOT/infra/docker-proxy/requirements.txt"
)

FAILED=0
TOTAL_VULNERABILITIES=0

# Audit each requirements file
for req_file in "${REQUIREMENTS_FILES[@]}"; do
    if [ ! -f "$req_file" ]; then
        echo -e "${YELLOW}Warning: $req_file not found, skipping...${NC}"
        continue
    fi
    
    echo -e "${GREEN}Auditing: $req_file${NC}"
    
    # Run pip-audit and capture output
    if pip-audit -r "$req_file" --format=json > /tmp/pip-audit-output.json 2>&1; then
        # Check if there are any vulnerabilities
        VULN_COUNT=$(python3 -c "import json; data = json.load(open('/tmp/pip-audit-output.json')); print(len(data.get('vulnerabilities', [])))" 2>/dev/null || echo "0")
        
        if [ "$VULN_COUNT" -gt 0 ]; then
            echo -e "${RED}Found $VULN_COUNT vulnerability/vulnerabilities${NC}"
            pip-audit -r "$req_file" --format=text
            FAILED=1
            TOTAL_VULNERABILITIES=$((TOTAL_VULNERABILITIES + VULN_COUNT))
        else
            echo -e "${GREEN}No vulnerabilities found${NC}"
        fi
    else
        # If JSON format fails, try text format
        if pip-audit -r "$req_file" --format=text 2>&1 | grep -q "vulnerability"; then
            echo -e "${RED}Vulnerabilities found (see output above)${NC}"
            FAILED=1
        else
            echo -e "${GREEN}No vulnerabilities found${NC}"
        fi
    fi
    echo ""
done

# Summary
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All dependencies audited successfully. No vulnerabilities found.${NC}"
    exit 0
else
    echo -e "${RED}✗ Audit failed. Found $TOTAL_VULNERABILITIES total vulnerability/vulnerabilities.${NC}"
    echo ""
    echo "To fix vulnerabilities:"
    echo "1. Review the vulnerabilities listed above"
    echo "2. Update affected packages in requirements.txt to patched versions"
    echo "3. Run tests to ensure compatibility"
    echo "4. Re-run this script to verify fixes"
    exit 1
fi

