#!/usr/bin/zsh

# LiteLLM CCProxy API test script
# Tests LiteLLM proxy with Claude Code OAuth token
# All headers and JSON body general structure required to use the claude code oauth token

# Default to localhost:4000 for LiteLLM proxy
LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"

echo "Testing LiteLLM proxy at: $LITELLM_URL"
echo "Using model: default (should route to claude-sonnet-4-20250514)"
echo ""

curl \
  -H 'anthropic-dangerous-direct-browser-access: true' \
  -H 'anthropic-beta: oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14' \
  -H 'anthropic-version: 2023-06-01' \
  -H "Authorization: Bearer $(jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json)" \
  --compressed \
  -X POST "$LITELLM_URL/v1/messages" \
  -d '{
  "model": "default",
  "messages": [
    {"role": "user", "content": "Hello, Claude! This is a test through LiteLLM proxy."}
  ],
  "metadata": {
    "user_id": "user_19f2f4ee153d47fb2ef3e7954239ff16d3bff6daddd7cac0b1e7e3794fcaae80_account_a929b7ef-d758-4a98-b88e-07166e6c8537_session_34832e57-9b65-4df6-9604-60b9fc786bcb"
  },
  "max_tokens": 32000,
  "stream": true,
  "system": [
    {
      "type": "text",
      "text": "You are Claude Code, Anthropic'\''s official CLI for Claude.",
      "cache_control": {
        "type": "ephemeral"
      }
    },
    {
      "type": "text",
      "text": "\nYou are an interactive CLI tool that helps users with software engineering tasks...",
      "cache_control": {
        "type": "ephemeral"
      }
    }
  ]
}'
