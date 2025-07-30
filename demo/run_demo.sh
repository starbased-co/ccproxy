#!/bin/bash
# Run CCProxy demo with LiteLLM

echo "CCProxy LiteLLM Demo"
echo "==================="
echo ""
echo "This script demonstrates CCProxy integration with LiteLLM proxy."
echo ""

# Kill any existing LiteLLM processes on port 8888
lsof -i :8888 | grep -v COMMAND | awk '{print $2}' | xargs kill 2>/dev/null || true

# Set up environment
export LITELLM_CONFIG_PATH="demo_config.yaml"

echo "Starting LiteLLM proxy on port 8888..."
echo ""

# Start LiteLLM in the background
uv run litellm --config demo_config.yaml --port 8888 &
LITELLM_PID=$!

# Wait for startup
echo "Waiting for proxy to start..."
sleep 5

# Check if LiteLLM started successfully
if ! lsof -i :8888 >/dev/null 2>&1; then
    echo "Error: LiteLLM failed to start"
    exit 1
fi

echo ""
echo "LiteLLM proxy is running!"
echo "========================="
echo ""
echo "You can now:"
echo "1. Test routing with: curl http://localhost:8888/v1/chat/completions"
echo "2. Run the demo: cd .. && python demo/demo_requests.py"
echo "3. Check logs: tail -f litellm_new.log"
echo ""
echo "Press Ctrl+C to stop the proxy"
echo ""

# Keep the script running
wait $LITELLM_PID
