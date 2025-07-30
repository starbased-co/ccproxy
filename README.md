# `ccproxy`

A LiteLLM-based transformation hook system that routes Claude Code API requests to different providers based on request properties.

## Installation

```bash
uv tool install ccproxy
```

## Quick Start

To get started, a [LiteLLM `config.yaml`](https://docs.litellm.ai/docs/proxy/configs) is required. An [example](./config.yaml.example) is provided:

```

```

```python
from ccproxy import CCProxyHandler

# Initialize the handler
handler = CCProxyHandler()

# Use with LiteLLM proxy
# The handler will automatically route requests based on configured rules
```

## Routing Rules

- Long context (>60k tokens, configurable) → `large_context`
- Model is `claude-3-5-haiku` → `background`
- Request has thinking field → `think`
- Tools contain `web_search` → `web_search`
- Default case → `default`
