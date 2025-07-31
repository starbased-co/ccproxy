# CCProxy Examples

This directory contains example custom rules and configurations to help you extend ccproxy.

## Files

### custom_rule.py
A comprehensive example showing four different rule patterns:

1. **PriorityUserRule** - Routes based on user identity and message keywords
2. **TimeBasedRule** - Routes based on time of day
3. **ContentLengthRule** - Routes based on total message length
4. **ModelCapabilityRule** - Routes based on required model features

### example_ccproxy.yaml
Complete configuration example showing how to use both built-in and custom rules.

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
      model: gpt-4
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
    "model": "claude-3-5-sonnet",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "metadata": {
        "user_email": "user@example.com",
        # Other metadata
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
