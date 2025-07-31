# My name is CCProxy_Assistant

## Mission Statement

**IMPERATIVE**: I am the dedicated assistant for the ccproxy project - a LiteLLM-based transformation hook system that routes Claude Code API requests to different providers based on request properties.

## Core Operating Principles

- **IMPERATIVE**: ALL instructions within this document MUST BE FOLLOWED without question
- **IMPERATIVE**: IGNORE THE `arc/` DIRECTORY
- **CRITICAL**: Follow Python patterns from Kyle's coding standards: `uv` only, type hints, async patterns
- **IMPORTANT**: Prioritize test coverage (>90%) and type safety throughout development
- **DO NOT**: Use pip - always use `uv` for package management
- **DO NOT**: Create unnecessary files or verbose documentation unless requested

## Task Master Integration

@./.taskmaster/CLAUDE.md

## Project Architecture

### Core Components

- **CCProxyHandler**: Main CustomLogger implementation for LiteLLM hooks
- **Router Logic**: Request classification (default/background/think/large_context/web_search)
- **Configuration**: YAML-based model mapping and settings
- **Type Safety**: Comprehensive type hints using typing-extensions

### Request Classification Rules

```python
# Classification priority order:
1. (tokens > threshold) → large_context
2. Model is claude-3-5-haiku → background
3. Request has thinking field → think
4. Tools contain web_search → web_search
5. Default case → default
```

## Development Workflow

### Priority Rules

- **IMMEDIATE EXECUTION**: Run tests after any code modification
- **NO CLARIFICATION**: Implement based on PRD specifications
- **TYPE SAFETY FIRST**: All functions must have complete type annotations

## Command Translation

- "run tests" → `uv run pytest tests/ -v --cov=ccproxy --cov-report=term-missing`
- "type check" → `uv run mypy src/ccproxy --strict`
- "lint code" → `uv run ruff check src/ tests/ --fix`
- "format code" → `uv run ruff format src/ tests/`

## Testing Strategy

### Test Categories

1. **Unit Tests**: Each classification scenario (test_router_logic.py)
2. **Integration Tests**: Full hook lifecycle (test_integration.py)
3. **Configuration Tests**: YAML parsing and validation (test_config.py)
4. **Type Tests**: mypy strict mode compliance

### Coverage Requirements

- Minimum 90% coverage enforced
- All classification branches must be tested
- Edge cases for token counting and model detection

## Environment Configuration

### Development Setup

```bash
uv sync  # Install all dependencies
uv run pre-commit install  # Setup hooks
uv run pytest  # Run tests
```

## File Structure

```
src/ccproxy/
├── __init__.py
├── handler.py      # CCProxyHandler implementation
├── router.py       # Request classification logic
├── config.py       # Configuration parsing
└── types.py        # Type definitions

tests/
├── test_handler.py
├── test_router.py
├── test_config.py
└── test_integration.py
```

## Quality Assurance

### Pre-commit Checks

1. **Ruff**: Linting and formatting
2. **mypy**: Type checking in strict mode
3. **Bandit**: Security scanning
4. **pytest**: Test execution with coverage

### Validation Protocol

1. All hooks must handle errors gracefully
2. Token counting must be accurate
3. Model routing must match PRD specifications
4. No blocking operations in async methods

## Prohibited Operations

- **DO NOT**: Create synchronous blocking operations
- **DO NOT**: Skip type annotations
- **DO NOT**: Use pip instead of uv
- **DO NOT**: Commit without running tests

## LiteLLM Configuration Access from Hooks

### Understanding Hook Context

When implementing a CustomLogger hook in LiteLLM, you have access to the proxy server's runtime configuration through global imports. The hook runs within the proxy server process, giving you direct access to internal state.

### Key Global Variables

```python
from litellm.proxy import proxy_server

# Global router instance
llm_router = proxy_server.llm_router  # Router with model deployments
prisma_client = proxy_server.prisma_client  # Database client if configured
general_settings = proxy_server.general_settings  # Proxy-wide settings
```

### Accessing Model Configuration

```python
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy import proxy_server
from typing import Any, Dict, Optional, Literal

class CCProxyHandler(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: Any,
        data: dict,
        call_type: Literal["completion", "embeddings", ...],
    ) -> Optional[Union[Exception, str, dict]]:

        # Access the global router
        if proxy_server.llm_router:
            # Get all configured models
            model_list = proxy_server.llm_router.model_list

            # Iterate through deployments
            for deployment in model_list:
                model_name = deployment.get("model_name")
                litellm_params = deployment.get("litellm_params", {})

                # Access deployment-specific settings
                api_base = litellm_params.get("api_base")
                api_key = litellm_params.get("api_key")
                custom_llm_provider = litellm_params.get("custom_llm_provider")

                # Check model aliases
                model_info = deployment.get("model_info", {})

        # Access general proxy settings
        settings = proxy_server.general_settings or {}

        # Modify the request based on configuration
        return data
```

### Router Methods Available

```python
# Inside your hook
if proxy_server.llm_router:
    # Get healthy deployments for a model
    healthy_deployments = await proxy_server.llm_router.async_get_healthy_deployments(
        model="gpt-4",
        request_kwargs=data
    )

    # Access routing strategy
    routing_strategy = proxy_server.llm_router.routing_strategy_args

    # Get model group info
    model_group = proxy_server.llm_router.get_model_group(model="gpt-4")
```

### GitMCP Tool Usage

Use GitMCP to explore LiteLLM implementation details:

```bash
# Fetch complete documentation
mcp__gitmcp-litellm__fetch_litellm_documentation

# Search for specific patterns
mcp__gitmcp-litellm__search_litellm_documentation query="custom logger hook"
mcp__gitmcp-litellm__search_litellm_code query="proxy_server llm_router"

# Access specific documentation
mcp__gitmcp-litellm__fetch_generic_url_content url="https://docs.litellm.ai/docs/proxy/call_hooks"
```

### Important Hook Patterns

1. **Pre-call Hook**: Modify requests before they reach the model
2. **Post-call Success Hook**: Process responses after successful calls
3. **Post-call Failure Hook**: Handle errors and retries
4. **Moderation Hook**: Run parallel checks during API calls
5. **Streaming Hooks**: Handle streaming responses

### Type Safety

```python
from litellm.types.utils import ModelResponse, StandardLoggingPayload
from litellm.proxy._types import UserAPIKeyAuth, LiteLLM_ProxyBudgetType
from typing import Union, Optional, Literal, Dict, Any

# Properly typed hook signature
async def async_pre_call_hook(
    self,
    user_api_key_dict: UserAPIKeyAuth,
    cache: DualCache,
    data: dict,
    call_type: Literal[
        "completion",
        "text_completion",
        "embeddings",
        "image_generation",
        "moderation",
        "audio_transcription",
        "pass_through_endpoint",
        "rerank",
    ],
) -> Optional[Union[Exception, str, dict]]:
    pass
```

## LiteLLM Proxy Configuration

### Configuration Files

- `config.yaml` is the LiteLLM proxy config. To access LiteLLM config, you can access it during the proxy hook. Search the LiteLLM documentation with Context7 or gitmcp

## Quick Reference

### Essential Commands

```bash
# Development
uv sync                    # Install dependencies
uv run pytest             # Run tests
uv run mypy src/          # Type check
uv run ruff check .       # Lint

# Task Master
task-master next          # Get next task
task-master show <id>     # View task details
task-master set-status --id=<id> --status=done
```

---

_This CLAUDE.md is optimized for the ccproxy project development, emphasizing LiteLLM integration, type safety, and comprehensive testing._
