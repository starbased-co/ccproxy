# Configuration Guide

This guide covers `ccproxy`'s configuration system, including all configuration files and their purposes.

## Overview

`ccproxy` uses three main configuration files:

1. **`config.yaml`** - LiteLLM proxy configuration (models, API keys, etc.)
2. **`ccproxy.yaml`** - ccproxy-specific settings (rules, hooks, debug options)
3. **`ccproxy.py`** - Handler instantiation for LiteLLM integration

## Installation

Install configuration templates to `~/.ccproxy/`:

```bash
ccproxy install
```

### Manual Setup

For those who prefer not to run the automated setup, you can download the files to the proper locations directly:

```bash
# Create the ccproxy configuration directory
mkdir -p ~/.ccproxy

# Download the callback file
curl -o ~/.ccproxy/ccproxy.py \
  https://raw.githubusercontent.com/starbased-co/ccproxy/main/src/ccproxy/templates/ccproxy.py

# Download the LiteLLM config
curl -o ~/.ccproxy/config.yaml \
  https://raw.githubusercontent.com/starbased-co/ccproxy/main/src/ccproxy/templates/config.yaml

# Download ccproxy's config
curl -o ~/.ccproxy/ccproxy.yaml \
  https://raw.githubusercontent.com/starbased-co/ccproxy/main/src/ccproxy/templates/ccproxy.yaml
```

## Configuration

`ccproxy` has minimal coupling between components, allowing you to disable rules, routing, and other add-ons. A minimal configuration contains:

- **Anthropic Model Deployments**: `anthropic/claude-sonnet-4-20250514` and `anthropic/claude-opus-4-1-20250805` in `config.yaml` (and `anthropic/claude-3-5-haiku-20241022` for non-essential model calls like flavor text)
- **`ccproxy.hooks.forward_oauth`**: without this in `ccproxy.yaml`, you can not use your logged in Claude Max account to make API requests

The routing model aliases `default`, `background`, and `think`, etc. and are only needed if using the rule & routing systems.

### `config.yaml` (LiteLLM Configuration)

