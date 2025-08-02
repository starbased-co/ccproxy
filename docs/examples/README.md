# CCProxy Examples

This directory contains example custom rules and configurations to help you extend ccproxy.

## Quick Start

1. **Install CCProxy**:
   ```bash
   uv tool install git+https://github.com/starbased-co/ccproxy.git
   # or
   pipx install git+https://github.com/starbased-co/ccproxy.git
   ```

2. **Set up configuration**:
   ```bash
   ccproxy install
   ```

3. **Copy examples** (optional):
   ```bash
   cp examples/custom_rule.py ~/.ccproxy/
   ```

## Files

### custom_rule.py
A comprehensive example showing four different custom rule patterns:

1. **PriorityUserRule** - Routes based on user identity and message keywords
2. **TimeBasedRule** - Routes based on time of day
3. **ContentLengthRule** - Routes based on total message length
4. **ModelCapabilityRule** - Routes based on required model features

### ccproxy.yaml
Complete configuration example showing built-in rules:
- **TokenCountRule** - Routes large context requests (>60k tokens)
- **MatchModelRule** - Routes specific model requests (e.g., claude-3-5-haiku)
- **ThinkingRule** - Routes requests with thinking fields
- **MatchToolRule** - Routes based on tool usage (e.g., WebSearch)

### config.yaml
LiteLLM configuration example with model deployments matching the rule labels.

### ccproxy.py
Custom callbacks file that creates the CCProxyHandler instance for LiteLLM.

## Creating Your Own Rules

### Step 1: Create Your Rule Class

Copy `custom_rule.py` to your project and modify it:

```python
from typing import Any
from ccproxy.rules import ClassificationRule
from ccproxy.config import CCProxyConfig

class MyCustomRule(ClassificationRule):
    def __init__(self, my_param: str) -> None:
        self.my_param = my_param

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        # Your logic here
        return True  # Return True to use this rule's label
```

### Step 2: Configure in ccproxy.yaml

Add your rule to the ccproxy configuration:

```yaml
ccproxy:
  rules:
    - label: my_model_label  # Must match a model_name in config.yaml
      rule: myproject.MyCustomRule  # Python import path
      params:
        - my_param: "value"
```

### Step 3: Ensure Model Configuration

Make sure you have a corresponding model in your LiteLLM `config.yaml`:

```yaml
model_list:
  - model_name: my_model_label  # Matches the label above
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: ${ANTHROPIC_API_KEY}
```

## Rule Guidelines

### Constructor Parameters

Rules can accept parameters in several formats:

```yaml
# Single positional argument
params:
  - "single_value"

# Multiple positional arguments
params:
  - "first"
  - "second"

# Keyword arguments
params:
  - param1: "value1"
    param2: "value2"

# Mixed (multiple dicts merged)
params:
  - setting1: true
  - setting2: false
```

### Request Structure

The `request` parameter contains the LiteLLM request data:

```python
{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "metadata": {
        "user_email": "user@example.com",
        # Other metadata from LiteLLM proxy
    },
    "tools": [...],  # If using function calling
    "stream": False,
    # Other LiteLLM parameters
}
```

### Best Practices

1. **Type Safety**: Always use proper type hints
2. **Error Handling**: Return `False` on errors rather than raising exceptions
3. **Performance**: Keep evaluation logic fast as it runs on every request
4. **Documentation**: Document your rule's purpose and parameters
5. **Testing**: Include test code to verify your rule works correctly

## Testing Your Rules

Run the example to see how rules work:

```bash
python examples/custom_rule.py
```

Or test in your own code:

```python
from myproject import MyCustomRule

rule = MyCustomRule("parameter")
test_request = {
    "messages": [{"role": "user", "content": "Test"}],
    # ... other request data
}

result = rule.evaluate(test_request, config)
print(f"Rule matched: {result}")
```

## Advanced Patterns

### Accessing LiteLLM Runtime

If you need to access the LiteLLM proxy runtime:

```python
from litellm.proxy import proxy_server

def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
    if proxy_server and proxy_server.llm_router:
        model_list = proxy_server.llm_router.model_list
        # Use model configuration data
    return False
```

### Stateful Rules

For rules that need to maintain state:

```python
class RateLimitRule(ClassificationRule):
    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self._request_times: list[float] = []

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        import time
        current_time = time.time()
        # Clean old entries
        self._request_times = [
            t for t in self._request_times
            if current_time - t < 60
        ]
        # Check rate limit
        if len(self._request_times) >= self.limit:
            return True  # Route to rate-limited model
        self._request_times.append(current_time)
        return False
```

## Need Help?

- See the main project documentation for more details
- Check existing rules in `src/ccproxy/rules.py` for more examples
- Ensure your rule follows the same patterns as the built-in rules
