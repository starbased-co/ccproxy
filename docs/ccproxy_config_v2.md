# `ccproxy.yaml` Config File Changes (Completed)

- Moved `ccproxy` settings out of the LiteLLM proxy `config.yaml` into a new `ccproxy.yaml`. See @./ccproxy.yaml
- contains settings for `ccproxy` such as debug mode, any other ccproxy specific settings, and most importantly, the `rules` config
- Expect `ccproxy.yaml` file in the same directory as `config.yaml`

## Example Configuration File

```yaml
ccproxy:
  debug: true
  rules:
    - label: token_count
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 60000
    - label: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: claude-3-5-haiku-20241022
    - label: think
      rule: ccproxy.rules.ThinkingRule
    - label: web_search
      rule: ccproxy.rules.MatchToolRule
      params:
        - tool_name: WebSearch
```

- Initialize `ClassificationRule` objects at start when reading `ccproxy.yaml` config
  - Every rule's label must be matching a model in the LiteLLM proxy `config.yaml` `model_list` field
- Need to Remove the `RoutingLabel` class. Now labels are defined by the user and associated with a `ClassificationRule`
  - `ClassificationRule.evaluate` returns a `RoutingLabel`, therefore the evaluate function should probably return true or false and the classifier uses the associated label name from the config file for the first rule in order of priority that returns true
- `rule` field is the path of a python import, so built in rules can be imported by importing `ccproxy.rules.{rule name}` just like how LiteLLM imports the hook with `callbacks: custom_callbacks.proxy_handler_instance`
- `params` field is treated as \*args and/or \*\*kwargs according to the rule's class constructor
