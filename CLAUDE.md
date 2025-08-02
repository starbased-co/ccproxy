# `ccproxy` Assistant Instructions

## Project Overview

**`ccproxy`** is a LiteLLM-based transformation hook system that intelligently routes Claude Code API requests to different AI providers based on request properties. This document contains instructions for AI assistants working with the `ccproxy` codebase.

## Version

**Current Version**: v1.0.0

## Core Operating Principles

- **IMPERATIVE**: Follow all instructions in this document precisely
- **CRITICAL**: Maintain Python best practices: type hints, async patterns, comprehensive testing
- **IMPORTANT**: Prioritize code quality with >90% test coverage and strict type safety
- **MANDATORY**: Use `uv` for Python package management (never pip)
- **REQUIRED**: Keep responses concise and focused on the task at hand

## Key Dependencies

- **LiteLLM**: The core proxy framework for unified LLM API access
- **Tyro**: Modern CLI framework for command-line interface
- **PyYAML**: Configuration file parsing
- **tiktoken**: Accurate token counting for request routing
- **attrs**: Data class definitions with validation

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
- `~/.ccproxy` is the project's default `config_dir`
- The files in `./src/ccproxy/templates/{ccproxy.py,ccproxy.yaml,config.yaml}` are symlinked to `~/.ccproxy/{ccproxy.py,ccproxy.yaml,config.yaml}`

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

1. **TokenCountRule**: Routes requests exceeding a token threshold to high-capacity models
2. **MatchModelRule**: Routes based on the requested model name (e.g., claude-3-5-haiku)
3. **ThinkingRule**: Routes requests containing a "thinking" field to specialized models
4. **MatchToolRule**: Routes based on tool usage (e.g., WebSearch tool)

## Development Guidelines

### Code Quality Standards

- **Test First**: Run tests after any code modification (`uv run pytest`)
- **Type Safety**: All functions must have complete type annotations
- **Error Handling**: All hooks must handle errors gracefully
- **Async Only**: No blocking operations in async methods
- **Documentation**: Code should be self-documenting through clear naming

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

## Installation & Setup

### For Users

```bash
# Install from PyPI
uv tool install ccproxy
# or
pipx install ccproxy

# Run automated setup
ccproxy install
```

### For Development

```bash
# Clone repository
git clone https://github.com/yourusername/ccproxy.git
cd ccproxy

# Install development dependencies
uv sync
uv run pre-commit install

# Run tests
uv run pytest
```

## File Structure

```
src/ccproxy/
├── __init__.py
├── handler.py      # CCProxyHandler implementation
├── router.py       # Dynamic rule-based routing engine
├── config.py       # Configuration management (singleton)
├── rules.py        # Classification rule implementations
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

## Best Practices

### DO
- ✅ Use async/await for all I/O operations
- ✅ Add comprehensive type hints to all functions
- ✅ Handle errors gracefully with proper logging
- ✅ Test edge cases and error conditions
- ✅ Follow existing code patterns and conventions

### DON'T
- ❌ Create synchronous blocking operations
- ❌ Skip type annotations
- ❌ Use pip (always use uv)
- ❌ Commit without running tests
- ❌ Access LiteLLM internals directly (use proxy_server)

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

### LiteLLM Documentation Resources

For detailed LiteLLM information:
- Official Documentation: https://docs.litellm.ai/
- Custom Logger Hooks: https://docs.litellm.ai/docs/proxy/call_hooks
- Proxy Configuration: https://docs.litellm.ai/docs/proxy/configs

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
  rules:
    - label: token_count # Must match a model_name in config.yaml
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 60000
    - label: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: "claude-3-5-haiku-20241022"
    - label: think
      rule: ccproxy.rules.ThinkingRule
    - label: web_search
      rule: ccproxy.rules.MatchToolRule
      params:
        - tool_name: "WebSearch"
```

### config.yaml (LiteLLM)

```yaml
model_list:
  - model_name: default # Default routing
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: ${ANTHROPIC_API_KEY}

  - model_name: token_count # For large context requests
    litellm_params:
      model: google/gemini-2.0-flash-exp
      api_key: ${GOOGLE_API_KEY}

  - model_name: background # For claude-3-5-haiku requests
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: ${ANTHROPIC_API_KEY}

  # ... additional models for think, web_search, etc.

litellm_settings:
  callbacks: custom_callbacks.proxy_handler_instance
```

### Key Configuration Concepts

- **Label Matching**: Labels in ccproxy.yaml rules MUST have corresponding model_name entries in config.yaml
- **Dynamic Loading**: Rules are loaded at runtime using Python import paths
- **Parameter Flexibility**: Rules can accept positional args, keyword args, or mixed parameters
- **Singleton Pattern**: Configuration is loaded once and shared across the application

## Quick Reference

### Essential Commands

```bash
# Installation & Setup
ccproxy install           # Set up configuration files
ccproxy install --force   # Overwrite existing files

# Running the Proxy
ccproxy start           # Start proxy in foreground
ccproxy start --detach  # Start proxy in background
ccproxy stop              # Stop background proxy
ccproxy logs -f           # Follow proxy logs

# Development Commands
uv sync                   # Install dependencies
uv run pytest             # Run tests
uv run mypy src/          # Type check
uv run ruff check .       # Lint code
uv run ruff format .      # Format code
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
- **Coverage Target**: Maintain >90% test coverage across all modules

## Production Deployment

### Environment Setup

1. **API Keys**: Set all required environment variables:
   ```bash
   export ANTHROPIC_API_KEY="your-key"
   export GOOGLE_API_KEY="your-key"  # If using Gemini
   # Add other provider keys as needed
   ```

2. **Configuration**: Place configuration files in `~/.ccproxy/`:
   - `ccproxy.yaml` - Routing rules
   - `config.yaml` - LiteLLM configuration
   - `custom_callbacks.py` - Hook initialization

3. **Running in Production**:
   ```bash
   # Start with proper environment
   cd ~/.ccproxy
   litellm --config config.yaml --port 4000

   # Or use ccproxy CLI
   ccproxy start --detach
   ```

### Performance Considerations

- Token counting is performed on every request - ensure adequate CPU
- Rules are evaluated in order - place most common rules first
- Use debug mode sparingly in production (impacts performance)
- Monitor memory usage with large context requests

### Troubleshooting

Common issues and solutions:

1. **Import Errors**: Ensure ccproxy is installed in the Python environment
2. **Routing Failures**: Check debug logs for rule evaluation details
3. **API Key Issues**: Verify environment variables are set correctly
4. **Performance**: Disable debug mode and optimize rule ordering

---

_`ccproxy` v1.0.0 - Production-ready LiteLLM transformation hook system_

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
