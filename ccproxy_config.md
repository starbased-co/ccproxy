# `ccproxy.yaml` Config File

- `config.yaml` is the LiteLLM proxy config file, `ccproxy.yaml` will contain settings for `ccproxy` such as debug mode, model rules, and rule properties like the token count threshold

## Example Configuration File

```yaml
ccproxy:
  debug: true
  # list of
  rules:
    # python import of rule class in the same manner litellm does with `callbacks: custom_callbacks.proxy_handler_instance` in config.yaml
    - class: ccproxy.rules.TokenCountRule
      # all other properties will be passed as kwargs to the rule class
      threshold: 60000
    - class: ccproxy.rules.ModelNameRule
      name: model_name
      model: anthropic/claude-3-5-haiku-20241022
    - class: ccproxy.rules.ThinkingRule
      name:
```
