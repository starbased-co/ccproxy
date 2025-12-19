# ccproxy Architecture

This document describes the internal architecture and request flow of ccproxy.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Claude Code / Client                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LiteLLM Proxy                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CCProxyHandler                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │  Classifier  │  │    Router    │  │         Hooks            │  │   │
│  │  │              │  │              │  │  ┌────────────────────┐  │  │   │
│  │  │ Token Count  │  │ Model Lookup │  │  │   rule_evaluator   │  │  │   │
│  │  │ Thinking Det │  │ Config Load  │  │  │   model_router     │  │  │   │
│  │  │              │  │              │  │  │   forward_oauth    │  │  │   │
│  │  └──────────────┘  └──────────────┘  │  │   capture_headers  │  │  │   │
│  │                                       │  └────────────────────┘  │  │   │
│  │                                       └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          Metrics Collector                           │   │
│  │  Total Requests │ By Model │ By Rule │ Success/Fail │ Uptime        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
            │   Anthropic  │    │    Gemini    │    │   OpenAI     │
            │     API      │    │     API      │    │     API      │
            └──────────────┘    └──────────────┘    └──────────────┘
```

---

## Component Descriptions

### CCProxyHandler

The main entry point, implementing LiteLLM's `CustomLogger` interface.

```python
class CCProxyHandler(CustomLogger):
    def __init__(self):
        self.classifier = RequestClassifier()
        self.router = get_router()
        self.metrics = get_metrics()
        self.hooks = config.load_hooks()
    
    async def async_pre_call_hook(self, data, user_api_key_dict):
        # Run hooks → classify → route → return modified data
        
    async def async_log_success_event(self, kwargs, response_obj):
        # Record success metrics
        
    async def async_log_failure_event(self, kwargs, response_obj):
        # Record failure metrics
```

### RequestClassifier

Analyzes requests to determine routing characteristics.

```python
class RequestClassifier:
    def classify(self, data: dict) -> ClassificationResult:
        # Returns: token_count, has_thinking, model_name, etc.
```

**Classification Features:**
- Token counting (using tiktoken)
- Thinking parameter detection
- Message content analysis

### ModelRouter

Maps rule names to LiteLLM model configurations.

```python
class ModelRouter:
    def get_model(self, model_name: str) -> ModelConfig | None:
        # Lookup model in config, reload if needed
    
    def reload_models(self):
        # Refresh model mapping (5s cooldown)
```

**Features:**
- Lazy model loading
- Automatic reload on model miss
- Thread-safe access

### Hooks System

Pluggable request processors executed in sequence.

```python
# Hook signature
def my_hook(data: dict, user_api_key_dict: dict, **kwargs) -> dict:
    # Modify and return data
```

**Built-in Hooks:**

| Hook | Purpose |
|------|---------|
| `rule_evaluator` | Evaluate classification rules |
| `model_router` | Route to target model |
| `forward_oauth` | Add OAuth token to request |
| `capture_headers` | Store request headers |
| `store_metadata` | Store request metadata |

### Metrics Collector

Thread-safe metrics tracking.

```python
class MetricsCollector:
    def record_request(self, model_name, rule_name, is_passthrough)
    def record_success()
    def record_failure()
    def get_snapshot() -> MetricsSnapshot
```

**Tracked Metrics:**
- Total/successful/failed requests
- Requests by model
- Requests by rule
- Passthrough requests
- Uptime

---

## Request Flow

### 1. Request Arrival

```
Client Request
     │
     ▼
