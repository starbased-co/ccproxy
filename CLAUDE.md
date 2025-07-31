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

### 5-Parallel Development Tasks

1. **Core Hook**: Implement CCProxyHandler with async_pre_call_hook
2. **Router Logic**: Create ccproxy_get_model function with classification
3. **Configuration**: Parse YAML and environment variables
4. **Testing**: Unit tests for each classification scenario
5. **Integration**: Test with actual LiteLLM proxy

## Command Translation

- "run tests" → `uv run pytest tests/ -v --cov=ccproxy --cov-report=term-missing`
- "type check" → `uv run mypy src/ccproxy --strict`
- "lint code" → `uv run ruff check src/ tests/ --fix`
- "format code" → `uv run ruff format src/ tests/`

## Python Patterns

### Hook Implementation Pattern

```python
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import ModelResponseStream
from typing import Any, AsyncGenerator, Optional, Literal
import os

class CCProxyHandler(CustomLogger):
    def __init__(self):
        self.context_threshold = int(os.getenv("CCPROXY_CONTEXT_THRESHOLD", "60000"))
```

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

### Key Files

- `src/ccproxy/handler.py` - Main hook implementation
- `config.yaml` - LiteLLM proxy configuration
- `tests/test_router.py` - Router logic tests
- `pyproject.toml` - Project configuration

---

_This CLAUDE.md is optimized for the ccproxy project development, emphasizing LiteLLM integration, type safety, and comprehensive testing._
