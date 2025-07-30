# ccproxy

A LiteLLM-based transformation hook system that routes Claude Code API requests to different providers based on request properties.

## Features

- Context-aware routing based on token count, model type, and request features
- Seamless integration with LiteLLM proxy as a CustomLogger
- Configurable routing rules via YAML and environment variables
- Built-in metrics collection and monitoring
- Production-ready with comprehensive testing

## Installation

```bash
pip install ccproxy
```

## Quick Start

```python
from ccproxy import CCProxyHandler

# Initialize the handler
handler = CCProxyHandler()

# Use with LiteLLM proxy
# The handler will automatically route requests based on configured rules
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following:

```bash
# Core Configuration
LITELLM_CONFIG_PATH=./config.yaml
CCPROXY_CONTEXT_THRESHOLD=60000

# API Keys (configure as needed)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
# ... see .env.example for all options

# Monitoring
METRICS_PORT=9090
LOG_LEVEL=INFO
```

### Configuration Access Patterns

CCProxy provides two patterns for accessing configuration:

#### 1. Singleton Pattern (Recommended for most use cases)

```python
from ccproxy import get_config, reload_config

# Get the singleton config instance
config = get_config()
print(f"Context threshold: {config.context_threshold}")

# Manually reload config
new_config = reload_config()
```

#### 2. Dependency Injection Pattern (For testing and multiple configs)

```python
from ccproxy import ConfigProvider, CCProxyConfig

# Create a provider with custom config
provider = ConfigProvider(CCProxyConfig(context_threshold=50000))

# Use in a service
class MyService:
    def __init__(self, config_provider: ConfigProvider):
        self._config_provider = config_provider

    def process(self):
        config = self._config_provider.get()
        # Use config...
```

### Hot-Reload Configuration

CCProxy supports hot-reloading of configuration files without restarting the service. To enable:

1. Set `reload_config_on_change: true` in your config.yaml
2. Start the config watcher in your application:

```python
from ccproxy import start_config_watcher, get_config

# Start watching for config changes
start_config_watcher()

# Your config will automatically reload when the file changes
config = get_config()
```

See `examples/hot_reload_demo.py` and `examples/config_usage_demo.py` for complete demonstrations.

## Routing Rules

- Long context (>60k tokens) → `large_context`
- Model is `claude-3-5-haiku` → `background`
- Request has thinking field → `think`
- Tools contain `web_search` → `web_search`
- Default case → `default`

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

Private project - all rights reserved
