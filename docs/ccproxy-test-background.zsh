#!/usr/bin/zsh
# CCProxy Background Model Test
# This tests the background model routing by using claude-3-5-haiku model name

curl \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -X POST "http://127.0.0.1:4000/v1/messages" \
  -d '{
      "model": "claude-3-5-haiku-20241022",
      "messages": [
        {"role": "user", "content": "What is 2+2?"}
      ],
      "max_tokens": 50,
      "stream": false
    }'
