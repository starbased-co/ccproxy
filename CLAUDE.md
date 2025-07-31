# My name is CCProxy_Assistant

## Mission Statement

**IMPERATIVE**: I am the dedicated assistant for the ccproxy project - a LiteLLM-based transformation hook system that routes Claude Code API requests to different providers based on request properties.

## Core Operating Principles

- **IMPERATIVE**: ALL instructions within this document MUST BE FOLLOWED without question
- **CRITICAL**: Follow Python patterns from Kyle's coding standards: `uv` only, type hints, async patterns
- **IMPORTANT**: Prioritize test coverage (>90%) and type safety throughout development
- **DO NOT**: Use pip - always use `uv` for package management
- **DO NOT**: Create unnecessary files or verbose documentation unless requested

## Task Master Integration

@./.taskmaster/CLAUDE.md

## Project Architecture

### Core Components

- **CCProxyHandler**: Main CustomLogger implementation for LiteLLM hooks
- **Router**: Dynamic rule-based request classification system
- **Configuration**: Dual YAML system (ccproxy.yaml + config.yaml)
- **Rules Engine**: Extensible classification rules with boolean returns
- **Type Safety**: Comprehensive type hints with strict mypy checking

### Configuration System

- **ccproxy.yaml**: Contains ccproxy-specific settings and rule definitions
- **config.yaml**: LiteLLM proxy configuration with model deployments
- Rules are dynamically loaded using Python import paths
- Labels in ccproxy rules must match model_name entries in LiteLLM's model_list

### Classification Architecture

```python
# Dynamic rule evaluation:
1. Rules are loaded from ccproxy.yaml with parameters
2. Each rule returns boolean (True = use this label's model)
3. First matching rule determines the routing label
4. Label is mapped to model via LiteLLM's model_list
5. Default model used if no rules match
```

### Built-in Rules

- **TokenCountRule**: Routes based on token count threshold
- **MatchModelRule**: Routes based on model name pattern matching
- **ThinkingFieldRule**: Routes when request contains thinking field
- **WebSearchToolRule**: Routes when web_search tool is present

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
├── router.py       # Dynamic rule-based routing engine
├── config.py       # Configuration management (singleton)
├── rules.py        # Classification rule implementations
├── types.py        # Type definitions (currently unused)
└── cli.py          # Command-line interface

tests/
├── test_handler.py        # Hook integration tests
├── test_router.py         # Router logic tests
├── test_config.py         # Configuration tests
├── test_rules.py          # Rule implementation tests
├── test_classifier.py     # Rule classification tests
├── test_integration.py    # End-to-end tests
└── test_*.py              # Additional test modules

stubs/                      # Type stubs for external dependencies
├── litellm/
│   └── proxy.pyi
└── pydantic_settings.pyi
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

## Configuration Files

### ccproxy.yaml Structure

```yaml
ccproxy:
  debug: false
  metrics_enabled: true
  rules:
    - label: large_context # Must match a model_name in config.yaml
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 80000
    - label: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: "claude-3-5-haiku"
    - label: think
      rule: ccproxy.rules.ThinkingFieldRule
    - label: web_search
      rule: ccproxy.rules.WebSearchToolRule
```

### config.yaml (LiteLLM)

```yaml
model_list:
  - model_name: default # Label referenced by ccproxy rules
    litellm_params:
      model: claude-3-5-sonnet-20241022
  - model_name: large_context # Matches label in ccproxy.yaml
    litellm_params:
      model: gemini-2.0-flash-exp
  # ... additional models
```

### Key Configuration Concepts

- **Label Matching**: Labels in ccproxy.yaml rules MUST have corresponding model_name entries in config.yaml
- **Dynamic Loading**: Rules are loaded at runtime using Python import paths
- **Parameter Flexibility**: Rules can accept positional args, keyword args, or mixed parameters
- **Singleton Pattern**: Configuration is loaded once and shared across the application

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

### Creating Custom Rules

```python
from typing import Any
from ccproxy.rules import ClassificationRule
from ccproxy.config import CCProxyConfig

class MyCustomRule(ClassificationRule):
    """Custom rule implementation."""

    def __init__(self, my_param: str) -> None:
        self.my_param = my_param

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        """Return True to use this rule's label."""
        # Your custom logic here
        return "my_condition" in request
```

Then add to ccproxy.yaml:

```yaml
ccproxy:
  rules:
    - label: my_custom_label
      rule: mymodule.MyCustomRule
      params:
        - my_param: "value"
```

### Testing Patterns

- **Test Isolation**: Always use `clear_config_instance()` and `clear_router()` in cleanup
- **Mock proxy_server**: Use `unittest.mock` to simulate LiteLLM runtime environment
- **Type Stubs**: Located in `stubs/` directory for external dependencies

---

_This CLAUDE.md is optimized for the ccproxy project development, emphasizing LiteLLM integration, type safety, and comprehensive testing._
