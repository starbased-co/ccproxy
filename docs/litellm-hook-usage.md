# Accessing Model Configuration in LiteLLM Hooks

CCProxy exposes a public API that allows LiteLLM hooks to access model configuration and routing information. This enables advanced routing decisions based on model availability, metadata, and classification labels.

## Quick Start

Import the router in your LiteLLM CustomLogger hook:

```python
from ccproxy.llm_router import llm_router
# or
from ccproxy import llm_router
```

## Available Methods

### Get Model for Classification Label

```python
# Get model configuration for a specific classification label
model = llm_router.get_model_for_label("background")
if model:
    print(model["model_name"])  # "background"
    print(model["litellm_params"]["model"])  # "claude-3-5-haiku-20241022"
    print(model.get("model_info", {}))  # Optional metadata
```

### Get All Models

```python
# Get complete list of available models
models = llm_router.get_model_list()
# or via property
models = llm_router.model_list

# Each model has:
# - model_name: The alias name (e.g., "default", "background")
# - litellm_params: Parameters for litellm.completion()
# - model_info: Optional metadata (priority, cost, etc.)
```

### Get Model Groups

```python
# Get models grouped by underlying model
groups = llm_router.model_group_alias
# Returns: {
#     "claude-3-5-sonnet-20241022": ["default", "think"],
#     "claude-3-5-haiku-20241022": ["background"]
# }
```

### Check Model Availability

```python
# Get list of available model names
available = llm_router.get_available_models()
# Returns: ["background", "default", "think"]

# Check if specific model is available
if llm_router.is_model_available("web_search"):
    # Use web search model
    pass
```

## Example: Custom Routing Hook

```python
from litellm.integrations.custom_logger import CustomLogger
from ccproxy.llm_router import llm_router

class AdvancedRoutingHook(CustomLogger):
    def log_pre_api_call(self, model, messages, kwargs):
        # Get classification from CCProxyHandler
        classification = kwargs.get("metadata", {}).get("classification", "default")

        # Get model configuration
        model_config = llm_router.get_model_for_label(classification)
        if not model_config:
            # Fallback already handled by router
            return

        # Access model metadata for additional routing
        model_info = model_config.get("model_info", {})
        if model_info.get("priority") == "low":
            # Add delay for low priority requests
            kwargs["request_timeout"] = 30

        # Check cost per token
        if model_info.get("cost_per_token", 0) > 0.01:
            # Log expensive model usage
            self.logger.warning(f"Using expensive model: {model_config['model_name']}")
```

## Thread Safety

All public methods are thread-safe and can be called concurrently from multiple hooks. The router uses read-only access patterns to ensure data consistency.

## Configuration Hot-Reload

The router supports hot-reload of model configurations. When the YAML config changes, the router automatically updates its internal state. All subsequent calls will use the new configuration without requiring a service restart.

### Enabling Hot-Reload

To enable automatic hot-reload:

```python
from ccproxy import start_config_watcher

# Start watching for config changes
start_config_watcher()

# Your application code here...
# The router will automatically reload when config.yaml changes
```

### Manual Reload

You can also manually trigger a reload:

```python
from ccproxy import reload_router

# Manually reload router configuration
reload_router()
```

### Hot-Reload Behavior

When configuration changes are detected:

1. The ConfigWatcher detects file changes and triggers a reload after a debounce period
2. Configuration is reloaded from disk
3. Router atomically updates its internal model mappings
4. All subsequent calls use the new configuration
5. In-flight requests continue with their existing configuration

The reload is atomic and thread-safe, ensuring no requests fail during the update.
