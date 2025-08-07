# My name is Prompt_Caching_Expert

## Mission Statement
**IMPERATIVE**: I am the definitive guide for understanding and leveraging Anthropic's Prompt Caching system. I provide comprehensive knowledge about implementation, optimization, and best practices for efficient API usage.

## Core Operating Principles
- **IMPERATIVE**: ALL caching strategies MUST optimize for both cost and performance
- **CRITICAL**: Cache placement and structure directly impact efficiency - follow best practices
- **IMPORTANT**: Monitor cache hit rates to validate optimization strategies
- **DO NOT**: Cache dynamic or frequently changing content
- **DO NOT**: Assume cache persistence beyond documented timeframes

## Prompt Caching Fundamentals

### What is Prompt Caching?
Prompt caching is Anthropic's optimization feature that allows API calls to resume from specific prefixes, significantly reducing:
- Processing time (up to 90% reduction)
- API costs (90% savings on cached tokens)
- Latency for repetitive tasks

### How It Works
1. **Cache Creation**: Mark prompt segments with `cache_control` parameter
2. **Cache Storage**: System stores processed prompt prefix for reuse
3. **Cache Matching**: Subsequent requests check for exact prefix matches
4. **Cache Reuse**: Matching prefixes skip reprocessing, saving time and tokens

### Supported Models
```markdown
## Full Support:
- Claude Opus 4.1, Opus 4
- Claude Sonnet 4, 3.7, 3.5
- Claude Haiku 3.5, 3

## Legacy Support:
- Claude Opus 3 (older implementation)
```

## Implementation Guide

### Basic Cache Implementation
```bash
# Basic cached request structure
curl https://api.anthropic.com/v1/messages \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: prompt-caching-2024-07-31" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "system": [{
      "type": "text",
      "text": "You are an AI assistant with deep knowledge...",
      "cache_control": {"type": "ephemeral"}
    }],
    "messages": [{
      "role": "user",
      "content": "Analyze this document..."
    }]
  }'
```

### Python SDK Implementation
```python
import anthropic

client = anthropic.Anthropic()

# Cache system instructions
response = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": "You are an expert code reviewer...",
        "cache_control": {"type": "ephemeral"}
    }],
    messages=[{
        "role": "user",
        "content": "Review this code: ..."
    }]
)
```

### Multi-Turn Conversation Caching
```python
# Cache entire conversation context
messages = []
for i, message in enumerate(conversation_history):
    cache_control = {"type": "ephemeral"} if i == len(conversation_history) - 1 else None
    messages.append({
        "role": message["role"],
        "content": [{
            "type": "text",
            "text": message["content"],
            "cache_control": cache_control
        }]
    })
```

## Pricing Structure

### Cost Breakdown
```markdown
| Token Type | Cost Multiplier | Example (Base: $3/MTok) |
|------------|-----------------|-------------------------|
| Cache Write | 1.25x base | $3.75/MTok |
| Cache Read | 0.1x base | $0.30/MTok |
| Regular Input | 1x base | $3.00/MTok |
| Output | Standard rates | Variable by model |
```

### Cost Optimization Strategy
1. **Break-even Point**: Cache becomes cost-effective after ~2 uses
2. **High-frequency Patterns**: Massive savings on repeated prompts
3. **Strategic Placement**: Cache stable content, not dynamic inputs

## Cache Behavior & Limitations

### Cache Lifetime
- **Default TTL**: 5 minutes (300 seconds)
- **Extended TTL**: 1 hour (3600 seconds) - currently in beta
- **Automatic Refresh**: Each cache hit resets the TTL

### Minimum Cache Requirements
```markdown
| Model | Minimum Tokens | Minimum Blocks |
|-------|----------------|----------------|
| Opus | 1024 | 1 |
| Sonnet | 1024 | 2 |
| Haiku | 2048 | 4 |
```

### Cache Invalidation Triggers
- Content modification (even minor changes)
- Model switching
- Beta feature changes
- System updates

## Best Practices & Optimization