The [LiteLLM proxy server configuration](https://docs.litellm.ai/docs/proxy/configs) includes several key components used by `ccproxy`:

- Model Deployments: Real model configurations that connect to AI providers (e.g., `claude-sonnet-4-20250514`)
- Model Aliases: ccproxy routing labels that map to deployments based on rules (e.g., `default`, `background`, `think`)
- Callbacks: Where `ccproxy` hooks into the request lifecycle (`ccproxy.handler`)

Note the distinction between deployments and aliases: model deployments are your **actual connections to AI providers**, while model aliases **map to deployments**. [See here for more information on model aliases](https://docs.litellm.ai/docs/completion/model_alias).

```yaml
# LiteLLM model configuration
model_list:
  # === Aliases ===
  # Default model for regular use
  - model_name: default
    litellm_params:
      model: claude-sonnet-4-20250514

  # Background model for low-cost operations
  - model_name: background
    litellm_params:
      model: claude-3-5-haiku-20241022

  # Thinking model for complex reasoning
  - model_name: think
    litellm_params:
      model: claude-opus-4-1-20250805

  # Large context model for >60k tokens
  - model_name: token_count
    litellm_params:
      model: gemini-2.5-pro

  # Web search model for tool usage
  - model_name: web_search
    litellm_params:
      model: gemini-2.5-flash

  # === Deployments ===
  # Anthropic provided claude models, no `api_key` needed
  - model_name: claude-sonnet-4-20250514
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_base: https://api.anthropic.com

  - model_name: claude-opus-4-1-20250805
    litellm_params:
      model: anthropic/claude-opus-4-1-20250805
      api_base: https://api.anthropic.com

  - model_name: claude-3-5-haiku-20241022
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_base: https://api.anthropic.com

  # Add any other provider/model supported by LiteLLM

  - model_name: gemini-2.5-pro
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_base: https://generativelanguage.googleapis.com
      api_key: os.environ/GOOGLE_API_KEY

# LiteLLM settings
litellm_settings:
  callbacks:
    - ccproxy.handler

general_settings:
  forward_client_headers_to_llm_api: true
```

Each `model_name` can be either:

- A [valid LiteLLM model](https://docs.litellm.ai/docs/providers) (e.g., `anthropic/claude-sonnet-4-20250514`)
- An alias to a valid LiteLLM model
- The name of a rule configured in `ccproxy.yaml` (e.g., `default`, `background`, `think`)

Rule names in `ccproxy.yaml` must correspond to model aliases in `config.yaml`. When a rule matches, `ccproxy` changes the model from Claude Code's request to the matching model alias.

#### ccproxy.py (Handler Integration)

This file is the file referenced under `litellm_settings.callbacks`, and it instantiates [the `ccproxy` handler](src/ccproxy/handler.py#L27).

```python
from ccproxy.handler import CCProxyHandler

# Create the instance that LiteLLM will use
handler = CCProxyHandler()
```

### `ccproxy.yaml` (ccproxy Configuration)

This file configures `ccproxy` systems such as routing rules and hooks.

```yaml
# ccproxy-specific configuration
ccproxy:
  debug: true

  # Processing hooks (executed in order)
  hooks:
    - ccproxy.hooks.rule_evaluator # Evaluates rules
    - ccproxy.hooks.model_router # Routes to models
    - ccproxy.hooks.forward_oauth # Forwards OAuth tokens

  # Routing rules (evaluated in order)
  rules:
    # Route high-token requests to large context model
    - name: token_count
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 60000

    # Route haiku model requests to background
    - name: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: claude-3-5-haiku-20241022

    # Route thinking requests to reasoning model
    - name: think
      rule: ccproxy.rules.ThinkingRule

    # Route web search tool usage
    - name: web_search
      rule: ccproxy.rules.MatchToolRule
      params:
        - tool_name: WebSearch

# See `litellm --help`
litellm:
  host: 127.0.0.1
  port: 4000
  num_workers: 4
  debug: true
  detailed_debug: true
```

- **`ccproxy.hooks`**: A list of hooks that are executed in series during the `async_pre_call_hook`
- **`ccproxy.rules`**: Request routing rules (evaluated in order) and parameters
- **`litellm`**: LiteLLM proxy server process (See `litellm --help`)

#### Built-in Rules

1. **TokenCountRule**: Routes based on token count threshold
2. **MatchModelRule**: Routes specific model requests
3. **ThinkingRule**: Routes requests with thinking fields
4. **MatchToolRule**: Routes based on tool usage

#### Rule Parameters

Rules accept parameters in various formats:

```yaml
# Single positional parameter
params:
  - threshold: 60000

# Multiple parameters
params:
  - param1: value1
    param2: value2

# Mixed parameters
params:
  - "positional_value"
  - keyword: "keyword_value"
```

## Request Processing Flow

1. **Request Received**: LiteLLM proxy receives request
2. **Hook Processing**: `ccproxy` hooks process the request in order:
   - `rule_evaluator` (optional): Evaluates rules to determine routing
   - `model_router` (optional): Maps rule name to model configuration
   - `forward_oauth` (required): Handles OAuth token forwarding for Anthropic API
3. **Model Selection**: Request sent to appropriate model (routed if using routing system, otherwise direct)
4. **Response**: Response returned through LiteLLM proxy

**Note**: Only OAuth forwarding is required for basic Claude Code functionality. The routing system is optional.

## Custom Rules

Create custom routing rules by implementing the `ClassificationRule` interface:

```python
from typing import Any
from ccproxy.rules import ClassificationRule
from ccproxy.config import CCProxyConfig

class CustomRule(ClassificationRule):
    def __init__(self, custom_param: str) -> None:
        self.custom_param = custom_param

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        # Custom routing logic
        return True  # Return True to use this rule's model
```

Add to `ccproxy.yaml`:

```yaml
ccproxy:
  rules:
    - name: custom_model # Must match model_name in config.yaml
      rule: myproject.CustomRule # Python import path
      params:
        - custom_param: "value"
```

## Custom Hooks

`ccproxy` provides a hook system that allows you to extend and customize its behavior. Hooks are Python functions or classes that can intercept and modify requests, implement custom logging, filtering, or integrate with external systems.

**Minimal requirement for Claude Code:**

- `ccproxy.hooks.forward_oauth` - Forwards OAuth tokens for Anthropic API requests

**Optional routing system hooks:**

- `ccproxy.hooks.rule_evaluator` - Evaluates classification rules to determine routing
- `ccproxy.hooks.model_router` - Routes requests to appropriate models based on classification

The routing system is an extension that provides intelligent request routing, but Claude Code can function with just OAuth token forwarding.

### Hook Signature

All hooks must follow this signature:

```python
from typing import Any
from ccproxy.handler import CCProxyHandler

def hook_name(
    data: dict[str, Any],
    user_api_key_dict: dict[str, Any],
    handler: CCProxyHandler,
    **kwargs: Any
) -> dict[str, Any]:
    """
    Args:
        data: Request data dictionary containing model, messages, metadata, etc.
        user_api_key_dict: Dictionary containing user API key information
        handler: CCProxyHandler instance providing access to:
            - handler.classifier: RequestClassifier for rule evaluation
            - handler.router: ModelRouter for model routing
            - handler.hooks: List of configured hooks
        **kwargs: Additional keyword arguments for future extensibility

    Returns:
        Modified request data dictionary
    """
    # Access handler components as needed
    classifier = handler.classifier
    router = handler.router

    # Your hook logic here
    return data
```

### Example: Request Logging Hook

```python
# ~/.ccproxy/my_hooks.py
import logging
from typing import Any
from ccproxy.handler import CCProxyHandler

logger = logging.getLogger(__name__)

def request_logger(data: dict[str, Any], user_api_key_dict: dict[str, Any], handler: CCProxyHandler, **kwargs: Any) -> dict[str, Any]:
    """Log detailed request information.

    Args:
        data: Request data dictionary
        user_api_key_dict: User API key information
        handler: CCProxyHandler instance providing access to classifier, router, and other components
        **kwargs: Additional keyword arguments for future extensibility
    """
    metadata = data.get("metadata", {})
    logger.info(f"Processing request for model: {data.get('model')}")

    # You can access handler components if needed:
    # classifier = handler.classifier
    # router = handler.router

    return data
```

Add to `ccproxy.yaml`:

```yaml
ccproxy:
  hooks:
    - ccproxy.hooks.rule_evaluator # Optional: Evaluate classification rules
    - ccproxy.hooks.model_router # Optional: Route to appropriate model
    - my_hooks.request_logger # Optional: Your custom logging hook
    - ccproxy.hooks.forward_oauth # Required: Handle OAuth tokens for Anthropic API
```

### Class-Based Hooks

For more complex functionality, you can create class-based hooks using the `BaseHook` abstract class:

```python
# ~/.ccproxy/my_hooks.py
from typing import Any
from ccproxy.hooks import BaseHook
from ccproxy.handler import CCProxyHandler

class MetricsHook(BaseHook):
    """Hook that collects request metrics."""

    def __init__(self):
        self.request_count = 0
        self.total_tokens = 0

    def __call__(
        self,
        data: dict[str, Any],
        user_api_key_dict: dict[str, Any],
        handler: CCProxyHandler,
        **kwargs: Any
    ) -> dict[str, Any]:
        """Collect metrics and pass through request."""
        self.request_count += 1

        # Estimate token count if available
        messages = data.get("messages", [])
        estimated_tokens = sum(len(str(msg)) // 4 for msg in messages)
        self.total_tokens += estimated_tokens

        # Add metrics to metadata for downstream hooks
        if "metadata" not in data:
            data["metadata"] = {}

        data["metadata"]["request_number"] = self.request_count
        data["metadata"]["estimated_tokens"] = estimated_tokens

        return data

# Create instance for ccproxy to use
metrics_collector = MetricsHook()
```

Register the class-based hook:

```yaml
ccproxy:
  hooks:
    - ccproxy.hooks.rule_evaluator # Optional: Routing system
    - ccproxy.hooks.model_router # Optional: Routing system
    - my_hooks.metrics_collector # Optional: Custom class-based hook
    - ccproxy.hooks.forward_oauth # Required: OAuth forwarding
```

## Debugging

Enable debug output in `ccproxy.yaml`:

```yaml
litellm:
  debug: true
  detailed_debug: true

ccproxy:
  debug: true
```

This provides detailed logging for request processing and routing decisions.

## Common Patterns

### Token-Based Routing

Route expensive requests to cost-effective models:

```yaml
rules:
  - name: large_context
    rule: ccproxy.rules.TokenCountRule
    params:
      - threshold: 50000

  - name: default
    rule: ccproxy.rules.DefaultRule
```

### Tool-Based Routing

Route tool usage to specialized models:

```yaml
rules:
  - name: web_search
    rule: ccproxy.rules.MatchToolRule
    params:
      - tool_name: WebSearch

  - name: code_execution
    rule: ccproxy.rules.MatchToolRule
    params:
      - tool_name: CodeExecution
```

### Model-Specific Routing

Route specific model requests:

```yaml
rules:
  - name: background
    rule: ccproxy.rules.MatchModelRule
    params:
      - model_name: claude-3-5-haiku-20241022

  - name: reasoning
    rule: ccproxy.rules.MatchModelRule
    params:
      - model_name: claude-opus-4-1-20250805
```