┌─────────────────────────────────────┐
│         async_pre_call_hook         │
│                                     │
│  1. Skip if health check            │
│  2. Extract metadata                │
│  3. Run hook chain                  │
│  4. Log routing decision            │
│  5. Record metrics                  │
└─────────────────────────────────────┘
```

### 2. Hook Chain Execution

```
┌─────────────────────────────────────────────────────────────┐
│                       Hook Chain                             │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │rule_evaluator│ → │ model_router │ → │forward_oauth │    │
│  │              │   │              │   │              │    │
│  │ Classify req │   │ Route model  │   │ Add token    │    │
│  │ Match rules  │   │ Update data  │   │ Set headers  │    │
│  └──────────────┘   └──────────────┘   └──────────────┘    │
│                                                              │
│  Each hook modifies 'data' dict and passes to next          │
└─────────────────────────────────────────────────────────────┘
```

### 3. Rule Evaluation

```
┌─────────────────────────────────────────────────────────────┐
│                    Rule Evaluation                           │
│                                                              │
│  For each rule in config.rules:                             │
│    ┌─────────────────────────────────────────────────────┐  │
│    │ if rule.evaluate(classification_result):            │  │
│    │     return rule.model_name  # First match wins      │  │
│    └─────────────────────────────────────────────────────┘  │
│                                                              │
│  If no match and default_model_passthrough:                 │
│    return original_model                                     │
└─────────────────────────────────────────────────────────────┘
```

### 4. Model Routing

```
┌─────────────────────────────────────────────────────────────┐
│                    Model Routing                             │
│                                                              │
│  1. Get model config from router                            │
│  2. Update request with new model                           │
│  3. Store routing metadata:                                 │
│     - ccproxy_model_name                                    │
│     - ccproxy_litellm_model                                 │
│     - ccproxy_is_passthrough                                │
│     - ccproxy_matched_rule                                  │
└─────────────────────────────────────────────────────────────┘
```

### 5. Response Handling

```
┌─────────────────────────────────────────────────────────────┐
│                   Response Handling                          │
│                                                              │
│  Success:                          Failure:                 │
│  ┌─────────────────────────┐      ┌─────────────────────┐  │
│  │async_log_success_event  │      │async_log_failure_evt│  │
│  │                         │      │                     │  │
│  │ - Update Langfuse trace │      │ - Log error details │  │
│  │ - Log success           │      │ - Record metrics    │  │
│  │ - Record metrics        │      │                     │  │
│  └─────────────────────────┘      └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration Loading

### Discovery Order

```
┌─────────────────────────────────────────────────────────────┐
│                Configuration Discovery                       │
│                                                              │
│  Priority 1: $CCPROXY_CONFIG_DIR/ccproxy.yaml               │
│      ↓                                                       │
│  Priority 2: ./ccproxy.yaml (current directory)             │
│      ↓                                                       │
│  Priority 3: ~/.ccproxy/ccproxy.yaml                        │
│      ↓                                                       │
│  Priority 4: Default values                                  │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Validation

```
┌─────────────────────────────────────────────────────────────┐
│                  Validation Checks                           │
│                                                              │
│  ✓ Rule name uniqueness                                     │
│  ✓ Handler path format (module:ClassName)                   │
│  ✓ Hook path format (module.path.function)                  │
│  ✓ OAuth command non-empty                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## OAuth Token Management

### Token Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                  OAuth Token Lifecycle                       │
│                                                              │
│  Startup:                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ _load_credentials()                                  │    │
│  │   Execute shell commands for each provider           │    │
│  │   Cache tokens in _oat_values                        │    │
│  │   Store user-agents in _oat_user_agents              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Background Refresh (if oauth_refresh_interval > 0):        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ start_background_refresh()                           │    │
│  │   Daemon thread runs every N seconds                 │    │
│  │   Calls refresh_credentials()                        │    │
│  │   Updates cached tokens                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Thread Safety

### Shared Resources

| Resource | Protection | Notes |
|----------|------------|-------|
| `_config_instance` | `threading.Lock` | Singleton config |
| `_router_instance` | `threading.Lock` | Singleton router |
| `ModelRouter._lock` | `threading.RLock` | Model loading |
| `MetricsCollector._lock` | `threading.Lock` | Counter updates |
| `_request_metadata_store` | TTL + LRU cleanup | Max 10,000 entries |

---

## File Structure

```
src/ccproxy/
├── __init__.py
├── __main__.py          # Entry point
├── classifier.py        # Request classification
├── cli.py              # Command-line interface
├── config.py           # Configuration management
├── handler.py          # LiteLLM CustomLogger
├── hooks.py            # Hook implementations
├── metrics.py          # Metrics collection
├── router.py           # Model routing
├── rules.py            # Classification rules
├── utils.py            # Utilities
└── templates/
    ├── ccproxy.yaml    # Default config
    ├── ccproxy.py      # Custom hooks template
    └── config.yaml     # LiteLLM config template
```

---

## Extension Points

### Custom Rules

```python
from ccproxy.rules import ClassificationRule

class MyCustomRule(ClassificationRule):
    def __init__(self, my_param: str):
        self.my_param = my_param
    
    def evaluate(self, context: dict) -> bool:
        # Your logic here
        return True
```

### Custom Hooks

```python
def my_custom_hook(data: dict, user_api_key_dict: dict, **kwargs) -> dict:
    # Access classifier and router via kwargs
    classifier = kwargs.get('classifier')
    router = kwargs.get('router')
    
    # Modify data
    data['metadata']['my_custom_field'] = 'value'
    
    return data
```

### Metrics Access

```python
from ccproxy.metrics import get_metrics

metrics = get_metrics()
snapshot = metrics.get_snapshot()

print(f"Total: {snapshot.total_requests}")
print(f"By model: {snapshot.requests_by_model}")
```
