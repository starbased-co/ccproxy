#!/bin/bash
# Script to start LiteLLM proxy with CCProxy integration

echo "Starting LiteLLM proxy with CCProxy..."
echo "=================================="

# Export the CCProxy module path so LiteLLM can find it
export PYTHONPATH="${PYTHONPATH}:$(cd .. && pwd)/src"

# Config is expected to be at ./demo_config.yaml

echo "Using config: ./demo_config.yaml"
echo "Note: To enable debug mode, set debug: true in the ccproxy_settings section of the config"
echo ""
echo "Note: Make sure you have set the following environment variables:"
echo "  - ANTHROPIC_API_KEY"
echo "  - GOOGLE_API_KEY (optional, for large context)"
echo "  - PERPLEXITY_API_KEY (optional, for web search)"
echo ""
echo "Starting proxy server..."
echo "=================================="

# Start LiteLLM proxy with callbacks
litellm --config ./demo_config.yaml \
        --port 8000 \
        --debug \
        --callbacks "ccproxy.handler.CCProxyHandler"
