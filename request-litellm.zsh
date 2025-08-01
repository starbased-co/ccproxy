#!/usr/bin/env zsh

ANTHROPIC_BASE_URL="http://localhost:4000"
ANTHROPIC_API_KEY="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"

http POST "$ANTHROPIC_BASE_URL/v1/messages?beta=true" \
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
  'accept-encoding: br, gzip, deflate' <<<'{"model":"claude-3-5-haiku-20241022","max_tokens":512,"messages":[{"role":"user","content":"hi claude"}],"system":[{"type":"text","text":"Analyze if this message indicates a new conversation topic. If it does, extract a 2-3 word title that captures the new topic. Format your response as a JSON object with two fields: '"'"'isNewTopic'"'"' (boolean) and '"'"'title'"'"' (string, or null if isNewTopic is false). Only include these fields, no other text."}],"temperature":0,"metadata":{"user_id":"user_19f2f4ee153d47fb2ef3e7954239ff16d3bff6daddd7cac0b1e7e3794fcaae80_account_a929b7ef-d758-4a98-b88e-07166e6c8537_session_2978ad57-d800-4a88-85fb-490d108ed665"},"stream":true}'
