# 1_haiku_quota

## Request

```http
POST /v1/messages?beta=true HTTP/1.1
host: api.anthropic.com
connection: keep-alive
Accept: application/json
X-Stainless-Retry-Count: 0
X-Stainless-Timeout: 60
X-Stainless-Lang: js
X-Stainless-Package-Version: 0.55.1
X-Stainless-OS: Linux
X-Stainless-Arch: x64
X-Stainless-Runtime: node
X-Stainless-Runtime-Version: v24.4.1
anthropic-dangerous-direct-browser-access: true
anthropic-version: 2023-06-01
authorization: Bearer $CLAUDE_CODE_OAUTH_TOKEN
x-app: cli
User-Agent: claude-cli/1.0.62 (external, cli)
content-type: application/json
anthropic-beta: oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14
accept-language: *
sec-fetch-mode: cors
accept-encoding: br, gzip, deflate
content-length: 284

{"model":"claude-3-5-haiku-20241022","max_tokens":1,"messages":[{"role":"user","content":"quota"}],"metadata":{"user_id":"user_19f2f4ee153d47fb2ef3e7954239ff16d3bff6daddd7cac0b1e7e3794fcaae80_account_a929b7ef-d758-4a98-b88e-07166e6c8537_session_17662a42-afbd-4a84-9e8c-3933bb3541b2"}}
```

## Response

```http
HTTP/1.1 200 OK
Date: Sat, 02 Aug 2025 20:27:04 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive
anthropic-ratelimit-unified-status: allowed
anthropic-ratelimit-unified-representative-claim: five_hour
anthropic-ratelimit-unified-fallback-percentage: 0.5
anthropic-ratelimit-unified-reset: 1754179200
request-id: req_011CRjWg8gmowrHs23BDytyU
strict-transport-security: max-age=31536000; includeSubDomains; preload
anthropic-organization-id: 411f8cc6-c7b8-4a23-b579-da0dbdd68d9b
via: 1.1 google
cf-cache-status: DYNAMIC
X-Robots-Tag: none
Server: cloudflare
CF-RAY: 969050580df5cf2f-SJC

14a
{"id":"msg_01GWhTRMn4BjPrXcKZLSv4aS","type":"message","role":"assistant","model":"claude-3-5-haiku-20241022","content":[{"type":"text","text":"Here"}],"stop_reason":"max_tokens","stop_sequence":null,"usage":{"input_tokens":8,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":1,"service_tier":"standard"}}
0

```