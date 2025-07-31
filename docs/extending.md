# Extending CCProxy

CCProxy provides a flexible rule-based classification system that can be easily extended without modifying core code.

## Extension Points

### 1. Custom Classification Rules

The primary way to extend CCProxy is by creating custom classification rules. All rules inherit from the `ClassificationRule` abstract base class.

```python
from ccproxy.classifier import ClassificationRule, RoutingLabel
from ccproxy.config import CCProxyConfig

class CustomRule(ClassificationRule):
    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        # Your logic here
        if some_condition:
            return RoutingLabel.BACKGROUND
        return None
```

### 2. Adding Rules to the Classifier

You can add custom rules to the classifier in several ways:

#### Add to existing rules
```python
from ccproxy.classifier import RequestClassifier

classifier = RequestClassifier()
classifier.add_rule(CustomRule())
```

#### Replace all rules
```python
classifier.clear_rules()
classifier.add_rule(CustomRule1())
classifier.add_rule(CustomRule2())
```

#### Reset to defaults
```python
classifier.reset_rules()  # Restores standard rules
```

## Example: Custom Header-Based Routing

Here's a complete example of a custom rule that routes based on HTTP headers:

```python
class PriorityHeaderRule(ClassificationRule):
    """Route requests based on X-Priority header."""

    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        headers = request.get("headers", {})
        priority = headers.get("X-Priority", "").lower()

        if priority == "low":
            return RoutingLabel.BACKGROUND
        elif priority == "urgent":
            return RoutingLabel.THINK

        return None

# Use the custom rule
classifier = RequestClassifier()
classifier.add_rule(PriorityHeaderRule())
```

## Example: Custom Model Name Routing

You can create additional model name rules for specific models:

```python
from ccproxy.rules import ModelNameRule

# Route GPT-4o-mini requests to background
classifier = RequestClassifier()
classifier.add_rule(ModelNameRule("gpt-4o-mini", RoutingLabel.BACKGROUND))

# Route a specific custom model to think label
classifier.add_rule(ModelNameRule("my-reasoning-model", RoutingLabel.THINK))
```

## Example: Environment-Based Routing

Route requests differently based on deployment environment:

```python
class EnvironmentRule(ClassificationRule):
    """Route based on deployment environment."""

    def __init__(self, production_model: RoutingLabel = RoutingLabel.DEFAULT):
        self.production_model = production_model

    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        metadata = request.get("metadata", {})
        env = metadata.get("environment", "")

        if env == "production":
            return self.production_model
        elif env == "staging":
            return RoutingLabel.BACKGROUND

        return None
```

## Rule Evaluation Order

Rules are evaluated in the order they are added. The first rule that returns a non-None value determines the routing label:

```python
classifier = RequestClassifier()
# Default rules are added in this order:
# 1. TokenCountRule (token_count)
# 2. ModelNameRule("claude-3-5-haiku", RoutingLabel.BACKGROUND)
# 3. ThinkingRule (think)
# 4. WebSearchRule (web_search)

# Your custom rules are added after defaults
classifier.add_rule(CustomRule())  # Evaluated after defaults
```

To prioritize custom rules, clear defaults first:

```python
classifier.clear_rules()
classifier.add_rule(CustomRule())  # Now evaluated first
classifier.add_rule(TokenCountRule())  # Add back specific defaults
```

## Best Practices

1. **Keep rules focused**: Each rule should check one specific condition
2. **Return None for no match**: This allows other rules to be evaluated
3. **Use configuration**: Access `config` parameter for thresholds and settings
4. **Handle errors gracefully**: Don't let exceptions escape from `evaluate()`
5. **Document behavior**: Clearly document what triggers your rule

## Testing Custom Rules

Always test custom rules thoroughly:

```python
def test_custom_rule():
    rule = CustomRule()
    config = CCProxyConfig()

    # Test matching case
    request = {"your": "data"}
    assert rule.evaluate(request, config) == RoutingLabel.EXPECTED

    # Test non-matching case
    request = {"other": "data"}
    assert rule.evaluate(request, config) is None
```

## Integration with LiteLLM

When CCProxy routes a request to a different model, it works seamlessly with LiteLLM's proxy:

1. Your custom rule returns a `RoutingLabel`
2. CCProxy maps the label to a model using the LiteLLM config
3. LiteLLM routes the request to the appropriate provider

No additional integration work is needed - just return the appropriate `RoutingLabel` from your rule.
