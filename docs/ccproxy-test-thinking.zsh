#!/usr/bin/zsh
# CCProxy Thinking Model Test
# This tests the thinking model routing by including a thinking field

curl \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -X POST "http://127.0.0.1:4000/v1/messages" \
  -d '{
      "model": "default",
      "messages": [
        {"role": "user", "content": "Solve this step by step: What is the sum of all prime numbers less than 20?"}
      ],
      "max_tokens": 500,
      "stream": false,
      "think": true
    }'
