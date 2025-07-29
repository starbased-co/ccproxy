# Product Requirements Document: `ccproxy` Claude Code Router via LiteLLM Hooks

## Executive Summary

This PRD outlines the requirements for reimplementing [`claude-code-router`](https://github.com/musistudio/claude-code-router), a proxy server that Claude Code's LLM requests to different providers based on properties of the request such as tool usage, number of tokens, thinking, etc. `ccproxy` will be a similartransformation server using LiteLLM call hooks for redirecting Claude Code API requests. This approach leverages LiteLLM's mature infrastructure while providing the advanced transformation capabilities of the original project.

## Problem Statement

The current TypeScript project attempts to create a standalone LLM transformation server but:

- Duplicates functionality already available in LiteLLM
- Lacks tests, documentation, and community support
- Requires maintaining separate infrastructure

By reimplementing as LiteLLM hooks, we can provide the same transformation capabilities while leveraging LiteLLM's:

- Battle-tested infrastructure handling 100+ providers
- Existing security measures and best practices
- Active community and documentation
- Built-in observability and monitoring

## Goals & Objectives

### Primary Goals

1. **Provide Advanced Transformation Capabilities** - Enable complex request/response transformations beyond basic modifications
2. **Simplify Deployment** - Leverage LiteLLM's existing infrastructure
3. **Enable Composability** - Allow multiple transformations to be chained and combined

### Success Metrics

- Support for all transformation patterns from the original project
- Comprehensive test coverage (>90%)

## User Stories

### As a Developer

1. I want to enhance tool call parsing to handle malformed JSON from LLMs safely
2. I want to transform provider-specific formats to/from unified formats
3. I want to add custom streaming transformations without writing complex stream handling
4. I want to compose multiple transformations in a specific order
5. I want to dynamically select transformations based on request context

### As a Security Engineer

1. I want confidence that malformed LLM responses cannot execute arbitrary code
2. I want audit logs of all transformations applied
3. I want to validate and sanitize all transformed data

## Functional Requirements

### Core Hook Implementation

#### 1. Enhanced Tool Call Parser Hook

```python
class EnhancedToolCallHook(CustomLogger):
    """Safely parse and repair malformed tool calls from LLMs"""

    def __init__(self):
        self.jsonrepair = jsonrepair  # Safe JSON repair library

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        # Parse and repair tool calls in responses
        if "tool_calls" in response.get("choices", [{}])[0].get("message", {}):
            response = self._repair_tool_calls(response)
        return response

    async def async_post_call_streaming_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: str,
    ):
        # Handle streaming tool call repairs
        return self._repair_streaming_chunk(response)
```

#### 2. Unified Format Transformer Hook

```python
class UnifiedFormatHook(CustomLogger):
    """Transform between provider-specific and unified formats"""

    def __init__(self, transformers: Dict[str, BaseTransformer]):
        self.transformers = transformers

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: str
    ):
        # Transform unified format to provider format
        provider = self._extract_provider(data)
        if provider in self.transformers:
            data = await self.transformers[provider].transform_request_out(data)
        return data

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        # Transform provider format to unified format
        provider = self._extract_provider(data)
        if provider in self.transformers:
            response = await self.transformers[provider].transform_response_in(response)
        return response
```

#### 3. Composable Transformation Pipeline

```python
class TransformationPipeline(CustomLogger):
    """Compose multiple transformations in order"""

    def __init__(self, pipeline_config: List[Dict]):
        self.pre_hooks = []
        self.post_hooks = []
        self.stream_hooks = []
        self._build_pipeline(pipeline_config)

    async def async_pre_call_hook(self, *args, **kwargs):
        data = kwargs.get("data")
        for hook in self.pre_hooks:
            data = await hook(data, *args, **kwargs)
        return data
```

### Transformation Features

#### 1. Safe JSON Repair

- Use `jsonrepair` library instead of dangerous `vm` module
- Handle common LLM JSON errors:
  - Missing quotes around keys/values
  - Trailing commas
  - Comments in JSON
  - Incomplete JSON structures
  - Mixed single/double quotes

#### 2. Provider-Specific Transformations

Transform between different provider formats:

- OpenAI ↔ Anthropic format conversion
- Google Vertex AI ↔ unified format
- Custom provider format support

#### 3. Streaming Transformations

- Buffer management for incomplete chunks
- State tracking across streaming chunks
- Tool call accumulation and repair
- Efficient memory usage with size limits

#### 4. Dynamic Transformation Selection

```python
async def async_pre_call_hook(self, *args, **kwargs):
    # Select transformer based on context
    if kwargs.get("user_api_key_dict").metadata.get("transform_mode") == "enhanced":
        return await self.enhanced_transformer(*args, **kwargs)
    return await self.standard_transformer(*args, **kwargs)
```

## Technical Requirements

### Architecture

```
┌─────────────────────┐
│   LiteLLM Proxy     │
├─────────────────────┤
│   Hook Registry     │
├─────────────────────┤
│ Transformation Hooks│
│ ┌─────────────────┐ │
│ │ Tool Call Parser│ │
│ ├─────────────────┤ │
│ │ Format Unified  │ │
│ ├─────────────────┤ │
│ │ Custom Pipeline │ │
│ └─────────────────┘ │
├─────────────────────┤
│  Provider Backends  │
└─────────────────────┘
```

### Dependencies

- `jsonrepair`: Safe JSON parsing and repair
- `pydantic`: Data validation and serialization
- `typing-extensions`: Advanced type hints
- LiteLLM core dependencies

### Security Requirements

- No code execution vulnerabilities
- Input validation on all transformations
- Sanitization of transformed outputs
- Audit logging of transformation activities
- Rate limiting on transformation complexity

## Implementation Plan

### Phase 1: Core Hook Framework

1. Implement base transformation hook classes
2. Create safe JSON repair functionality
3. Build streaming transformation support
4. Add comprehensive error handling
5. Implement transformation pipeline composer
6. Add dynamic transformation selection
7. Create configuration management
8. Build monitoring and metrics

### Phase 2: Testing & Documentation (Week 7-8)

1. Unit tests for all transformers
2. Integration tests with LiteLLM
3. Comprehensive documentation

## `claude-code-router` Configuration Example

```
{
  "Providers": [
    {
      "name": "openrouter",
      "api_base_url": "https://openrouter.ai/api/v1/chat/completions",
      "api_key": "sk-xxx",
      "models": [
        "google/gemini-2.5-pro-preview",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.7-sonnet:thinking"
      ],
      "transformer": {
        "use": ["openrouter"]
      }
    },
    {
      "name": "ollama",
      "api_base_url": "http://localhost:11434/v1/chat/completions",
      "api_key": "ollama",
      "models": ["qwen2.5-coder:latest"]
    },
    {
      "name": "gemini",
      "api_base_url": "https://generativelanguage.googleapis.com/v1beta/models/",
      "api_key": "sk-xxx",
      "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
      "transformer": {
        "use": ["gemini"]
      }
    },
  ],
  "Router": {
    "default": "deepseek,deepseek-chat",
    "background": "ollama,qwen2.5-coder:latest",
    "think": "deepseek,deepseek-reasoner",
    "longContext": "openrouter,google/gemini-2.5-pro-preview",
    "longContextThreshold": 60000,
    "webSearch": "gemini,gemini-2.5-flash"
  },
  "APIKEY": "your-secret-key",
  "HOST": "0.0.0.0",
  "API_TIMEOUT_MS": 600000
}
```

The `Router` object defines which model to use for different scenarios:

- `default`: The default model for general tasks.
- `background`: A model for background tasks. This can be a smaller, local model to save costs.
- `think`: A model for reasoning-heavy tasks, like Plan Mode.
- `longContext`: A model for handling long contexts (e.g., > 60K tokens).
- `longContextThreshold` (optional): The token count threshold for triggering the long context model. Defaults to 60000 if not specified.
- `webSearch`: Used for handling web search tasks and this requires the model itself to support the feature. If you're using openrouter, you need to add the `:online` suffix after the model name.

> [!NOTE]
> `longContextThreshold` will be specified through an environment variable `$CCPROXY_CONTEXT_THRESHOLD`

For `claude-code-router`, specifying custom models for these fields are mandatory. This is not desirable behavior

For `ccproxy`, these fields will be optional. Every request will still be labeled as one of `default`, `background`, `think`, `large_context`, or `websearch`, just as they are in `claude-code-router`. For `ccproxy` when one of these is not specified the request will be left unmodified and continue to Anthropic's API.

Here is how `claude-code-router` determines which label to apply to every request (will be re-implemented in litellm hook):

## `claude-code-router` Model Router Example

```typescript
const getUseModel = async (req: any, tokenCount: number, config: any) => {
  if (req.body.model.includes(",")) {
    return req.body.model;
  }
  // if tokenCount is greater than the configured threshold, use the long context model
  const longContextThreshold = config.Router.longContextThreshold || 60000;
  if (tokenCount > longContextThreshold && config.Router.longContext) {
    log(
      "Using long context model due to token count:",
      tokenCount,
      "threshold:",
      longContextThreshold,
    );
    return config.Router.longContext;
  }
  // If the model is claude-3-5-haiku, use the background model
  if (
    req.body.model?.startsWith("claude-3-5-haiku") &&
    config.Router.background
  ) {
    log("Using background model for ", req.body.model);
    return config.Router.background;
  }
  // if thinking exists, use the think model
  if (req.body.thinking && config.Router.think) {
    log("Using think model for ", req.body.thinking);
    return config.Router.think;
  }
  // if a web_search tool is present, use the web_search model
  if (
    Array.isArray(req.body.tools) &&
    req.body.tools.some((tool: any) => tool.type?.startsWith("web_search")) &&
    config.Router.webSearch
  ) {
    return config.Router.webSearch;
  }
  return config.Router!.default;
};
```

## `ccproxy` Configuration Example

```yaml
model_list:
  - model_name: default # model used for `default` requests
    litellm_params: # all params accepted by litellm.completion() - https://docs.litellm.ai/docs/completion/input
      model: claude-sonnet-4-20250514 ### MODEL NAME sent to `litellm.completion()` ###
      api_base: https://api.anthropic.com
  - model_name: background # model used for `background` requests
    litellm_params:
      model: openrouter/openai/gpt-4
      api_base: https://openrouter.ai/api/v1
  - model_name: think # model used for `think` requests
    litellm_params:
      model: claude-opus-4-20250514
      api_base: https://api.anthropic.com
  - model_name: large_context # model used for `large_context` labeled requests
    litellm_params:
      model: openrouter/openai/gpt-4
      api_base: https://openrouter.ai/api/v1
  - model_name: web_search # model used for `web_search` labeled requests
    litellm_params:
      model: openrouter/openai/gpt-4
      api_base: https://openrouter.ai/api/v1

litellm_settings:
  callbacks: custom_callbacks.ccproxy

  monitoring:
    log_transformations: true
    metrics_enabled: true
    slow_transformation_threshold: 50ms
```

## Hook Example

Adapted from the [LiteLLM call hooks documentation](https://docs.litellm.ai/docs/proxy/call_hooks).

```python
from litellm.integrations.custom_logger import CustomLogger
import litellm
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from litellm.types.utils import ModelResponseStream
from typing import Any, AsyncGenerator, Optional, Literal



# EXAMPLE: Roughly equivalent implementation to `getUseModel`
def ccproxy_router(self, user_api_key_dict: UserAPIKeyAuth, cache: DualCache, data: dict, call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
        ]):
    # Re-implement claude-code-router's `getUseModel` function here, see the "`claude-code-router` Model Router Example" section above
    request_type = ccproxy_get_model(user_api_key_dict, cache, data, call_type)
    match request_type:
        case "background":
          # uses background model
        case "think":
          # uses think model
        case "long_context":
          # uses long_context model
        case "web_search":
          # uses web_search model
        case "default":
        case _: # default case
          # uses default model

# This file includes the custom callbacks for LiteLLM Proxy
# Once defined, these can be passed in proxy_config.yaml
class CCProxyHandler(CustomLogger): # https://docs.litellm.ai/docs/observability/custom_callback#callback-class
    # Class variables or attributes
    def __init__(self):
        pass

    #### CALL HOOKS - proxy only ####

    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache: DualCache, data: dict, call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
        ]):
        return ccproxy_router(user_api_key_dict, cache, data, call_type)

    async def async_post_call_failure_hook(
        self,
        request_data: dict,
        original_exception: Exception,
        user_api_key_dict: UserAPIKeyAuth,
        traceback_str: Optional[str] = None,
    ):
        pass

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        pass

    async def async_moderation_hook( # call made in parallel to llm api call
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        call_type: Literal["completion", "embeddings", "image_generation", "moderation", "audio_transcription"],
    ):
        pass

    async def async_post_call_streaming_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: str,
    ):
        pass

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[ModelResponseStream, None]:
        """
        Passes the entire stream to the guardrail

        This is useful for plugins that need to see the entire stream.
        """
        async for item in response:
            yield item

ccproxy = CCProxyHandler()
```

## Success Criteria

1. **Security**: Zero vulnerabilities, passed security audit
2. **Compatibility**: All original transformations working
3. **Performance**: Meeting latency requirements
4. **Adoption**: Clear migration path with minimal disruption
5. **Maintenance**: Active community contributions

## Appendix

### A. Comparison with Original Project

| Feature           | Original (TypeScript) | New (LiteLLM Hooks) |
| ----------------- | --------------------- | ------------------- |
| Tool Call Parsing | vm module (unsafe)    | jsonrepair (safe)   |
| Deployment        | Standalone server     | LiteLLM integration |
| Provider Support  | Limited               | 100+ via LiteLLM    |
| Testing           | None                  | Comprehensive       |
| Documentation     | Minimal               | Extensive           |
| Community         | Single maintainer     | LiteLLM ecosystem   |

