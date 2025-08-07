#!/bin/bash

# Start Anthropic Cache Analyzer with Reverse Proxy
# Simple startup script that just works

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Anthropic Cache Analyzer${NC}"
echo "====================================="
echo

# Check if mitmproxy is installed
if ! command -v mitmdump &> /dev/null; then
    echo -e "${RED}Error: mitmproxy is not installed${NC}"
    echo "Install it with: pip install mitmproxy"
    exit 1
fi

# Check if Python packages are available
python3 -c "import flask, flask_cors" 2>/dev/null || {
    echo -e "${YELLOW}Installing required Python packages...${NC}"
    pip install flask flask-cors
}

# Port configuration
PROXY_PORT=${PROXY_PORT:-4000}
DASHBOARD_PORT=5555
WEB_PORT=8081

echo "Configuration:"
echo "  Proxy: http://localhost:$PROXY_PORT"
echo "  Cache Dashboard: http://localhost:$DASHBOARD_PORT"
echo "  Mitmweb Dashboard: http://localhost:$WEB_PORT"
echo

echo -e "${YELLOW}To use with Claude Code:${NC}"
echo
echo -e "  ${BLUE}export ANTHROPIC_BASE_URL=\"http://localhost:$PROXY_PORT\"${NC}"
echo -e "  ${BLUE}claude${NC}"
echo
echo "Or use the wrapper script: ./run_claude.sh"
echo

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${GREEN}Starting reverse proxy with cache analysis...${NC}"
echo "Press Ctrl+C to stop"
echo

# Run mitmweb in reverse proxy mode with our unified analyzer
mitmweb \
    --listen-port $PROXY_PORT \
    --web-port 8081 \
    --web-open-browser \
    --mode "reverse:https://api.anthropic.com" \
    --ssl-insecure \
    -s "$SCRIPT_DIR/cache_analyzer.py" \
    --set confdir="$HOME/.mitmproxy" \
    --set termlog_verbosity=info