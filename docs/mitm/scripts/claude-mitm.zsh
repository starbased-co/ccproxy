#!/usr/bin/env zsh

# Get the directory of this script
SCRIPT_DIR="${0:A:h}"

# Start mitmweb in background with output redirected and filter
export NODE_EXTRA_CA_CERTS="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
export NODE_TLS_REJECT_UNAUTHORIZED=0
mitmweb --listen-host 127.0.0.1 --listen-port 58888 --web-open-browser \
    --set view_filter="~u https://api.anthropic.com/v1/messages" \
    --scripts "$SCRIPT_DIR/mitm_save_requests.py" \
    >/dev/null 2>&1 &
MITMWEB_PID=$!

# Wait for mitmweb to start
sleep 2

# Export proxy variables for claude
export HTTP_PROXY="http://127.0.0.1:58888"
export HTTPS_PROXY="http://127.0.0.1:58888"

# Function to cleanup on exit
cleanup() {
    echo "Shutting down mitmweb..."
    kill $MITMWEB_PID 2>/dev/null
    wait $MITMWEB_PID 2>/dev/null
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Run claude with all arguments
claude "$@"

# Cleanup will be called automatically via trap
