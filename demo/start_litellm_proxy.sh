#!/bin/bash
# Script to start LiteLLM proxy with CCProxy integration

echo "Starting LiteLLM proxy with CCProxy..."
echo "=================================="

# Export the CCProxy module path so LiteLLM can find it
export PYTHONPATH="${PYTHONPATH}:$(cd .. && pwd)/src"

# Set the config path
export LITELLM_CONFIG_PATH="./demo_config.yaml"

# Enable debug mode to see CCProxy routing decisions
export CCPROXY_DEBUG=true

echo "Using config: $LITELLM_CONFIG_PATH"
echo "CCProxy debug mode: enabled"
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
