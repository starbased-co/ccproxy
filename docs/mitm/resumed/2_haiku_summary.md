# 2_haiku_summary

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
x-stainless-helper-method: stream
accept-language: *
sec-fetch-mode: cors
accept-encoding: br, gzip, deflate
content-length: 718

{"model":"claude-3-5-haiku-20241022","max_tokens":512,"messages":[{"role":"user","content":"Are there any fields or properties related to caching or cache control?"}],"system":[{"type":"text","text":"Analyze if this message indicates a new conversation topic. If it does, extract a 2-3 word title that captures the new topic. Format your response as a JSON object with two fields: 'isNewTopic' (boolean) and 'title' (string, or null if isNewTopic is false). Only include these fields, no other text."}],"temperature":0,"metadata":{"user_id":"user_19f2f4ee153d47fb2ef3e7954239ff16d3bff6daddd7cac0b1e7e3794fcaae80_account_a929b7ef-d758-4a98-b88e-07166e6c8537_session_17662a42-afbd-4a84-9e8c-3933bb3541b2"},"stream":true}
```

## Response

```http
HTTP/1.1 200 OK
Date: Sat, 02 Aug 2025 20:27:08 GMT
Content-Type: text/event-stream; charset=utf-8
Transfer-Encoding: chunked
Connection: keep-alive
Cache-Control: no-cache
anthropic-ratelimit-unified-status: allowed
anthropic-ratelimit-unified-representative-claim: five_hour
anthropic-ratelimit-unified-fallback-percentage: 0.5
anthropic-ratelimit-unified-reset: 1754179200
request-id: req_011CRjWgRZmwdgK3Jk6StFKF
strict-transport-security: max-age=31536000; includeSubDomains; preload
anthropic-organization-id: 411f8cc6-c7b8-4a23-b579-da0dbdd68d9b
via: 1.1 google
cf-cache-status: DYNAMIC
X-Robots-Tag: none
Server: cloudflare
CF-RAY: 969050709e09cf2f-SJC

6af
event: message_start
data: {"type":"message_start","message":{"id":"msg_016YEW7iPVXRrAJ8YeaCeuWQ","type":"message","role":"assistant","model":"claude-3-5-haiku-20241022","content":[],"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":99,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":1,"service_tier":"standard"}}    }

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}  }

event: ping
data: {"type": "ping"}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"{"}              }

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"\n    "} }

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"\"isNewTopic"}   }

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"\": true,\n    "}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"\"title\": \""}  }

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Caching Properties"}          }

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"\"\n}"}      }

event: content_block_stop
data: {"type":"content_block_stop","index":0 }

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":27}        }

event: message_stop
data: {"type":"message_stop"            }


0

```