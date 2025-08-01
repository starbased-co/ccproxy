# Claude Code OAuth Authentication with LiteLLM

## Key Observations:

1. **OAuth Token in Authorization Header**: Claude Code uses an OAuth token (`sk-ant-oat01-...`) in the standard `Authorization: Bearer` format, not Anthropic's typical `x-api-key` header

2. **Multiple Beta Features**: The request includes `anthropic-beta: oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14`

3. **Special Headers Required**:
   - `anthropic-dangerous-direct-browser-access: true` (critical for OAuth)
   - Various Stainless SDK headers
   - `x-app: cli` for client identification

4. **Metadata with User Context**: Complex metadata structure with user_id, account, and session information

5. **Streaming Enabled**: Request expects streaming responses

## Comprehensive Plan for LiteLLM Adaptation:

### 1. **Configure Pass-Through Endpoint**
Create a dedicated pass-through endpoint that preserves all headers exactly:

```yaml
general_settings:
  pass_through_endpoints:
    - path: "/anthropic/v1/messages"
      target: "https://api.anthropic.com/v1/messages"
      forward_headers: true  # Forward ALL headers from client
      # Don't set any headers here - let them all pass through
```

### 2. **Alternative: Configure Standard Endpoint with Header Forwarding**
For using the standard `/v1/chat/completions` endpoint:

```yaml
general_settings:
  forward_client_headers_to_llm_api: true

model_list:
  - model_name: claude-3-5-haiku
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      # Don't set api_key here - let it come from client
      custom_llm_provider: anthropic
      stream: true
```

### 3. **Custom Hook for OAuth Token Handling**
Create a custom logger hook to ensure the OAuth token is properly forwarded:

```python
class OAuthPassthroughHandler(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # Check if Authorization header exists in the original request
        # Ensure it's passed to the LLM call
        # Add required headers like anthropic-dangerous-direct-browser-access
        return data
```

### 4. **Request Transformation Considerations**:
- **Preserve the Authorization header** as-is (don't transform to x-api-key)
- **Forward all Stainless headers** for proper SDK compatibility
- **Maintain the metadata structure** without modification
- **Ensure streaming capability** is preserved

### 5. **Testing Strategy**:
1. First test with pass-through endpoint to ensure all headers are forwarded
2. Verify OAuth token authentication works
3. Check that streaming responses function correctly
4. Validate metadata is preserved in logs/callbacks

### 6. **Potential Issues to Address**:
- LiteLLM might try to validate or transform the API key format
- The OAuth token might conflict with LiteLLM's own authentication
- Some headers might be filtered out by default
- Streaming might need special handling for OAuth-authenticated requests

## Working Request Example:

```bash
ANTHROPIC_BASE_URL="https://api.anthropic.com"
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
```
