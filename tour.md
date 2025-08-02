# CCProxy Context Preservation System - Code Tour

## Overview

The CCProxy context preservation system integrates with Claude Code's conversation history to maintain context across different LLM providers. This tour will walk you through the architecture and implementation details.

## System Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Code    │     │    CCProxy       │     │  LLM Provider   │
│  JSONL Files    │────▶│  Context System  │────▶│  (Anthropic,    │
│ ~/.claude/...   │     │                  │     │   Gemini, etc)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │ Provider Metadata│
                        │     Storage      │
                        └──────────────────┘
```

## Core Components

### 1. Claude Integration Module (`src/ccproxy/claude_integration.py`)

This module handles discovering and reading Claude Code's JSONL conversation files.

#### Key Classes:

**ClaudeProjectLocator**
- Discovers Claude Code project directories from working directory
- Maps filesystem paths to Claude's project naming scheme
- Caches project information for performance

```python
# Example: /home/user/myproject → ~/.claude/projects/-home--user--myproject
project_path = locator.find_project_path(Path("/home/user/myproject"))
```

**ClaudeCodeReader**
- Parses JSONL session files into structured conversation history
- Extracts messages with metadata (role, content, timestamp, etc.)
- Maintains chronological order of messages

```python
conversation = reader.read_conversation(session_file)
# Returns ConversationHistory with messages, session_id, project_path
```

### 2. Context Manager (`src/ccproxy/context_manager.py`)

The orchestrator that coordinates all context preservation operations.

#### Key Features:

**Async Context Retrieval**
```python
async def get_context(self, cwd: Path, chat_id: str | None = None) -> list[Message]:
    # 1. Find Claude Code project
    # 2. Get latest session file
    # 3. Read conversation (with caching)
    # 4. Enrich with provider routing history
    # 5. Return message list
```

**Performance Optimizations**
- LRU caching with mtime-based invalidation
- Async I/O for file operations
- Configurable cache size

**Provider History Integration**
- Records routing decisions (which provider/model was used)
- Links decisions to Claude Code session IDs
- Enables context-aware routing

### 3. Provider Metadata Store (`src/ccproxy/provider_metadata.py`)

Persistent storage for routing decisions and provider history.

#### Key Features:

**Async File Operations**
- Uses ThreadPoolExecutor for non-blocking I/O
- Atomic writes with tempfile + rename
- Inter-process locking for concurrent access

**Data Structure**
```json
{
  "provider_history": [
    {
      "provider": "anthropic",
      "model": "claude-3-5-sonnet",
      "ts": 1704067200000
    }
  ],
  "routing_decisions": [
    {
      "provider": "anthropic",
      "model": "claude-3-5-sonnet",
      "timestamp": 1704067200.123,
      "session_id": "abc123...",
      "selected_by_rule": "default",
      "metadata": {}
    }
  ]
}
```

### 4. Context Hooks (`src/ccproxy/context_hooks.py`)

LiteLLM hook implementations for context injection.

#### Hook Lifecycle:

1. **Pre-call Hook**: Injects context into requests
   ```python
   async def async_log_pre_api_call(self, ...):
       # Extract working directory from headers
       # Retrieve context from ContextManager
       # Inject into messages array
   ```

2. **Success Hook**: Records routing decisions
   ```python
   async def async_log_success_event(self, ...):
       # Extract session ID from response
       # Record provider/model decision
   ```

### 5. Main Handler (`src/ccproxy/handler.py`)

The CCProxyHandler that integrates all components.

#### Initialization Flow:

```python
handler = CCProxyHandler()
# 1. Loads configuration
# 2. Initializes router with classification rules
# 3. Sets up context preservation (if enabled)
# 4. Configures hook chain
```

#### Request Processing:

```python
# 1. Pre-call: Route request based on rules
# 2. Pre-call: Inject context if enabled
# 3. API call happens
# 4. Success: Record routing decision
# 5. Success: Update metrics
```

## Configuration

### Enable Context Preservation

In `ccproxy.yaml`:
```yaml
ccproxy:
  context_preservation:
    enabled: true
    max_messages: 50  # Optional: limit context size
    cache_size: 256   # Optional: LRU cache entries