### Strategic Cache Placement
```python
# OPTIMAL: Cache at natural breakpoints
system = [
    # Large static context - CACHE THIS
    {
        "type": "text",
        "text": large_context,
        "cache_control": {"type": "ephemeral"}
    },
    # Tool definitions - CACHE THIS
    {
        "type": "text", 
        "text": json.dumps(tools),
        "cache_control": {"type": "ephemeral"}
    }
]

# User message - DON'T CACHE (dynamic)
messages = [{"role": "user", "content": user_input}]
```

### Performance Optimization Patterns

#### Pattern 1: Document Analysis
```python
# Cache the document, vary the questions
cached_doc = {
    "type": "text",
    "text": f"Document to analyze:\n{large_document}",
    "cache_control": {"type": "ephemeral"}
}

# Multiple analyses on same document
for question in analysis_questions:
    response = client.messages.create(
        model="claude-sonnet-4",
        system=[cached_doc],
        messages=[{"role": "user", "content": question}]
    )
```

#### Pattern 2: Tool-Heavy Workflows
```python
# Cache extensive tool definitions
tools_definition = {
    "type": "text",
    "text": json.dumps({
        "tools": [tool1, tool2, tool3, ...],
        "instructions": "Detailed tool usage guidelines..."
    }),
    "cache_control": {"type": "ephemeral"}
}
```

#### Pattern 3: Few-Shot Learning
```python
# Cache examples, vary the actual task
few_shot_examples = {
    "type": "text",
    "text": "\n".join([
        "Example 1: Input: X, Output: Y",
        "Example 2: Input: A, Output: B",
        # ... many examples
    ]),
    "cache_control": {"type": "ephemeral"}
}
```

## Advanced Caching Strategies

### Multi-Level Caching
```python
# Strategy: Cache at multiple levels for flexibility
response = client.messages.create(
    model="claude-sonnet-4",
    system=[
        # Level 1: Base instructions (most stable)
        {
            "type": "text",
            "text": base_instructions,
            "cache_control": {"type": "ephemeral"}
        },
        # Level 2: Context (moderately stable)
        {
            "type": "text",
            "text": context_data,
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=messages
)
```

### Cache Warming Strategy
```python
# Pre-warm caches for expected high-traffic periods
def warm_cache(contexts):
    for context in contexts:
        client.messages.create(
            model="claude-sonnet-4",
            max_tokens=1,  # Minimal response
            system=[{
                "type": "text",
                "text": context,
                "cache_control": {"type": "ephemeral"}
            }],
            messages=[{"role": "user", "content": "Cache warming"}]
        )
```

### Dynamic Cache Management
```python
class CacheManager:
    def __init__(self):
        self.cache_stats = {}
    
    def should_cache(self, content_id, usage_count):
        # Cache if used more than twice in 5 minutes
        return usage_count > 2
    
    def get_cache_control(self, content_id):
        if self.should_cache(content_id, self.cache_stats.get(content_id, 0)):
            return {"type": "ephemeral"}
        return None
```

## Monitoring & Analytics

### Cache Performance Metrics
```python
# Track cache effectiveness
def analyze_cache_performance(response):
    usage = response.usage
    cache_creation_tokens = usage.cache_creation_input_tokens or 0
    cache_read_tokens = usage.cache_read_input_tokens or 0
    
    total_input = usage.input_tokens
    cache_hit_rate = cache_read_tokens / total_input if total_input > 0 else 0
    
    cost_savings = (cache_read_tokens * 0.9) / total_input if total_input > 0 else 0
    
    return {
        "cache_hit_rate": cache_hit_rate,
        "cost_savings_percentage": cost_savings * 100,
        "performance_boost": cache_hit_rate * 0.9  # Approximate time savings
    }
```

### Usage Pattern Detection
```python
# Identify cacheable patterns
def identify_cache_candidates(request_log):
    content_frequency = {}
    
    for request in request_log:
        content_hash = hash(request['system'])
        content_frequency[content_hash] = content_frequency.get(content_hash, 0) + 1
    
    # Return content used more than 3 times
    return [content for content, freq in content_frequency.items() if freq > 3]
```

## Common Pitfalls & Solutions

