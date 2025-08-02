# Google AI Caching Guide for Claude

## Overview

Google AI's context caching feature allows you to save and reuse precomputed input tokens across multiple requests. This can significantly reduce costs and improve response times when working with the same content repeatedly.

## Key Concepts

### What is Context Caching?

Context caching pre-processes content (text, files, system instructions, tools) and stores it for reuse. The cached content:
- Can only be used with the model it was created for
- Has a time-to-live (TTL) or explicit expiration time
- Maintains the exact same context across requests
- Reduces token costs for repeated content

### When to Use Caching

Ideal scenarios:
- Asking multiple questions about the same large document
- Using the same system instructions repeatedly
- Analyzing the same media files with different prompts
- Maintaining conversation context across sessions
- Working with consistent tool configurations

## API Methods

### 1. Create Cached Content

**Endpoint:** `POST https://generativelanguage.googleapis.com/v1beta/cachedContents`

**Key Parameters:**
- `contents[]`: The content to cache (text, files, etc.)
- `model`: Required - must specify the exact model (e.g., `models/gemini-1.5-flash-001`)
- `systemInstruction`: Optional system instructions
- `tools[]`: Optional tool configurations
- `ttl` or `expireTime`: Expiration settings
- `displayName`: Human-readable name (max 128 chars)

**Example Request Structure:**
```json
{
  "model": "models/gemini-1.5-flash-001",
  "contents": [
    {
      "parts": [
        {
          "inline_data": {
            "mime_type": "text/plain",
            "data": "base64_encoded_content"
          }
        }
      ],
      "role": "user"
    }
  ],
  "systemInstruction": {
    "parts": [
      {
        "text": "You are an expert analyzing transcripts."
      }
    ]
  },
  "ttl": "300s"
}
```

### 2. List Cached Contents

**Endpoint:** `GET https://generativelanguage.googleapis.com/v1beta/cachedContents`

**Query Parameters:**
- `pageSize`: Max items per page (max 1000)
- `pageToken`: For pagination

### 3. Get Specific Cache

**Endpoint:** `GET https://generativelanguage.googleapis.com/v1beta/{name=cachedContents/*}`

**Path Parameter:**
- `name`: The cache resource name (format: `cachedContents/{id}`)

### 4. Update Cache (Expiration Only)

**Endpoint:** `PATCH https://generativelanguage.googleapis.com/v1beta/{cachedContent.name=cachedContents/*}`

**Updatable Fields:**
- `ttl`: New time-to-live duration
- `expireTime`: New expiration timestamp

**Note:** Only expiration can be updated - content is immutable.

### 5. Delete Cache

**Endpoint:** `DELETE https://generativelanguage.googleapis.com/v1beta/{name=cachedContents/*}`

## Usage Patterns

### Basic File Caching

1. Upload a file
2. Create cache with the file
3. Use the cache for multiple queries

```python
# Create cache
cache = client.caches.create(
    model="gemini-1.5-flash-001",
    config={
        "contents": [uploaded_file],
        "system_instruction": "You are an expert analyzing transcripts."
    }
)

# Use cache for generation
response = client.models.generate_content(
    model="gemini-1.5-flash-001",
    contents="Please summarize this transcript",
    config={"cached_content": cache.name}
)
```

### Conversation Caching

Cache an entire conversation history to continue later:

```python
# Create chat and have conversation
chat = client.chats.create(model=model_name, config=config)
# ... multiple exchanges ...

# Cache the conversation
cache = client.caches.create(
    model=model_name,
    config={
        "contents": chat.get_history(),
        "system_instruction": system_instruction
    }
)

# Later, continue with cached context
new_chat = client.chats.create(
    model=model_name,
    config={"cached_content": cache.name}
)
```

## Content Structure

### Content Object
```json
{
  "parts": [
    {
      "text": "string",
      "inline_data": {"mime_type": "string", "data": "base64"},
      "file_data": {"file_uri": "string", "mime_type": "string"},
      "function_call": {...},
      "function_response": {...}
    }
  ],
  "role": "user|model"
}
```

### Supported Part Types
- Text content
- Inline data (base64 encoded)
- File references (URI-based)
- Function calls and responses
- Executable code and results
- Video metadata

## Expiration Management

### Time-to-Live (TTL)
- Input only
- Duration format: `"300s"` (5 minutes), `"7200s"` (2 hours)
- Convenient for relative expiration

### Expire Time
- Absolute timestamp
- RFC 3339 format: `"2024-10-02T15:01:23Z"`
- Always returned in responses

## Best Practices

### 1. Model Consistency
- Cached content is model-specific
- Cannot use cache created for one model with another
- Include model version in cache planning

### 2. Content Selection
- Cache large, frequently-used content
- Include system instructions if consistent
- Consider caching tool configurations

### 3. Expiration Strategy
- Short TTL for temporary analysis (minutes/hours)
- Longer TTL for stable reference content (days)
- Monitor usage to optimize expiration

### 4. Error Handling
- Cache may expire during use
- Have fallback to recreate cache
- Check cache existence before use

## Cost Optimization

### Token Savings
- Cached tokens are pre-computed once
- Subsequent uses don't re-process these tokens
- Significant savings for large documents

### Usage Metadata
```json
{
  "usageMetadata": {
    "totalTokenCount": 12345
  }
}
```

## Tool Integration

Cached content can include tool configurations:

```json
{
  "tools": [
    {
      "functionDeclarations": [...],
      "googleSearchRetrieval": {...},
      "codeExecution": {},
      "googleSearch": {...}
    }
  ],
  "toolConfig": {
    "functionCallingConfig": {
      "mode": "AUTO",
      "allowedFunctionNames": [...]
    }
  }
}
```

## Limitations and Considerations

1. **Immutability**: Content cannot be modified after caching
2. **Model Binding**: Cache is tied to specific model
3. **Size Limits**: Check model-specific context limits
4. **Expiration**: No auto-renewal; must recreate
5. **Storage**: Counts against account quotas

## Example Workflows

### Document Analysis Workflow
1. Upload document
2. Create cache with analysis instructions
3. Ask multiple questions using same cache
4. Update expiration if needed
5. Delete when analysis complete

### Conversation Continuity Workflow
1. Start conversation
2. Cache conversation state at checkpoint
3. Resume later with cached context
4. Continue building on previous context
5. Re-cache periodically for new checkpoints

## Integration with Claude

When implementing caching in a system like ccproxy:

1. **Cache Strategy**: Determine what content benefits from caching
2. **Model Mapping**: Ensure cached content aligns with model routing
3. **Expiration Handling**: Implement cache renewal logic
4. **Fallback Logic**: Handle cache misses gracefully
5. **Cost Tracking**: Monitor token savings from cache usage

This caching system is particularly useful for:
- Large context windows in Gemini models
- Repeated analysis tasks
- Maintaining conversation state
- Reducing latency for common queries
- Optimizing costs for high-volume applications