#!/bin/bash

# Run Claude Code with Anthropic Cache Analyzer
# Simple wrapper that connects Claude to the cache analyzer

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
PROXY_HOST="${PROXY_HOST:-localhost}"
PROXY_PORT="${PROXY_PORT:-4000}"
DASHBOARD_PORT=5555

echo -e "${BLUE}🔍 Running Claude Code with Cache Analysis${NC}"
echo "=========================================="
echo

# Check if cache analyzer is running
if curl -s "http://${PROXY_HOST}:${PROXY_PORT}/health" | grep -q "unified-cache-analyzer" 2>/dev/null; then
    echo -e "${GREEN}✓ Cache analyzer is running${NC}"
    echo -e "  Dashboard: http://${PROXY_HOST}:${DASHBOARD_PORT}"
elif nc -z "${PROXY_HOST}" "${PROXY_PORT}" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Proxy running but cache analyzer not detected${NC}"
else
    echo -e "${RED}✗ Cache analyzer is not running${NC}"
    echo
    echo "Start it with: ./start.sh"
    echo
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo
echo -e "${GREEN}Configuration:${NC}"
echo "  ANTHROPIC_BASE_URL=http://${PROXY_HOST}:${PROXY_PORT}"
echo "  ✓ MCP servers will work normally"
echo "  ✓ Only Anthropic API calls will be analyzed"
echo

# Set the Anthropic base URL to our proxy
export ANTHROPIC_BASE_URL="http://${PROXY_HOST}:${PROXY_PORT}"

# Run Claude Code with any arguments passed to this script
exec claude "$@"