# CCProxy Demo Summary

## What is CCProxy?

CCProxy is a LiteLLM transformation hook that intelligently routes API requests to different models based on request characteristics:

- **Large contexts** (>60k tokens) → Efficient models like Gemini
- **Background tasks** (haiku requests) → Cost-effective models
- **Complex reasoning** (`<thinking>` tags) → Advanced models like Opus
- **Web searches** (web_search tool) → Internet-enabled models
- **Default requests** → Standard model (Sonnet)

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

## Key Files

- `demo/demo_config.yaml` - LiteLLM configuration with model mappings
- `demo/custom_callbacks.py` - Callback loader for LiteLLM
- `demo/demo_requests.py` - Standalone routing demonstration
- `src/ccproxy/handler.py` - Main CCProxy implementation

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
