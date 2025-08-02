# CCProxy Context Preservation System - Complete Code Tour

## Overview

The CCProxy context preservation system enables Claude Code conversations to maintain context across different LLM providers. It intercepts requests through LiteLLM hooks, extracts Claude Code session information, reads conversation history from JSONL files, and injects that context into requests before they're routed to various providers.

## Architecture

### Normal Claude Code Operation (Without CCProxy)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                              │
│  • Maintains conversation in ~/.claude/projects/*/SESSION.jsonl│
│  • Sends ONLY current message to API                           │
│  • Context exists locally but isn't sent to provider           │
└────────────────┬───────────────────────────────────────────────┘
                 │ API Request (current message only)
                 │ {
                 │   "messages": [{"role": "user", "content": "..."}],
                 │   "metadata": {"user_id": "user_..._session_xyz"}
                 │ }
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Anthropic API                                │
│  • Receives only the current message                           │
│  • No awareness of conversation history                        │
│  • Each request is stateless                                   │
└─────────────────────────────────────────────────────────────────┘

Problem: When switching providers, all context is lost!
```

### With CCProxy Context Preservation

```
┌────────────────────────────────────────────────────────────────┐
│                        Claude Code                             │
│  • Embeds session ID in metadata.user_id                       │
│  • Stores conversations in ~/.claude/projects/*/SESSION.jsonl  │
└────────────────┬───────────────────────────────────────────────┘
                 │ API Request
                 ▼
┌───────────────────────────────────────────────────────────────┐
│                    LiteLLM Proxy Server                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                  CCProxyHandler Hooks                   │  │
│  │                                                         │  │
│  │  1. pre_call_hook → context_injection_hook              │  │
│  │     • Extract session ID from metadata.user_id          │  │
│  │     • Find and read JSONL conversation file             │  │
│  │     • Inject historical messages into request           │  │
│  │                                                         │  │
│  │  2. post_call_success_hook → context_recording_hook     │  │
│  │     • Record routing decision to SQLite                 │  │
│  │     • Track which provider handled each request         │  │
│  └─────────────────────────────────────────────────────────┘  │
└────────────────┬──────────────────────────────────────────────┘
                 │ Enriched Request
                 │ {
                 │   "messages": [
                 │     {"role": "user", "content": "previous msg 1"},
                 │     {"role": "assistant", "content": "response 1"},
                 │     {"role": "user", "content": "current msg"}
                 │   ]
                 │ }
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              Target LLM Provider (Anthropic, OpenAI, etc.)      │
│  • Receives full conversation history                          │
│  • Can maintain context across provider switches               │
│  • Stateful conversation experience                            │
└─────────────────────────────────────────────────────────────────┘

Solution: Context preserved across all providers!
```

## Core Components

### 1. Context Hooks (`src/ccproxy/context_hooks.py`)

The main entry points for context preservation:

```python
async def context_injection_hook(data: dict[str, Any], user_api_key_dict: Any) -> dict[str, Any]:
    """Pre-call hook that injects conversation context."""
    # 1. Check if context preservation is enabled
    config = get_config()
    if not config or not config.context.get("enabled", False):
        return data

    # 2. Extract session ID from metadata.user_id
    # Claude Code format: user_<hash>_account_<uuid>_session_<session-id>
    session_id = None
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id", "")
    if user_id and "_session_" in user_id:
        parts = user_id.split("_session_")
        if len(parts) == 2:
            session_id = parts[1]

    # 3. Get conversation context
    context_messages = await manager.get_context(cwd, chat_id, session_id)

    # 4. Inject context messages before current messages
    if context_messages:
        enriched_messages = [msg.to_dict() for msg in context_messages]
        enriched_messages.extend(data.get("messages", []))
        data["messages"] = enriched_messages
```

### 2. Context Manager (`src/ccproxy/context_manager.py`)

Orchestrates the context retrieval process:

```python
@attrs.define(slots=True)
class ContextManager:
    """Coordinates Claude Code conversation reading with provider metadata."""

    locator: ClaudeProjectLocator
    reader: ClaudeCodeReader
    store: ProviderMetadataStore
    cache_size: int = 256

    async def get_context(self, cwd: Path, chat_id: str | None = None,
                         session_id: str | None = None) -> list[Message]:
        """Get conversation context using session ID or directory discovery."""

        # Try session ID lookup first (fast path)
        if session_id:
            session_file = await self._find_session_by_id(session_id)
            if session_file:
                return self._read_cached_session(session_file)

        # Fallback to directory-based discovery
        project_path = self.locator.find_project_path(cwd)
        if project_path:
            session_files = self.locator.get_session_files(project_path)
            if session_files:
                return self._read_cached_session(session_files[-1])

        return []

    async def _find_session_by_id(self, session_id: str) -> Path | None:
        """Search all Claude Code projects for a session file."""
        for project_dir in self.locator.projects_dir.iterdir():
            if project_dir.is_dir():
                session_file = project_dir / f"{session_id}.jsonl"
                if session_file.exists():
                    return session_file
        return None
