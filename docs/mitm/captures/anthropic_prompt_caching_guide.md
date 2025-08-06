# Anthropic Prompt Caching Guide

## 1. What Prompt Caching Is and How It Works

Prompt caching is a performance and cost-saving mechanism that allows Claude to "remember" the processed result of the initial part of a prompt, avoiding re-calculation on subsequent API calls within a conversation.

**How it works:**
1. **First API Call (Cache Creation):** Send a prompt with a `cache_control` marker. Claude processes all tokens up to that marker and stores the resulting internal state (the "KV cache"). You are billed for all tokens.
2. **Subsequent API Calls (Cache Read):** Send a new prompt beginning with the *exact same* sequence of cached tokens. Claude retrieves the saved state and only processes *new* tokens. You are only billed for new tokens.

Most effective for conversations with long, static prefixes (system prompts, few-shot examples, RAG documents).

## 2. How to Use `cache_control`

Enable caching by adding a `cache_control` object to your `messages` array:

- **Placement:** After a message with `role: "user"`
- **Structure:** JSON object with `type: "ephemeral"`

Example API call structure:

```json
{
  "model": "claude-3-opus-20240229",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": "You are a helpful assistant that specializes in the history of the Roman Empire..."
    },
    {
      "role": "assistant",
      "content": "Understood. I am Cassius, your expert on the Roman Empire."
    },
    {
      "role": "user",
      "content": "Who was the first emperor?"
    },
    {
      "role": "cache_control",
      "type": "ephemeral"
    },
    {
      "role": "assistant",
      "content": "As Cassius, I can tell you that the first Roman Emperor was Augustus."
    },
    {
      "role": "user",
      "content": "Tell me more about his reign."
    }
  ]
}
```

## 3. Best Practices for Cache Placement

**The Golden Rule:** Cache the largest, most static prefix of your conversation.

### RAG (Retrieval-Augmented Generation)
- **Ideal Use Case:** Cache thousands of tokens of retrieved context
- **Placement:** After the first user question, caching the massive system prompt and initial query

```json
"messages": [
  {
    "role": "user",
    "content": "Please answer my question based on the following document: <... 5000 tokens of text ...>"
  },
  { "role": "cache_control", "type": "ephemeral" }
]
```

### Complex Persona or Few-Shot Prompting
- **Use Case:** Detailed instructions, persona, and multiple examples
- **Placement:** After full instruction set has been provided and acknowledged

### Anti-Pattern
Avoid placing cache too early if important context is established in later turns. Value scales with size of cached prefix.

## 4. How Caching Affects Token Usage and Costs

| API Call | What You Send | What You Are Billed For |
|----------|---------------|-------------------------|
| **Cache Creation** | Full prefix + `cache_control` block | **All input tokens** (`cache_creation_input_tokens`) |
| **Cache Read** | Same prefix + `cache_control` + new messages | **Only new tokens** (`cache_read_input_tokens`) |
| **Cache Miss** | Slightly different prefix | **All input tokens** (new cache created) |

**Example:**
- 4000-token RAG context cached on first call: pay for 4000+ tokens
- Each follow-up question (20 tokens): pay only 20 tokens, not 4020

## 5. Limitations and Important Considerations

- **Ephemeral, Not Persistent:** Cache is temporary with 24-hour TTL. Designed for single user sessions
- **Immutability Required:** Cached prefix must be 100% identical. Any change causes cache miss
- **Beta Feature:** API could evolve, performance may vary
- **Supported Models:** Claude 3 family (Opus, Sonnet, Haiku)
- **Verify in Response:** Check `usage` object for `cache_creation` or `cache_read` to confirm

By following these guidelines, you can effectively integrate prompt caching to significantly reduce latency and operational costs for conversational applications.