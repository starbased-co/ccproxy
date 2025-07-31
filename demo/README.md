# CCProxy Demo

This directory contains demonstrations of CCProxy's intelligent request routing capabilities.

## Overview

CCProxy automatically routes LLM requests to the most appropriate model based on:
- **Token count** → Large contexts to efficient models (Gemini)
- **Model name** → Haiku requests to background processing
- **Thinking tags** → Complex reasoning to advanced models (Opus)
- **Web search tools** → Internet queries to web-enabled models (Perplexity)
- **Default** → Everything else to standard model (Sonnet)

## Demo Files

1. **`demo_config.yaml`** - LiteLLM configuration with model mappings
2. **`demo_requests.py`** - Standalone demo showing routing decisions
3. **`litellm_integration_demo.py`** - Integration pattern demonstration
4. **`start_litellm_proxy.sh`** - Script to start LiteLLM proxy with CCProxy
5. **`test_ccproxy_routing.py`** - Test routing via live proxy

## Quick Start

### 1. Run Standalone Demo (No API Keys Required)

```bash
# From the demo directory
python demo_requests.py
```

This shows how CCProxy routes different types of requests without making actual API calls.

### 2. Run Integration Demo

```bash
python litellm_integration_demo.py
```

This demonstrates the integration pattern and metadata tracking.

### 3. Run with LiteLLM Proxy (Requires API Keys)

First, set your API keys:
```bash
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"      # Optional
export PERPLEXITY_API_KEY="your-key"  # Optional
```

Start the proxy:
```bash
./start_litellm_proxy.sh
```

In another terminal, test routing:
```bash
python test_ccproxy_routing.py
```

## Routing Examples

### Default Routing
```python
# Simple queries go to claude-3-5-sonnet
{"model": "claude-3-5-sonnet-20241022",
 "messages": [{"role": "user", "content": "What is 2+2?"}]}
# Routes to → claude-3-5-sonnet-20241022
```

### Background Processing
```python
# Haiku model requests go to background
{"model": "claude-3-5-haiku-20241022",
 "messages": [{"role": "user", "content": "Format this JSON"}]}
# Routes to → claude-3-5-haiku-20241022 (background)
```

### Complex Reasoning
```python
# <thinking> tags trigger reasoning model
{"model": "claude-3-5-sonnet-20241022",
 "messages": [{"role": "user",
               "content": "<thinking>Need to analyze...</thinking>\nSolve P=NP"}]}
# Routes to → claude-3-5-opus-20241022 (think)
```

### Large Contexts
```python
# >60k tokens go to efficient model
{"model": "claude-3-5-sonnet-20241022",
 "messages": [{"role": "user", "content": "Analyze this book: " + "text"*20000}]}
# Routes to → gemini-2.0-flash-thinking-exp-1219 (token_count)
```

### Web Search
```python
# Web search tool triggers internet-enabled model
{"model": "claude-3-5-sonnet-20241022",
 "messages": [{"role": "user", "content": "Latest AI news?"}],
 "tools": [{"type": "function",
            "function": {"name": "web_search"}}]}
# Routes to → perplexity/llama-3.1-sonar-large-128k-online (web_search)
```

## Configuration

Edit `demo_config.yaml` to:
- Change model mappings
- Adjust token threshold (default: 60,000)
- Enable/disable debug logging
- Add new routing categories

## Priority Order

When multiple rules match, CCProxy uses this priority:
1. **token_count** (highest)
2. **background**
3. **think**
4. **web_search**
5. **default** (lowest)

Example: A request with both `<thinking>` tags AND >60k tokens routes to the token_count model.

## Integration with LiteLLM

To use CCProxy in your LiteLLM proxy:

```python
# In your proxy initialization
from ccproxy.handler import CCProxyHandler

# Register as callback
callbacks = [CCProxyHandler()]
```

Or via command line:
```bash
litellm --config config.yaml --callbacks "ccproxy.handler.CCProxyHandler"
```

## Debugging

Enable debug mode to see routing decisions:
```yaml
ccproxy_settings:
  debug: true
```

Check proxy logs for messages like:
```
[ccproxy] Routed to gemini-2.0-flash-thinking-exp-1219 (label: token_count)
```
