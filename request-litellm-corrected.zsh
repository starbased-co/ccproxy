#!/usr/bin/env zsh

LITELLM_BASE_URL="http://localhost:4000"
ANTHROPIC_API_KEY="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"

# Use the LiteLLM chat completions endpoint, not the Anthropic direct endpoint
http POST "$LITELLM_BASE_URL/chat/completions" \
  'connection: keep-alive' \
  'Accept: application/json' \
  'X-Stainless-Retry-Count: 0' \
  'X-Stainless-Timeout: 60' \
  'X-Stainless-Lang: js' \
  'X-Stainless-Package-Version: 0.55.1' \
  'X-Stainless-OS: Linux' \
  'X-Stainless-Arch: x64' \
  'X-Stainless-Runtime: node' \
  'X-Stainless-Runtime-Version: v24.4.1' \
  'anthropic-dangerous-direct-browser-access: true' \
  'anthropic-version: 2023-06-01' \
  "authorization: Bearer $ANTHROPIC_API_KEY" \
  'x-app: cli' \
  'User-Agent: claude-cli/1.0.62 (external, cli)' \
  'content-type: application/json' \
  'anthropic-beta: oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14' \
  'x-stainless-helper-method: stream' \
  'accept-language: *' \
  'sec-fetch-mode: cors' \
  'accept-encoding: br, gzip, deflate' <<<'{
    "model": "claude-3-5-haiku-20241022",
    "messages": [{"role": "user", "content": "hi claude"}],
    "max_tokens": 512,
    "temperature": 0,
    "stream": true
}'
