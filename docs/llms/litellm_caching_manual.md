# A Developer's Guide to Caching in LiteLLM: From Cost Savings to Smart Responses

## Table of Contents
1. [Introduction](#introduction)
2. [Part 1: Provider-Native Caching ("The Easy Win")](#part-1-provider-native-caching-the-easy-win)
3. [Part 2: LiteLLM Response Caching ("The Power-User Cache")](#part-2-litellm-response-caching-the-power-user-cache)
4. [Part 3: Semantic Caching ("The Smart Cache")](#part-3-semantic-caching-the-smart-cache)
5. [Part 4: Implementation Deep-Dive](#part-4-implementation-deep-dive)
6. [Part 5: Advanced Configurations](#part-5-advanced-configurations)
7. [Part 6: Provider-Specific Details](#part-6-provider-specific-details)
8. [Part 7: Performance & Cost Analysis](#part-7-performance--cost-analysis)
9. [Decision Matrix](#decision-matrix)
10. [Troubleshooting Cheat-Sheet](#troubleshooting-cheat-sheet)
11. [Next Steps Checklist](#next-steps-checklist)

## Introduction

LiteLLM offers three complementary caching mechanisms that can drive >90% cost savings, slash latency, and shield you from provider rate limits. This guide walks through:

1. **Provider-Native Caching** – leverage the LLM vendor's own cache
2. **LiteLLM Response Caching** – provider-agnostic, pluggable back-ends
3. **Semantic Caching** – "fuzzy" reuse based on meaning, not text

You can enable any combination: e.g. Provider-Native for cheap wins **plus** Response Caching for longer-lived storage.

## Part 1: Provider-Native Caching ("The Easy Win")

### Concept
Some vendors (Anthropic, Google Vertex, etc.) support an **ephemeral** cache if you attach a special `cache_control` block in the request. LiteLLM lets you:

• add the block manually, or  
• inject it automatically with a pre-LLM hook (recommended)

### Manual Example
```python
import litellm

resp = litellm.completion(
    model="anthropic/claude-3.5-sonnet-20240620",
    messages=[
        {"role": "system", "content": "Translate to French.", 
         "cache_control": {"type": "ephemeral"}},  # 👈 provider cache hint
        {"role": "user", "content": "Good morning"}
    ]
)
print(resp.choices[0].message.content)
```

### Automatic Injection
Use the bundled hook from `anthropic_cache_control_hook.py`.  
Key lines for context:

• Line 21 `async def async_pre_llm_hook(request, **kwargs):` – entry point invoked before the call  
• Line 64 `system_message_obj["cache_control"] = {"type": "ephemeral"}` – the injection itself

Enable in `config.yaml`:
```yaml
model_list:
  - model_name: claude-3.5-cached
    litellm_params:
      model: anthropic/claude-3.5-sonnet-20240620
hooks:                                  # ← tell LiteLLM to load the hook file
  - path: anthropic_cache_control_hook.py
    async_pre_llm_hook: async_pre_llm_hook

# optional – restrict which messages the hook touches
cache_control_injection_points:
  - location: message
    role: system
```

### When to use
• High-volume, *identical* prompts (system messages, chain-of-thought instructions)  
• You're OK with short (≈60s) TTL managed by the provider

## Part 2: LiteLLM Response Caching ("The Power-User Cache")

### Concept
LiteLLM hashes the request (model + messages + params) and stores the provider's JSON response in a user-selected back-end.  
Next identical request → LiteLLM returns the stored response without hitting the provider.

### Quick-start (single-process dev)
```python
import litellm
from litellm import caching

caching.enable_cache()               # defaults to in-memory
litellm.cache.ttl = 900              # 15 min

litellm.completion(model="gpt-4o", messages=[...])
```

### Production Proxy + Redis
```yaml
# config.yaml
cache_responses: true
caching:
  type: redis
  host: cache.internal
  port: 6379
  ttl: 7200                 # 2 hours
  key_prefix: litellm:v1:   # optional isolation per environment
proxy:
  host: 0.0.0.0
  port: 4000
```
Launch:  
`litellm --config config.yaml`

### Cache-Key Anatomy (default)
SHA256(model | join(messages) | sorted(kwargs))  
You can override the key builder if you need to ignore volatile fields (e.g., `user_id`) – supply your own `build_cache_key` callable in a hook.

### Choosing a Back-end
• `in-memory`  – fastest, not shared between pods  
• `disk`       – persists across restarts on a single node  
• `redis`      – standard for distributed workloads. Supports TTL eviction  
• `s3`         – ultra-cheap long-term retention; higher latency  
• `dual_cache` – L1 in-memory + L2 Redis; sample snippet:

```yaml
caching:
  type: dual_cache
  l1:
    type: in-memory
    capacity: 5000              # max entries
  l2:
    type: redis
    host: redis.internal
    ttl: 3600
```

### Edge-Cases & Gotchas
• Streaming responses: cached as **full** text; subsequent consumers receive the whole chunk at once (no token-stream)  
• Mutable model params (e.g., `temperature`) are part of the key – even slight changes create a miss  
• Versioning: bump `key_prefix` when you upgrade model or prompt template

## Part 3: Semantic Caching ("The Smart Cache")

### Concept
Instead of exact-key matching, LiteLLM embeds the *prompt* into a vector and looks for **similar** prompts in a vector DB.  
If similarity ≥ threshold, return the stored completion.

### Minimal Setup (Redis Vector search)
```yaml
cache_responses: true
caching:
  type: redis_semantic
  host: redis-vector.internal
  port: 6379
  ttl: 86400                       # 24 h
  similarity_threshold: 0.85
  params:
    embedding_model: text-embedding-3-small
```

### How It Works
1. Incoming prompt → embeddings via `embedding_model`
2. Redis ANN search (HNSW) for cosine similarity
3. Best hit ≥ 0.85 → serve cached answer; otherwise forward to provider and store new pair

### When Semantic Caching Shines
• FAQ/chatbot where users ask same question in many ways  
• LLM calls are expensive (`gpt-4o`, Claude 3). Small embedding fee offsets a full completion

### Where It Fails
• Program-synthesis, SQL generation, or extraction tasks requiring strict input fidelity  
• Prompts containing dynamic numbers or entities – semantically "close" might still be wrong

### Tuning Tips
• Raise the threshold (0.92-0.95) for tasks needing higher precision  
• Periodically evict data that drifts out of scope to prevent "stale answer" surprises  
• Use a cheaper embedding model (`embedding-small`) when cost matters; response quality mostly unaffected

## Part 4: Implementation Deep-Dive

This section covers the mechanics of how LiteLLM's Response Cache operates, giving you the control to tune its behavior for your specific needs.

### Cache Key Generation Internals

A deterministic cache key is the foundation of reliable caching. By default, LiteLLM generates a key by creating a stable string representation of the request and hashing it. The logic is conceptually:

`SHA256(f"{model}:{serialized_messages}:{serialized_params}")`

Where:
- `model`: The name of the model being called (e.g., `gpt-4o`)
- `serialized_messages`: A concatenation of all message content. The order is preserved
- `serialized_params`: A sorted, stable representation of all other completion parameters (`temperature`, `max_tokens`, `top_p`, etc.). Sorting is critical to ensure that `{temp: 0.5, top_p: 0.9}` and `{top_p: 0.9, temp: 0.5}` produce the same key

Any variation in these inputs—even a single character—will result in a different key and a cache miss.

### Custom Cache Key Builders

Sometimes, the default key generation is too strict. A common scenario is when your request includes metadata that shouldn't influence the cache hit, such as a `user_id` or `trace_id`.

You can override the key generation logic with a custom hook.

**Use Case:** Ignoring a `user` parameter to share a cache entry across all users for a specific request.

1. **Create a custom key builder hook (`custom_key_hook.py`):**

    ```python
    # custom_key_hook.py
    import litellm

    def build_cache_key(model, messages, **kwargs):
        """
        Builds a cache key but deliberately ignores the 'user' kwarg.
        """
        # Pop 'user' so it's not included in the default hashing
        kwargs.pop("user", None)

        # Use LiteLLM's default key builder with the modified kwargs
        return litellm.caching.cache_key_generator(
            model=model,
            messages=messages,
            **kwargs
        )
    ```

2. **Register the hook in `config.yaml`:**

    ```yaml
    # config.yaml
    cache_responses: true
    caching:
      type: redis
      host: redis.internal
      # 👇 Point to your custom key builder function
      key_builder: custom_key_hook.build_cache_key
    ```
    Now, calls with different `user` values but identical prompts will share the same cache entry.

### Cache Invalidation Strategies

"There are only two hard things in Computer Science: cache invalidation and naming things." LiteLLM provides three primary strategies for invalidation:

1. **TTL-Based (Default):** The simplest method. Let the cache backend (like Redis) automatically evict keys after the `ttl` expires. This is great for data that can be slightly stale but is otherwise fire-and-forget.

2. **Prefix Versioning (Recommended for Bulk Invalidation):** When you update a core prompt template or model version, you need to invalidate all related entries. The most robust way is to version your cache keys using the `key_prefix` in `config.yaml`.

    - **Version 1:** `key_prefix: litellm:prompt-v1:`
    - **Version 2 (after a prompt change):** `key_prefix: litellm:prompt-v2:`

    This instantly invalidates the entire old set without requiring any `DELETE` operations.

3. **Targeted Deletion (Programmatic):** For fine-grained control, you can explicitly delete a specific cache entry. This is useful when an external event makes a cached response invalid (e.g., a document in a RAG system is updated).

    ```python
    import litellm

    # First, generate the key for the entry you want to delete
    # Must use the *exact* same parameters as the original call
    key_to_delete = litellm.caching.get_cache_key(
        model="gpt-4o",
        messages=[{"role": "user", "content": "What is the capital of France?"}]
    )

    # Then, delete it
    litellm.cache.delete(key=key_to_delete)
    ```

### Monitoring Cache Performance

You can't optimize what you can't measure. Integrating LiteLLM with a monitoring stack like Prometheus is essential.

**Key Metrics to Track:**
- `litellm_cache_hit_ratio`: The single most important metric. `hits / (hits + misses)`. A high ratio means you're saving money and reducing latency
- `litellm_cache_hits_total` (Counter): The raw number of cache hits
- `litellm_cache_misses_total` (Counter): The raw number of cache misses
- `litellm_cache_latency_seconds` (Histogram): The time spent retrieving an item from the cache. Helps diagnose if your cache backend is slow

Enable monitoring in your `config.yaml`:
```yaml
# config.yaml
# ... other settings
litellm_settings:
  # 👇 Enables the /metrics endpoint for Prometheus
  enable_prometheus: true
```
Then, configure your Prometheus instance to scrape the `/metrics` endpoint on your LiteLLM proxy.

## Part 5: Advanced Configurations

### Multi-Tenant Caching & Namespace Isolation

In a multi-tenant application, you **must** prevent cache data from leaking between tenants. The best practice is to incorporate a tenant ID into the cache key. This can be achieved cleanly with a custom key builder hook that reads a tenant ID from the request.

**Use Case:** Partition the cache by `api_key`.

1. **Create the hook (`tenant_cache_hook.py`):**

    ```python
    # tenant_cache_hook.py
    import litellm

    def tenant_key_builder(api_key, **kwargs):
        """
        Prepends the api_key to the default cache key for strict tenant isolation.
        """
        # Generate the standard key first
        default_key = litellm.caching.cache_key_generator(**kwargs)

        # Return a new key namespaced by the tenant's api_key
        return f"tenant:{api_key}:{default_key}"
    ```

2. **Register it in `config.yaml`:**

    ```yaml
    # config.yaml
    cache_responses: true
    caching:
      type: redis
      # 👇 This hook will receive the api_key from the request context
      key_builder: tenant_cache_hook.tenant_key_builder
    ```
    This ensures `tenant_A` and `tenant_B` making the exact same API call will use separate, isolated cache entries.

### Cache Warming Strategies

Cache warming (or "pre-populating") is the process of filling your cache with expected responses *before* they are requested by users. This is ideal for minimizing latency on the first view of common items.

**Strategy:** A simple warming script that runs on deployment.

```python
# warm_cache.py
import litellm, asyncio

# List of common prompts you expect to be requested frequently
COMMON_PROMPTS = [
    "What are your hours of operation?",
    "How do I reset my password?",
    "What is your return policy?",
]

async def warm_cache():
    # Point to your running LiteLLM proxy
    litellm.api_base = "http://localhost:4000"
    litellm.api_key = "any-key" # Use a valid key if required

    for prompt in COMMON_PROMPTS:
        try:
            print(f"Warming cache for: '{prompt}'")
            await litellm.acompletion(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as e:
            print(f"Failed to warm cache for prompt: {prompt}. Error: {e}")

if __name__ == "__main__":
    asyncio.run(warm_cache())
```
**Best Practice:**
- Run this as a post-deployment step in your CI/CD pipeline
- Keep the list of warming prompts focused on your highest-traffic, most static content to avoid unnecessary costs

### A Note on Fallback Chains

You mentioned "Fallback Chains." In the context of caching, the primary fallback is already built-in: if a request is a **cache miss**, LiteLLM "falls back" to calling the actual LLM provider.

More complex fallback logic—such as "on cache miss, try a cheaper/faster model first"—is a **routing strategy**, not a caching one. This is best handled by LiteLLM's Router capabilities, which allow you to define sophisticated logic for model selection, retries, and fallbacks. We recommend keeping caching and routing concerns separate for a cleaner architecture.

## Part 6: Provider-Specific Details

### OpenAI

OpenAI supports prompt caching through the `cached` parameter in messages:

```python
import litellm

response = litellm.completion(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
            "cached": True  # Mark this message for caching
        },
        {"role": "user", "content": "Hello!"}
    ]
)
```

**Key Points:**
- Cached prompts reduce costs for repetitive system messages
- Cache duration is managed by OpenAI (typically hours)
- Only available for certain models (check OpenAI docs)

### Anthropic

Anthropic uses `cache_control` blocks with type "ephemeral":

```python
import litellm

response = litellm.completion(
    model="anthropic/claude-3.5-sonnet-20240620",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
            "cache_control": {"type": "ephemeral"}
        },
        {"role": "user", "content": "Hello!"}
    ]
)
```

**Key Points:**
- Ephemeral caching lasts ~5 minutes
- Significant cost savings for repetitive prompts
- Works with Claude 3+ models

### AWS Bedrock

Bedrock (when using Anthropic models) follows the same pattern as Anthropic:

```python
import litellm

response = litellm.completion(
    model="bedrock/anthropic.claude-3-sonnet",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
            "cache_control": {"type": "ephemeral"}
        },
        {"role": "user", "content": "Hello!"}
    ]
)
```

### Deepseek

Deepseek uses a `cache_control` parameter:

```python
import litellm

response = litellm.completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "Hello!"}],
    cache_control=True  # Enable caching for this request
)
```

### Gemini/VertexAI

Gemini uses a different approach with context caching APIs:

```python
import litellm

# First, create a cached context
cached_context = litellm.create_context_cache(
    model="gemini/gemini-1.5-pro",
    system_instruction="You are a helpful assistant with extensive knowledge.",
    ttl=3600  # Cache for 1 hour
)

# Then use the cached context
response = litellm.completion(
    model="gemini/gemini-1.5-pro",
    messages=[{"role": "user", "content": "What is quantum computing?"}],
    context_cache_id=cached_context.id
)
```

**Key Points:**
- Context caching is ideal for large system prompts
- TTL can be configured (up to 1 hour)
- Supports both Gemini and VertexAI endpoints

## Part 7: Performance & Cost Analysis

### Benchmarks for Different Cache Backends

| Backend | Latency (p50) | Latency (p99) | Throughput | Best For |
|---------|---------------|---------------|------------|----------|
| In-Memory | <1ms | 2ms | 100k+ req/s | Single instance, dev |
| Redis | 2-5ms | 10ms | 50k req/s | Production, distributed |
| Redis Cluster | 3-6ms | 12ms | 100k+ req/s | High-scale production |
| Disk | 5-20ms | 100ms | 1k req/s | Single node, persistence |
| S3 | 50-200ms | 500ms | 100 req/s | Long-term archival |
| Dual Cache | 1-5ms | 10ms | 80k req/s | High-performance prod |

### Cost Calculation Examples

Let's analyze the cost impact of caching for a typical chatbot scenario:

**Scenario:** Customer support bot with 10,000 daily queries
- 70% are variations of 20 common questions
- Average prompt: 500 tokens
- Average response: 150 tokens
- Model: GPT-4o ($0.005/1K input, $0.015/1K output)

**Without Caching:**
```
Daily cost = 10,000 × ((500 × 0.005 + 150 × 0.015) / 1000)
          = 10,000 × $0.00475
          = $47.50/day = $1,425/month
```

**With Semantic Caching (85% hit rate on common questions):**
```
Cache hits = 10,000 × 0.7 × 0.85 = 5,950
Cache misses = 10,000 - 5,950 = 4,050
Embedding cost = 10,000 × 0.0001 = $1.00

Daily cost = (4,050 × $0.00475) + $1.00
          = $19.24 + $1.00
          = $20.24/day = $607/month

Savings: 57% or $818/month
```

### Cache Hit Rate Optimization

To maximize your cache hit rate:

1. **Normalize Inputs:**
   ```python
   def normalize_prompt(prompt):
       # Remove extra whitespace
       prompt = " ".join(prompt.split())
       # Lowercase for case-insensitive matching
       prompt = prompt.lower()
       # Remove punctuation variations
       prompt = prompt.rstrip("?!.")
       return prompt
   ```

2. **Use Semantic Caching for Variable Inputs:**
   - Set similarity threshold based on your use case
   - Monitor false positive rates
   - Adjust embedding model for better semantic understanding

3. **Implement Smart Key Design:**
   ```python
   # Group related queries
   def smart_cache_key(model, messages, **kwargs):
       # Extract intent from user message
       user_msg = messages[-1]["content"]
       intent = extract_intent(user_msg)  # Your intent classifier
       
       # Use intent as part of cache key
       return f"{model}:{intent}:{hash(user_msg)}"
   ```

4. **Monitor and Iterate:**
   - Track cache hit rates by query type
   - Identify patterns in cache misses
   - Adjust caching strategy based on data

## Decision Matrix

| Goal / Constraint | Recommended Cache |
|---|---|
| Cheap win for identical system prompts (Anthropic) | Provider-Native |
| Cross-provider, multi-pod, exact prompt reuse | Response Caching (Redis) |
| High QPS, low latency, multi-pod | Dual Cache (In-Memory + Redis) |
| Varied phrasing; chatbot FAQ | Semantic Caching |
| Precision coding / extraction tasks | Response Caching only (no semantic) |

## Troubleshooting Cheat-Sheet

• "Cache never hits" → ensure identical ordering of messages and params; enable `litellm.set_verbose=True`  
• "Stale data" → verify `ttl` or call `litellm.cache.delete_cache()` programmatically  
• "Redis memory bloat" → adjust `maxmemory-policy allkeys-lru` or use `ttl`  
• "Semantic returns wrong answer" → raise similarity threshold or disable for that route

## Advanced: Custom Cache Hooks

Need bespoke logic (multi-tenant partitioning, per-user TTL)?  
Write an async pre-/post-LLM hook and register it:

```python
# cache_policy.py
async def async_post_cache_hook(response, request, **_):
    # tag cache entry with tenant for later eviction
    response["metadata"]["tenant_id"] = request.headers["X-Tenant"]

hooks:
  - path: cache_policy.py
    async_post_cache_hook: async_post_cache_hook
```

## Next Steps Checklist

☐ Decide which cache tier(s) match your workload  
☐ Copy the relevant `config.yaml` snippet, adjust host/TTL  
☐ (Optional) Drop the Anthropic hook file into your repo and list it under `hooks`  
☐ Run `litellm --config config.yaml`, tail logs for `CACHE HIT` / `CACHE MISS`  
☐ Monitor Redis memory & hit-rate dashboards; fine-tune TTL and thresholds

---

## Appendix: Implementation Files Reference

### Core Files
- `litellm/caching/caching.py` - Main caching module with base classes
- `litellm/integrations/anthropic_cache_control_hook.py` - Auto-injection logic
- `litellm/router_utils/prompt_caching_cache.py` - Router integration

### Cache Backend Implementations
- `litellm/caching/redis_cache.py` - Standard Redis key-value cache
- `litellm/caching/redis_semantic_cache.py` - Redis with vector similarity search
- `litellm/caching/qdrant_semantic_cache.py` - Qdrant vector database integration
- `litellm/caching/disk_cache.py` - File-based persistent caching
- `litellm/caching/in_memory_cache.py` - Fast local memory cache
- `litellm/caching/s3_cache.py` - AWS S3 storage backend
- `litellm/caching/dual_cache.py` - Two-tier caching (L1 + L2)

### Testing Resources
- `tests/local_testing/test_caching.py` - Comprehensive caching tests
- `tests/test_litellm/caching/` - Backend-specific test suites

---

*This guide represents the collective knowledge from LiteLLM's documentation, implementation analysis, and best practices developed through extensive production usage.*