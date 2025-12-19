# ccproxy Troubleshooting Guide

This guide covers common issues and solutions when using ccproxy.

---

## Table of Contents

1. [Startup Issues](#startup-issues)
2. [OAuth & Authentication](#oauth--authentication)
3. [Rule Configuration](#rule-configuration)
4. [Hook Chain Issues](#hook-chain-issues)
5. [Model Routing](#model-routing)
6. [Performance Issues](#performance-issues)

---

## Startup Issues

### Proxy Fails to Start

**Symptom:** `ccproxy start` exits immediately with an error.

**Common Causes:**

1. **Port already in use**
   ```bash
   # Check what's using port 4000
   lsof -i :4000
   
   # Kill the process or use a different port
   ccproxy start --port 4001
   ```

2. **Invalid YAML configuration**
   ```bash
   # Validate your config file
   python -c "import yaml; yaml.safe_load(open('ccproxy.yaml'))"
   ```

3. **Missing dependencies**
   ```bash
   # Reinstall ccproxy with all dependencies
   pip install ccproxy[all]
   ```

### Configuration Not Found

**Symptom:** "Could not find ccproxy.yaml" or using default config unexpectedly.

**Solution:** Check configuration discovery order:

1. `$CCPROXY_CONFIG_DIR/ccproxy.yaml` (environment variable)
2. `./ccproxy.yaml` (current directory)
3. `~/.ccproxy/ccproxy.yaml` (home directory)

```bash
# Set config directory explicitly
export CCPROXY_CONFIG_DIR=/path/to/config

# Or specify during install
ccproxy install --config-dir /path/to/config
```

---

## OAuth & Authentication

### OAuth Token Loading Fails

**Symptom:** Warning about OAuth tokens not loading at startup.

**Cause:** The shell command in `oat_sources` is failing.

**Debug Steps:**

1. **Test the command manually:**
   ```bash
   # Run your OAuth command directly
   jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json
   ```

2. **Check file permissions:**
   ```bash
   ls -la ~/.claude/.credentials.json
   ```

3. **Verify JSON structure:**
   ```bash
   cat ~/.claude/.credentials.json | jq .
   ```

**Solution:** Fix the command or file path in `ccproxy.yaml`:

```yaml
ccproxy:
  oat_sources:
    anthropic: "jq -r '.claudeAiOauth.accessToken' ~/.claude/.credentials.json"
```

### Token Expires During Runtime

**Symptom:** Requests fail with authentication errors after running for a while.

**Solution:** Enable automatic token refresh:

```yaml
ccproxy:
  oat_sources:
    anthropic: "your-oauth-command"
  oauth_refresh_interval: 3600  # Refresh every hour (default)
```

Set to `0` to disable automatic refresh.

### Empty OAuth Command Error

**Symptom:** "Empty OAuth command for provider 'X'" validation warning.

**Solution:** Remove empty entries or provide valid commands:

```yaml
# Wrong
oat_sources:
  anthropic: ""  # Empty command

# Correct
oat_sources:
  anthropic: "jq -r '.token' ~/.tokens.json"
```

---

## Rule Configuration

### Custom Rule Loading Errors

**Symptom:** "Could not import rule class" or similar errors.

**Debug Steps:**

1. **Check the import path:**
   ```python
   # Test in Python
   from ccproxy.rules import TokenCountRule
   ```

2. **Verify rule class exists:**
   ```bash
   grep -r "class TokenCountRule" src/
   ```

**Common Mistakes:**

```yaml
# Wrong - missing module path
rules:
  - name: my_rule
    rule: TokenCountRule  # Missing full path

# Correct
rules:
  - name: my_rule
    rule: ccproxy.rules.TokenCountRule
    params:
      - threshold: 50000
```

### Duplicate Rule Names

**Symptom:** "Duplicate rule names found" validation warning.

**Solution:** Each rule must have a unique name:

```yaml
# Wrong
rules:
  - name: token_count
    rule: ccproxy.rules.TokenCountRule
  - name: token_count  # Duplicate!
    rule: ccproxy.rules.ThinkingRule

# Correct
rules:
  - name: token_count
    rule: ccproxy.rules.TokenCountRule
  - name: thinking
    rule: ccproxy.rules.ThinkingRule
```

### Rule Not Matching

**Symptom:** Requests not being routed to expected model.

**Debug Steps:**

1. **Enable debug logging:**
   ```yaml
   ccproxy:
     debug: true
   ```

2. **Check rule order:** Rules are evaluated in order, first match wins.

3. **Verify model exists in LiteLLM config:**
   ```yaml
   # config.yaml
   model_list:
     - model_name: token_count  # Must match rule name
       litellm_params:
         model: gemini-2.0-flash
   ```

---

## Hook Chain Issues

### Hook Fails Silently

**Symptom:** Expected behavior not happening, no errors visible.

**Solution:** Enable debug mode to see hook execution:

```yaml
ccproxy:
  debug: true
  hooks:
    - ccproxy.hooks.rule_evaluator
    - ccproxy.hooks.model_router
```

Check logs for:
```
Hook rule_evaluator failed with error: ...
```

### Invalid Hook Path

**Symptom:** "Invalid hook path" validation warning.

**Solution:** Use full module path with dots:

```yaml
# Wrong
hooks:
  - rule_evaluator  # Missing module path

# Correct
hooks:
  - ccproxy.hooks.rule_evaluator
```

### Hook Order Matters

Hooks are executed in the order specified. Common order:

```yaml
hooks:
  - ccproxy.hooks.rule_evaluator    # 1. Evaluate rules
  - ccproxy.hooks.model_router      # 2. Route to model
  - ccproxy.hooks.forward_oauth     # 3. Add OAuth token
```

---

## Model Routing

### Model Not Found

**Symptom:** "Model 'X' not found" errors or fallback to default.

**Causes:**

1. **Model name mismatch:**
   ```yaml
   # Rule name must match model_name in LiteLLM config
   rules:
     - name: gemini  # This name...
   
   # config.yaml
   model_list:
     - model_name: gemini  # ...must match this
   ```

2. **LiteLLM config not loaded:** Check that `config.yaml` is in the right location.

### Passthrough Not Working

**Symptom:** Requests not being passed through to original model.

**Solution:** Ensure `default_model_passthrough` is enabled:

```yaml
ccproxy:
  default_model_passthrough: true  # Default
```

### Model Reload Issues

**Symptom:** New models not appearing after config change.

**Solution:** Restart the proxy or wait for automatic reload (5 second cooldown):

```bash
ccproxy restart
```

---

## Performance Issues

### High Memory Usage

**Symptom:** Memory growing over time.

**Possible Causes:**

1. **Request metadata accumulation:** Fixed with LRU cleanup (max 10,000 entries)
2. **Large token counting cache:** Each rule has its own tokenizer cache

**Solution:** Monitor with health check:

```bash
ccproxy status --health
```

### Slow Rule Evaluation

**Symptom:** High latency on requests.

**Solutions:**

1. **Reduce token counting:** Use simpler rules first
2. **Cache tokenizers:** TokenCountRule caches tokenizer per encoding
3. **Order rules efficiently:** Put most common matches first

### Model Reload Thrashing

**Symptom:** High CPU usage, frequent "reloading models" logs.

**Cause:** Models being reloaded on every cache miss.

**Solution:** This is now fixed with 5-second cooldown. Update to latest version.

---

## Getting Help

### Enable Debug Logging

```yaml
ccproxy:
  debug: true
```

### Check Status

```bash
# Basic status
ccproxy status

# With health metrics
ccproxy status --health

# JSON output for scripts
ccproxy status --json
```

### View Logs

```bash
# View recent logs
ccproxy logs

# Follow logs in real-time
ccproxy logs -f

# Last 50 lines
ccproxy logs -n 50
```

### Validate Configuration

```bash
# Start in debug mode
ccproxy start --debug

# Check for validation warnings in startup output
```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid handler format" | Handler path missing colon | Use `module.path:ClassName` |
| "Empty OAuth command" | OAuth source is empty string | Provide valid command or remove entry |
| "Duplicate rule names" | Two rules have same name | Use unique names |
| "Could not find templates" | Installation issue | Reinstall ccproxy |
| "Port already in use" | Another process on port | Kill process or use different port |
