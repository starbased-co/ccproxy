#!/usr/bin/zsh
# CCProxy Large Context Test
# This tests the token count routing by sending a request that would exceed 60k tokens

# Create a large text (simulating ~70k tokens)
LARGE_TEXT=$(python3 -c "print('This is a test sentence. ' * 10000)")

curl \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -X POST "http://127.0.0.1:4000/v1/messages" \
  -d "{
      \"model\": \"default\",
      \"messages\": [
        {\"role\": \"user\", \"content\": \"Please summarize this text: $LARGE_TEXT\"}
      ],
      \"max_tokens\": 200,
      \"stream\": false
    }"
