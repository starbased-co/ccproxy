# CCProxy Usage Guide

## Table of Contents
1. [What is CCProxy?](#what-is-ccproxy)
2. [Installation](#installation)
3. [Claude CLI Integration](#claude-cli-integration)
4. [Running the Demo](#running-the-demo)
5. [Configuration](#configuration)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

## What is CCProxy?

CCProxy is a LiteLLM transformation hook that intelligently routes API requests to different models based on request characteristics:

- **Large contexts** (>60k tokens) → Efficient models like Gemini
- **Background tasks** (haiku requests) → Cost-effective models
- **Complex reasoning** (`<thinking>` tags) → Advanced models like Opus
- **Web searches** (web_search tool) → Internet-enabled models
- **Default requests** → Standard model (Sonnet)

## Installation

```bash
# Install with uv (recommended)
uv add ccproxy

# Or install from source
git clone https://github.com/yourusername/ccproxy.git
cd ccproxy
uv sync
```

## Claude CLI Integration

CCProxy provides a transparent wrapper for the Claude CLI that automatically routes requests through a managed LiteLLM proxy with intelligent routing.

### Setup

After installing ccproxy, the `claude` command becomes available:

```bash
# Use claude as normal - CCProxy handles the routing transparently
claude "What is the capital of France?"

# All Claude CLI options work as expected
claude --model claude-3-opus-20240229 "Explain quantum computing"
claude --stream "Write a haiku about programming"
```

### How It Works

1. **Automatic Proxy Management**: The wrapper automatically starts a LiteLLM proxy in the background
2. **Process Coordination**: Multiple Claude instances share the same proxy instance
3. **Transparent Routing**: All requests are routed through CCProxy for intelligent model selection
4. **Lifecycle Management**: The proxy shuts down automatically when the last Claude instance exits

### Environment Variables

Control the Claude wrapper behavior with these environment variables:

```bash
# Use a specific proxy port
export CC_PROXY_PORT=9000

# Use a custom config file
export CC_PROXY_CONFIG=/path/to/config.yaml

# View logs
tail -f ~/.ccproxy/proxy.log
```

### Files and Directories

CCProxy creates the following files in your home directory:

- `~/.ccproxy/` - Main directory for CCProxy data
- `~/.ccproxy/claude_proxy.json` - Proxy state (PID, port, reference count)
- `~/.ccproxy/proxy.log` - Proxy logs (rotated at 10MB)
- `~/.ccproxy/claude.lock` - Lock file for process coordination
- `~/.ccproxy/config.yaml` - Default config location (optional)

## Running the Demo

### Option 1: Standalone Demo (No API Keys)

```bash
# From project root
uv run python demo/demo_requests.py
```

### Option 2: With LiteLLM Proxy

1. The integration is configured in `demo/demo_config.yaml`:

```yaml
litellm_settings:
  callbacks: custom_callbacks.proxy_handler_instance
```

2. Start LiteLLM:

```bash
cd demo
export LITELLM_CONFIG_PATH="demo_config.yaml"
uv run litellm --config demo_config.yaml --port 8888
```

3. Test with curl:

```bash
curl -X POST http://localhost:8888/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "<thinking>Complex problem</thinking>\nSolve P=NP"}]
  }'
```

### Option 3: Test Claude Wrapper

```bash
# Test the wrapper functionality
uv run python demo/test_claude_wrapper.py
```

## Configuration

### Model Routing Configuration

Define how requests are routed based on their characteristics:

```yaml
# Model routing based on request type
router_config:
  models:
    default: gpt-3.5-turbo
    large_context: claude-3-opus
    background: claude-3-haiku
    think: o1-preview
    web_search: perplexity-online

  context_threshold: 60000  # Tokens for large_context routing
```

### Classification Rules

CCProxy classifies requests using these rules (in priority order):

1. **Large Context**: Token count > threshold → `large_context` model
2. **Background**: Model is claude-3-5-haiku → `background` model
3. **Thinking**: Request has thinking field → `think` model
4. **Web Search**: Tools include web_search → `web_search` model
5. **Default**: All other requests → `default` model

## Advanced Usage

### Programmatic Usage

Use CCProxy in your Python code:

```python
import litellm
from ccproxy.handler import CCProxyHandler

# Initialize handler
handler = CCProxyHandler()

# Use with LiteLLM
litellm.callbacks = [handler]

# Make requests
response = litellm.completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Custom Classification

Extend classification logic by modifying the router:

```python
# custom_router.py
from ccproxy.handler import CCProxyHandler

class CustomCCProxyHandler(CCProxyHandler):
    def classify_request(self, data: dict) -> str:
        # Add custom classification logic
        if "code" in str(data.get("messages", [])):
            return "code_optimized"
        return super().classify_request(data)
```

## Troubleshooting

### Common Issues

1. **Claude CLI not found**
   ```bash
   # Install Anthropic CLI
   uv add anthropic
   ```

2. **Port already in use**
   ```bash
   # Check for running proxy
   cat ~/.ccproxy/claude_proxy.json

   # Kill stuck proxy
   kill $(cat ~/.ccproxy/claude_proxy.json | jq -r .pid)
   rm ~/.ccproxy/claude_proxy.json
   ```

3. **Config not loaded**
   ```bash
   # Verify config path
   export CC_PROXY_CONFIG=/absolute/path/to/config.yaml

   # Check logs
   tail -f ~/.ccproxy/proxy.log
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```yaml
# config.yaml
ccproxy_settings:
  debug: true

litellm_settings:
  set_verbose: true
```

### Getting Help

- Check logs: `~/.ccproxy/proxy.log`
- Run with debug: `CC_PROXY_DEBUG=1 claude --help`
- Report issues: [GitHub Issues](https://github.com/yourusername/ccproxy/issues)

## Key Files

- `demo/demo_config.yaml` - LiteLLM configuration with model mappings
- `demo/custom_callbacks.py` - Callback loader for LiteLLM
- `demo/demo_requests.py` - Standalone routing demonstration
- `src/ccproxy/handler.py` - Main CCProxy implementation
- `src/ccproxy/claude_wrapper.py` - Claude CLI wrapper implementation

## How It Works

1. LiteLLM loads the callback from the config file
2. CCProxy intercepts requests via `async_pre_call_hook`
3. Request is classified based on content/properties
4. Model is switched to the optimal choice
5. Request continues through LiteLLM normally

## Benefits

- **Cost Optimization**: Routes simple tasks to cheaper models
- **Performance**: Large contexts go to efficient models
- **Capability Matching**: Complex reasoning gets advanced models
- **Transparent**: No client code changes needed
- **Configurable**: Easy to adjust routing rules
- **Claude Integration**: Seamless integration with Claude CLI
