# `ccproxy`

A LiteLLM-based transformation hook system that routes Claude Code API requests to different providers based on request properties.

## Installation

```bash
uv tool install ccproxy
# or
pipx install ccproxy
# or
pip install ccproxy
```

## Quick Setup

Run the automated setup:

```bash
ccproxy install
# or with Python module:
python -m ccproxy install
```

This will create all necessary configuration files in `~/.ccproxy/`.

To overwrite existing files without prompting:

```bash
ccproxy install --force
```

## Manual Setup

If you prefer to set up manually:

1. **Create the CCProxy configuration directory**:

   ```bash
   mkdir -p ~/.ccproxy
   cd ~/.ccproxy
   ```

2. **Create the callback file** (`~/.ccproxy/custom_callbacks.py`):

   ```python
   from ccproxy.handler import CCProxyHandler

   # Create the instance that LiteLLM will use
   proxy_handler_instance = CCProxyHandler()
   ```

3. **Create your LiteLLM config** (`~/.ccproxy/config.yaml`):

   ```yaml
   model_list:
     # Default model for regular use
     - model_name: default
       litellm_params:
         model: anthropic/claude-sonnet-4-20250514
         api_key: ${ANTHROPIC_API_KEY}

     # Background model for claude-3-5-haiku requests
     - model_name: background
       litellm_params:
         model: anthropic/claude-3-5-haiku-20241022
         api_key: ${ANTHROPIC_API_KEY}

     # Add other models as needed...

   litellm_settings:
     callbacks: custom_callbacks.proxy_handler_instance
   ```

   See [config.yaml.example](./config.yaml.example) for a complete example with all routing models.

4. **Start the LiteLLM proxy**:

   ```bash
   cd ~/.ccproxy
   litellm --config config.yaml
   ```

   The proxy will start on `http://localhost:4000` by default.

## Environment Variables

Set your API keys before starting the proxy:

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export GOOGLE_API_KEY="your-google-key"  # For Gemini models
# Add other API keys as needed

cd ~/.ccproxy
litellm --config config.yaml
```

## Routing Rules

## Usage

After installation and setup, use Claude with automatic routing:

```bash
ccproxy claude --version
ccproxy claude -p "Explain quantum computing"

# Or set an alias for convenience:
alias claude='ccproxy claude'
claude -p "Hello world"
```

The proxy will start automatically when you use the `ccproxy claude` command and route your requests based on the configured rules.

## How It Works

CCProxy automatically routes requests based on these rules (in priority order):

1. **Long context** (>60k tokens, configurable) → `token_count` model
2. **Background requests** (model is `claude-3-5-haiku`) → `background` model
3. **Thinking requests** (request has `think` field) → `think` model
4. **Web search** (tools contain `web_search`) → `web_search` model
5. **Default** → `default` model

## Configuration

The `token_count_threshold` in `ccproxy_settings` controls when requests are routed to the large context model:

```yaml
ccproxy_settings:
  token_count_threshold: 60000 # Route to token_count if tokens > 60k
  debug: true # Enable debug logging to see routing decisions
```

## Troubleshooting

### "Could not import proxy_handler_instance from ccproxy"

Make sure you:

1. Created the `custom_callbacks.py` file in your config directory
2. Are running `litellm` from the same directory as your config files
3. Have installed ccproxy: `pip install ccproxy`

### API Key Errors

Ensure your API keys are set as environment variables before starting LiteLLM.

### Debug Logging

Set `debug: true` in `ccproxy_settings` to see detailed routing decisions in the logs.
