# `ccproxy` - Claude Code Proxy

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/starbased-co/ccproxy)

A LiteLLM-based transformation hook system that intelligently routes Claude Code API requests to different AI providers based on request properties.

> ⚠️ **Note**: This is a newly released project ready for public use and feedback. While core functionality is complete, real-world testing and community input are welcomed. Please [open an issue](https://github.com/starbased-co/ccproxy/issues) to share your experience, report bugs, or suggest improvements.
>
> **Known Issue**: Context preservation between providers is not yet implemented. When routing requests to different models/providers, conversation history may be lost. This is the next major feature being worked on.

## Installation

```bash
# Recommended: Install as a tool
uv tool install git+https://github.com/starbased-co/ccproxy.git
# or
pipx install git+https://github.com/starbased-co/ccproxy.git

# Alternative: Install with pip
pip install git+https://github.com/starbased-co/ccproxy.git
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

   See the examples directory for complete configuration examples.

4. **Start the LiteLLM proxy**:

   ```bash
   cd ~/.ccproxy
   litellm --config config.yaml
   ```

   The proxy will start on `http://localhost:4000` by default.

## Routing Rules

CCProxy includes built-in rules for intelligent request routing:

- **TokenCountRule**: Routes requests with large token counts to high-capacity models
- **MatchModelRule**: Routes based on the requested model name
- **ThinkingRule**: Routes requests containing a "thinking" field
- **MatchToolRule**: Routes based on tool usage (e.g., WebSearch)

You can also create custom rules - see the examples directory for details.

## CLI Commands

CCProxy provides several commands for managing the proxy server:

```bash
# Install configuration files
ccproxy install [--force]

# Start the LiteLLM proxy server
ccproxy start [--detach]

# Stop the background proxy server
ccproxy stop

# View proxy server logs
ccproxy logs [-f] [-n LINES]

# Run any command with proxy environment variables
ccproxy run <command> [args...]

```

## Usage

After installation and setup, you can run any command through the ccproxy:

```bash
# Run Claude Code through the proxy
ccproxy run claude --version
ccproxy run claude -p "Explain quantum computing"

# Run other tools through the proxy
ccproxy run curl http://localhost:4000/health
ccproxy run python my_script.py

```


The `ccproxy run` command sets up the following environment variables:
- `OPENAI_API_BASE` / `OPENAI_BASE_URL` - For OpenAI SDK compatibility
- `ANTHROPIC_BASE_URL` - For Anthropic SDK compatibility
- `LITELLM_PROXY_BASE_URL` / `LITELLM_PROXY_API_BASE` - For LiteLLM proxy
- `HTTP_PROXY` / `HTTPS_PROXY` - Standard proxy variables

## How It Works

CCProxy automatically routes requests based on these rules (in priority order):

1. **Long context** (>60k tokens, configurable) → `token_count` model
2. **Background requests** (model is `claude-3-5-haiku`) → `background` model
3. **Thinking requests** (request has `think` field) → `think` model
4. **Web search** (tools contain `web_search`) → `web_search` model
5. **Default** → `default` model

## Configuration

CCProxy uses a `ccproxy.yaml` file to configure routing rules:

```yaml
ccproxy:
  debug: true # Enable debug logging to see routing decisions
  rules:
    - label: token_count
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 60000  # Route to token_count if tokens > 60k
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

Set `debug: true` in the `ccproxy` section of your `ccproxy.yaml` file to see detailed routing decisions in the logs.

## Contributing

I welcome contributions! Please see the [Contributing Guide](CONTRIBUTING.md) for details on:

- Reporting issues and asking questions
- Setting up development environment
- Code style and testing requirements
- Submitting pull requests

Since this is a new project, I especially appreciate:
- Bug reports and feedback
- Documentation improvements
- Test coverage additions
- Feature suggestions

## Acknowledgments

Inspired in part by [claude-code-router](https://github.com/musistudio/claude-code-router).