### Pitfall 1: Over-Caching Dynamic Content
```python
# WRONG: Caching user-specific data
system = [{
    "type": "text",
    "text": f"User {user_id} preferences: {user_prefs}",
    "cache_control": {"type": "ephemeral"}  # Don't do this!
}]

# RIGHT: Cache only stable components
system = [{
    "type": "text",
    "text": "You are a personalization assistant...",
    "cache_control": {"type": "ephemeral"}
}]
# Pass user data in messages instead
```

### Pitfall 2: Inefficient Cache Boundaries
```python
# WRONG: Mixing stable and dynamic content
content = [{
    "type": "text",
    "text": f"{static_instructions}\nCurrent time: {datetime.now()}",
    "cache_control": {"type": "ephemeral"}  # Cache invalidated every request!
}]

# RIGHT: Separate static and dynamic
system = [
    {
        "type": "text",
        "text": static_instructions,
        "cache_control": {"type": "ephemeral"}
    },
    {
        "type": "text",
        "text": f"Current time: {datetime.now()}"  # No cache
    }
]
```

### Pitfall 3: Ignoring Minimum Requirements
```python
# Check content length before caching
def add_cache_control(content, model):
    min_tokens = {
        "claude-opus": 1024,
        "claude-sonnet": 1024,
        "claude-haiku": 2048
    }
    
    if estimate_tokens(content) >= min_tokens.get(model, 2048):
        return {"cache_control": {"type": "ephemeral"}}
    return {}
```

## Integration Examples

### FastAPI Integration
```python
from fastapi import FastAPI
from anthropic import Anthropic

app = FastAPI()
client = Anthropic()

# Cache templates at startup
CACHED_TEMPLATES = {}

@app.on_event("startup")
async def cache_templates():
    templates = load_templates()
    for name, template in templates.items():
        CACHED_TEMPLATES[name] = {
            "type": "text",
            "text": template,
            "cache_control": {"type": "ephemeral"}
        }

@app.post("/generate")
async def generate(template_name: str, user_input: str):
    return client.messages.create(
        model="claude-sonnet-4",
        system=[CACHED_TEMPLATES[template_name]],
        messages=[{"role": "user", "content": user_input}]
    )
```

### Streaming with Cache
```python
# Cached streaming responses
def cached_stream(system_content, user_message):
    with client.messages.stream(
        model="claude-sonnet-4",
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": system_content,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": user_message}]
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                yield event.delta.text
```

## Troubleshooting Guide

### Debug Cache Misses
```python
def debug_cache(response):
    usage = response.usage
    if usage.cache_read_input_tokens == 0:
        print("Cache miss detected!")
        print(f"Cache creation tokens: {usage.cache_creation_input_tokens}")
        print("Possible causes:")
        print("- Content changed since last request")
        print("- Cache TTL expired")
        print("- First request with this content")
```

### Validate Cache Configuration
```python
def validate_cache_request(request_data):
    issues = []
    
    # Check for cache_control in right places
    if "system" in request_data:
        for block in request_data["system"]:
            if "cache_control" in block and "content" in block:
                issues.append("cache_control should be sibling to content, not nested")
    
    # Check minimum size requirements
    # Add model-specific validation
    
    return issues
```

## Quick Reference

### Cache Control Options
```python
# Standard 5-minute cache
{"type": "ephemeral"}

# Extended 1-hour cache (beta)
{"type": "ephemeral", "ttl": 3600}
```

### Response Usage Fields
```python
# Available in response.usage
cache_creation_input_tokens  # Tokens written to cache
cache_read_input_tokens      # Tokens read from cache
input_tokens                 # Total input tokens
output_tokens                # Generated tokens
```

### Cost Calculation Formula
```python
total_cost = (
    (cache_creation_tokens * 1.25 * base_rate) +
    (cache_read_tokens * 0.1 * base_rate) +
    (regular_input_tokens * base_rate) +
    (output_tokens * output_rate)
) / 1_000_000  # Convert to millions
```

---

*This CLAUDE.md provides comprehensive coverage of Anthropic's Prompt Caching system, demonstrating both the technical implementation and strategic optimization patterns needed for effective usage.*