```

### 3. Claude Integration (`src/ccproxy/claude_integration.py`)

Handles Claude Code's file formats and project structure:

```python
@attrs.define(slots=True, frozen=True)
class Message:
    """Represents a single message in a Claude conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    uuid: str
    session_id: str = ""
    cwd: str | None = None
    model: str | None = None
    type: str | None = None

@attrs.define(slots=True)
class ClaudeProjectLocator:
    """Discovers Claude Code project directories."""

    claude_dir: Path = attrs.field(
        default=Path.home() / ".claude",
        converter=Path
    )

    def find_project_path(self, cwd: Path) -> Path | None:
        """Find Claude project containing the working directory."""
        # Walk up from cwd looking for a .claude-files marker
        current = cwd
        while current != current.parent:
            project_name = self._path_to_project_name(current)
            potential_project = self.projects_dir / project_name

            if potential_project.exists():
                # Verify with .claude-files marker
                marker = potential_project / ".claude-files" / current.name
                if marker.exists():
                    return potential_project

            current = current.parent

class ClaudeCodeReader:
    """Reads Claude Code JSONL conversation files."""

    def read_conversation(self, session_file: Path) -> Conversation:
        """Parse JSONL format with content blocks."""
        messages = []
        session_id = session_file.stem

        with session_file.open("r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)

                # Handle content blocks format
                content = self._extract_content(entry.get("content", []))

                messages.append(Message(
                    role=entry["role"],
                    content=content,
                    timestamp=entry.get("createdAt", ""),
                    uuid=entry.get("uuid", ""),
                    session_id=session_id,
                    cwd=entry.get("cwd"),
                    model=entry.get("model"),
                    type=entry.get("type", entry["role"])
                ))

        return Conversation(messages=messages, session_id=session_id)
```

### 4. Provider Metadata Store (`src/ccproxy/provider_metadata.py`)

Tracks routing decisions for debugging and analysis:

```python
@attrs.define(slots=True)
class ProviderMetadataStore:
    """SQLite-based storage for routing decisions."""

    db_path: Path = attrs.field(
        default=Path.home() / ".ccproxy" / "routing_history.db"
    )

    async def record_routing_decision(self, decision: RoutingDecision) -> None:
        """Store which provider handled each request."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("""
                INSERT INTO routing_decisions
                (session_id, provider, model, request_id, selected_by_rule,
                 metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.session_id,
                decision.provider,
                decision.model,
                decision.request_id,
                decision.selected_by_rule,
                json.dumps(decision.metadata),
                decision.created_at.isoformat()
            ))
            await db.commit()
```

## Key Features

### 1. Session ID Extraction

Claude Code embeds session information in the `metadata.user_id` field:

```
user_<hash>_account_<uuid>_session_<session-id>
```

This allows direct lookup of JSONL files without needing working directory information.

### 2. Directory-Based Discovery

As a fallback, the system can discover Claude Code projects by:

1. Walking up from the current working directory
2. Converting paths to project names (e.g., `/home/user/project` → `home-user-project`)
3. Checking for `.claude-files` markers to verify project ownership

### 3. Performance Optimization

- **LRU Caching**: Session files are cached with mtime-based invalidation
- **Async I/O**: All file operations use asyncio for non-blocking execution
- **Early Returns**: Fast paths for session ID lookups avoid directory traversal

### 4. Error Resilience

- Graceful fallbacks at every level
- Comprehensive error logging
- Request processing continues even if context injection fails

## Configuration

Enable context preservation in `ccproxy.yaml`:

```yaml
ccproxy:
  context:
    enabled: true
    max_messages: 50 # Optional limit
```

## Testing

The system includes comprehensive tests:

1. **Unit Tests**: Mock-based tests for each component
2. **Integration Tests**: End-to-end hook lifecycle testing
3. **Session ID Tests**: Extraction and lookup validation
4. **Performance Tests**: Cache effectiveness measurements

## Usage Flow

1. **Request Arrives**: Claude Code sends a request with session ID in metadata
2. **Hook Activation**: `context_injection_hook` extracts the session ID
3. **Session Lookup**: `_find_session_by_id` searches all projects for matching JSONL
4. **Content Reading**: `ClaudeCodeReader` parses the conversation history
5. **Context Injection**: Historical messages are prepended to the request
6. **Provider Routing**: Enriched request continues to the selected provider
7. **Decision Recording**: Post-call hook records which provider handled the request

## Benefits

- **Seamless Context**: Users experience consistent conversations across providers
- **Provider Flexibility**: Switch between models without losing context
- **Debugging Support**: Complete routing history for troubleshooting
- **Performance**: Minimal overhead with effective caching
- **Reliability**: Multiple fallback mechanisms ensure robustness

