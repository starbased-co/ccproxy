# ccproxy Configuration Examples

This document provides configuration examples for various use cases.

---

## Table of Contents

1. [Basic Setup](#basic-setup)
2. [Multi-Provider Setup](#multi-provider-setup)
3. [Token-Based Routing](#token-based-routing)
4. [Thinking Model Routing](#thinking-model-routing)
5. [OAuth Configuration](#oauth-configuration)
6. [Advanced Hook Configuration](#advanced-hook-configuration)
7. [Production Configuration](#production-configuration)

---

## Basic Setup

### Minimal Configuration

The simplest working configuration:

```yaml
# ccproxy.yaml
ccproxy:
  handler: ccproxy.handler:CCProxyHandler
  hooks:
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
  default_model_passthrough: true
```

```yaml
# config.yaml
litellm_settings:
  callbacks:
    - ccproxy.handler:CCProxyHandler

model_list:
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
```

---

## Multi-Provider Setup

### Using Anthropic, Google, and OpenAI

```yaml
# ccproxy.yaml
ccproxy:
  handler: ccproxy.handler:CCProxyHandler
  hooks:
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
  default_model_passthrough: true

  rules:
    # Route expensive requests to cheaper models
    - name: high_token
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 50000
    
    # Route thinking requests to Gemini
    - name: thinking
      rule: ccproxy.rules.ThinkingRule
```

```yaml
# config.yaml
litellm_settings:
  callbacks:
    - ccproxy.handler:CCProxyHandler

model_list:
  # Default model
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # High token count → Gemini Flash (cheaper)
  - model_name: high_token
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY

  # Thinking requests → Gemini 2.0 Flash Thinking
  - model_name: thinking
    litellm_params:
      model: gemini/gemini-2.0-flash-thinking-exp
      api_key: os.environ/GEMINI_API_KEY

  # OpenAI for specific use cases
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY
```

---

## Token-Based Routing

### Route by Token Count

```yaml
# ccproxy.yaml
ccproxy:
  rules:
    # Small requests → Claude Haiku (fast, cheap)
    - name: small_request
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 5000
        - max_threshold: 0  # No upper limit for this check
    
    # Medium requests → Claude Sonnet (balanced)
    - name: medium_request
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 30000
    
    # Large requests → Gemini Flash (high context)
    - name: large_request
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 100000
```

```yaml
# config.yaml
model_list:
  - model_name: small_request
    litellm_params:
      model: anthropic/claude-3-haiku-20240307
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: medium_request
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: large_request
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
```

---

## Thinking Model Routing

### Route Based on Thinking Parameter

```yaml
# ccproxy.yaml
ccproxy:
  rules:
    # Extended thinking → specialized model
    - name: deep_thinking
      rule: ccproxy.rules.ThinkingRule
      params:
        - thinking_budget_min: 10000  # Min thinking tokens
    
    # Regular thinking → standard thinking model
    - name: thinking
      rule: ccproxy.rules.ThinkingRule
```

```yaml
# config.yaml
model_list:
  # Deep thinking with high budget
  - model_name: deep_thinking
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      thinking:
        type: enabled
        budget_tokens: 50000

  # Standard thinking
  - model_name: thinking
    litellm_params:
      model: gemini/gemini-2.0-flash-thinking-exp
      api_key: os.environ/GEMINI_API_KEY
```

---

## OAuth Configuration

### Claude Code OAuth Forwarding

```yaml
# ccproxy.yaml
ccproxy:
  hooks:
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
    - ccproxy.hooks.forward_oauth  # Add this hook
  
  oat_sources:
    anthropic: "jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json"
  
  # Refresh tokens every hour
  oauth_refresh_interval: 3600
```

### Multiple OAuth Providers

```yaml
# ccproxy.yaml
ccproxy:
  oat_sources:
    # Anthropic - from Claude credentials file
    anthropic: "jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json"
    
    # Google - from gcloud
    google: "gcloud auth print-access-token"
    
    # GitHub - from environment
    github: "echo $GITHUB_TOKEN"

  oauth_refresh_interval: 1800  # Refresh every 30 minutes
```

### OAuth with Custom User-Agent

```yaml
# ccproxy.yaml
ccproxy:
  oat_sources:
    anthropic:
      command: "jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json"
      user_agent: "MyApp/1.0 (ccproxy)"
    
    gemini:
      command: "gcloud auth print-access-token"
      user_agent: "MyApp/1.0 (ccproxy)"
```

---

## Advanced Hook Configuration

### Hook with Parameters

```yaml
# ccproxy.yaml
ccproxy:
  hooks:
    # Simple hook (string format)
    - ccproxy.hooks.rule_evaluator
    
    # Hook with parameters (dict format)
    - hook: ccproxy.hooks.model_router
      params:
        fallback_model: claude-3-5-sonnet
    
    # Custom hook from your module
    - hook: my_hooks.custom_logger
      params:
        log_level: debug
        include_tokens: true
```

### Custom Hook Module

Create `~/.ccproxy/ccproxy.py`:

```python
# Custom hooks
import logging

logger = logging.getLogger(__name__)

def log_all_requests(data: dict, user_api_key_dict: dict, **kwargs) -> dict:
    """Log every request for debugging."""
    model = data.get('model', 'unknown')
    messages = data.get('messages', [])
    
    logger.info(f"Request to {model} with {len(messages)} messages")
    
    return data

def add_custom_metadata(data: dict, user_api_key_dict: dict, **kwargs) -> dict:
    """Add custom metadata to all requests."""
    if 'metadata' not in data:
        data['metadata'] = {}
    
    data['metadata']['processed_by'] = 'ccproxy'
    data['metadata']['version'] = '1.0'
    
    return data
```

Then use in config:

```yaml
# ccproxy.yaml
ccproxy:
  hooks:
    - ccproxy.py.log_all_requests
    - ccproxy.py.add_custom_metadata
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
```

---

## Production Configuration

### Full Production Setup

```yaml
# ccproxy.yaml
ccproxy:
  # Core settings
  debug: false
  metrics_enabled: true
  default_model_passthrough: true
  
  # Handler
  handler: ccproxy.handler:CCProxyHandler
  
  # Hook chain
  hooks:
    - ccproxy.hooks.capture_headers
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
    - ccproxy.hooks.forward_oauth
  
  # OAuth with refresh
  oat_sources:
    anthropic: "jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json"
  oauth_refresh_interval: 3600
  
  # Routing rules
  rules:
    # Route high-token requests to Gemini
    - name: high_token
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 50000
    
    # Route thinking requests to thinking model
    - name: thinking
      rule: ccproxy.rules.ThinkingRule
```

```yaml
# config.yaml
litellm_settings:
  callbacks:
    - ccproxy.handler:CCProxyHandler
  
  # Logging
  success_callback: []
  failure_callback: []

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  background_health_checks: true
  health_check_interval: 300

model_list:
  # Primary model
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
      max_tokens: 8192
      timeout: 600
  
  # High token route
  - model_name: high_token
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
      timeout: 600
  
  # Thinking route
  - model_name: thinking
    litellm_params:
      model: gemini/gemini-2.0-flash-thinking-exp
      api_key: os.environ/GEMINI_API_KEY
      timeout: 900
```

### Environment Variables (.env)

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# LiteLLM settings
LITELLM_MASTER_KEY=sk-master-...
HOST=127.0.0.1
PORT=4000

# ccproxy config directory
CCPROXY_CONFIG_DIR=/etc/ccproxy
```

---

## CLI Usage Examples

### Start the Proxy

```bash
# Default start
ccproxy start

# Detached mode (background)
ccproxy start -d

# With custom port
ccproxy start -- --port 8080
```

### Check Status

```bash
# Basic status
ccproxy status

# With health metrics
ccproxy status --health

# JSON output (for scripts)
ccproxy status --json
```

### Shell Integration

```bash
# Generate and install for current shell
ccproxy shell-integration --install

# Generate for specific shell
ccproxy shell-integration --shell zsh

# Just print the script
ccproxy shell-integration
```

### View Logs

```bash
# Recent logs
ccproxy logs

# Follow in real-time
ccproxy logs -f

# Last 50 lines
ccproxy logs -n 50
```

### Restart

```bash
# Restart the proxy
ccproxy restart

# Restart in detached mode
ccproxy restart -d
```

---

## Validation Rules

The configuration is validated on startup with these checks:

| Check | Error Message | Fix |
|-------|---------------|-----|
| Duplicate rule names | "Duplicate rule names found" | Use unique names |
| Invalid handler format | "Invalid handler format" | Use `module:ClassName` |
| Invalid hook path | "Invalid hook path" | Use `module.path.function` |
| Empty OAuth command | "Empty OAuth command" | Provide command or remove |

Check validation warnings:

```bash
ccproxy start --debug
# Look for "Configuration issue:" warnings
```