```

### Working Directory Detection

**Important Note**: Claude Code does NOT send working directory information in its requests.

The system now has two methods for finding the correct Claude Code project:

#### Method 1: Session ID Extraction (NEW)
Claude Code embeds the session ID in the `metadata.user_id` field in the format:
```
user_<hash>_account_<uuid>_session_<session-id>
```

The context system now:
1. Extracts the session ID from this metadata field
2. Searches all Claude Code projects for a matching `{session-id}.jsonl` file
3. Uses this file directly, bypassing the need for working directory information

This solves the working directory limitation for most cases!

#### Method 2: Working Directory Fallback
If session ID extraction fails, the system falls back to:
1. `X-Cwd` header (if provided by a custom client)
2. Proxy's current working directory (not Claude Code's)
3. Manual configuration override

## Data Flow Example

1. **Claude Code makes API request**
   - Contains messages array with conversation
   - Includes metadata with session ID
   - NOTE: Does NOT include working directory

2. **CCProxy intercepts request**
   - Router determines target provider/model
   - Context hooks activate

3. **Context injection**
   - Find Claude project: `/home/user/project` → `~/.claude/projects/-home--user--project`
   - Read latest JSONL session file
   - Parse messages and extract session ID
   - Inject historical context into request

4. **API call proceeds**
   - Request sent to selected provider
   - Response received

5. **Metadata recording**
   - Session ID extracted from response
   - Routing decision recorded
   - Linked to Claude Code session

## Performance Considerations

### Caching Strategy

- **LRU Cache**: Recently used sessions stay in memory
- **mtime-based invalidation**: Cache invalidates when files change
- **Async I/O**: No blocking on file operations

### Memory Management

- **Shared tokenizer cache**: Class-level caching prevents duplication
- **Limited cache size**: Configurable maximum entries
- **Lazy loading**: Context only loaded when needed

### Concurrency

- **Async throughout**: All I/O operations are async
- **Thread pool**: File operations use executor
- **File locking**: Prevents corruption from concurrent writes

## Security Considerations

1. **No credentials in context**: System never includes API keys
2. **Local file access only**: No network requests for context
3. **Read-only for Claude files**: Never modifies conversation history
4. **Atomic writes**: Metadata updates are crash-safe

## Debugging

### Enable debug logging:
```bash
export CCPROXY_DEBUG=true
```

### Check context discovery:
```python
# Logs will show:
# - Project path discovery
# - Session file selection
# - Cache hits/misses
# - Provider history
```

### Verify metadata storage:
```bash
ls -la ~/.ccproxy/metadata/
# Shows per-session JSON files
```

## Extension Points

### Custom Context Sources

Implement your own context provider:
```python
class CustomContextProvider:
    async def get_context(self, cwd: Path) -> list[Message]:
        # Your implementation
        pass
```

### Context Transformers

Process context before injection:
```python
def transform_context(messages: list[Message]) -> list[Message]:
    # Filter, modify, or enrich messages
    return messages
```

### Rule-based Context

Use different context strategies per rule:
```python
class ContextAwareRule(ClassificationRule):
    def evaluate(self, request, config):
        # Access context from request
        # Make routing decision
        pass
```

## Best Practices

1. **Keep context focused**: Use max_messages to limit size
2. **Monitor cache performance**: Check hit rates with get_cache_stats()
3. **Handle errors gracefully**: Context system never blocks requests
4. **Test with multiple projects**: Verify project discovery works
5. **Regular cleanup**: Old metadata files can be safely deleted

## Common Issues

### Context not being injected
- Check if context preservation is enabled
- Verify working directory header is present
- Ensure Claude Code project exists

### Performance degradation
- Increase cache_size if hit rate is low
- Check for large conversation histories
- Verify async I/O is working (no blocking)

### Memory usage
- Monitor tokenizer cache size
- Limit max_messages if needed
- Check for memory leaks in long-running processes

## Future Enhancements

1. **Streaming support**: Context injection for streaming responses
2. **Compression**: Reduce memory usage for large contexts
3. **Smart truncation**: Intelligent context window management
4. **Multi-project support**: Handle multiple Claude Code projects
5. **Context analytics**: Track which context influences routing

---

This context preservation system enables CCProxy to maintain conversation continuity across different LLM providers while respecting the original Claude Code conversation structure.
