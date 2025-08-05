# Product Requirements Document: ccproxy - Context-Aware Proxy for Claude Code

## Executive Summary

ccproxy is a context-aware proxy specifically designed for Claude Code that intelligently routes requests to different AI models based on the request context. By analyzing incoming Claude Code requests (simple queries, complex code generation, debugging tasks, refactoring operations, etc.), ccproxy routes them to the most appropriate model - using fast, cost-effective models for simple queries and powerful models for complex tasks.

This PRD outlines the requirements for reimplementing [`claude-code-router`](https://github.com/musistudio/claude-code-router) as a Python-based transformation server using LiteLLM call hooks. **ccproxy is NOT a general-purpose LLM proxy** but is specifically tuned for Claude Code's usage patterns and request context analysis.

## Problem Statement

Claude Code needs intelligent request routing based on context to optimize both performance and cost:

### Context-Based Routing Specifications

- **Simple queries** ("What is X?", "How do I...") don't need powerful models

- ## **Complex tasks** (debugging, architecture design, large refactoring) require advanced reasoning

- **Background tasks** (formatting, simple fixes) can use lightweight models
- **Large context operations** (analyzing entire codebases) need specialized handling
- **Web search queries** benefit from models with internet access

### Current Implementation Limitations

The existing TypeScript implementation has several limitations:

- Duplicates functionality already available in LiteLLM
- Lacks comprehensive tests and documentation
- Requires maintaining separate infrastructure
- Limited extensibility for new routing rules

### Solution: LiteLLM-Based Context Router

By reimplementing as LiteLLM hooks specifically for Claude Code, we can:

- Analyze Claude Code request patterns (token count, tool usage, code complexity)
- Route to appropriate models based on context-aware rules
- Leverage LiteLLM's mature infrastructure and provider support
- Maintain Claude Code-specific optimizations and patterns

## Goals & Objectives

### Primary Goals

1. **Context-Aware Routing** - Analyze Claude Code requests and route to optimal models
2. **Cost Optimization** - Use cheaper models for simple tasks without sacrificing quality
3. **Performance Enhancement** - Faster responses for simple queries, powerful models for complex tasks
4. **Claude Code Integration** - Seamless drop-in replacement maintaining API compatibility

### Success Metrics

- Maintain or improve response quality across all request types
- Zero breaking changes for Claude Code users
- Comprehensive test coverage (>90%)

## User Stories

### As a Claude Code User

1. I want my simple questions answered quickly using fast models
2. I want complex debugging tasks to use powerful reasoning models
3. I want large file operations to use models with extended context windows
4. I want my costs optimized without manually switching models
5. I want the proxy to be transparent - no changes to my workflow

### As a Developer

1. I want to customize routing rules for my specific use cases
2. I want detailed logs showing routing decisions
3. I want to add new model providers easily
4. I want to monitor performance and cost metrics
5. I want fallback behavior when preferred models are unavailable

## Claude Code Request Classification

### Request Types and Routing

| Request Type      | Characteristics                      | Recommended Model                     | Label           |
| ----------------- | ------------------------------------ | ------------------------------------- | --------------- |
| Default Query     | normal use+tools, basic questions    | Claude Sonnet, Gemini 2.5 Flash       | `default`       |
| Background Task   | Model explicitly set to haiku        | Claude Haiku                          | `background`    |
| Complex Reasoning | Has thinking blocks, complex prompts | Claude Opus, Gemini 2.5 Flash         | `think`         |
| Large Context     | >60,000 tokens                       | Gemini 2.5 Pro                        | `large_context` |
| Web Search        | Uses web_search tools                | Perplexity, Claude/Gemini with search | `web_search`    |

### Classification Logic (Priority Order)

```python
def classify_request(request):
    # 1. Check token count first (most objective)
    if request.token_count > CONTEXT_THRESHOLD:
        return "large_context"

    # 2. Check if explicitly using background model
    if request.model == "claude-3-5-haiku":
        return "background"

    # 3. Check for thinking
    if request.body.thinking:
        return "think"

    # 4. Check for web search tools
    if "web_search" in request.tools:
        return "web_search"

    # 5. Default
    return "default"
```

## Technical Architecture

### Core Components

1. **CCProxyHandler** - Main LiteLLM CustomLogger implementation
2. **RequestClassifier** - Analyzes requests and assigns routing labels

### LiteLLM replaces the need for

3. **ConfigurationManager** - Handles YAML config and environment overrides
4. **ModelRouter** - Maps labels to specific model configurations
5. **MetricsCollector** - Tracks routing decisions and performance

### Integration with LiteLLM

```python
from litellm.integrations.custom_logger import CustomLogger

class CCProxyHandler(CustomLogger):
    async def async_pre_call_hook(self, data, **kwargs):
        # Analyze request context
        label = self.classifier.classify(data)

        # Route to appropriate model
        data["model"] = self.router.get_model_for_label(label)

        # Log routing decision
        self.logger.info(f"Routed to {data['model']} (label: {label})")

        return data
```

### Example LiteLLM Configuration Schema

```yaml
# LiteLLM proxy config.yaml
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

ccproxy_settings:
  context_threshold: 60000
```

## Implementation Requirements

### Phase 1: Core Routing (MVP)

- Implement CCProxyHandler with basic routing logic
- Support all 5 routing labels from claude-code-router
- LiteLLM Proxy YAML configuration with environment overrides
- Basic logging of routing decisions

### Phase 2: Enhanced Features

- Request/response transformation capabilities
- Metrics collection and reporting

### Phase 3: Production Readiness

- Comprehensive test suite (>90% coverage)
- Performance benchmarking
- Documentation and examples
- Claude Code Wrapper

## Security Considerations

- API keys stored securely in environment variables
- No logging of sensitive request/response content
- HTTPS enforcement for all external calls
- Rate limiting and abuse prevention

## Testing Strategy

### Unit Tests

- Request classification logic
- Configuration parsing
- Model routing decisions
- Fallback behavior

### Integration Tests

- Full request lifecycle through LiteLLM
- Streaming and non-streaming responses
- Error handling and retries
- Provider-specific behaviors

### Performance Tests

- Routing overhead measurement
- Concurrent request handling
- Memory usage under load

## Documentation Requirements

1. **User Guide** - Installation, configuration, basic usage
2. **API Reference** - All configuration options and APIs
3. **Migration Guide** - Moving from claude-code-router
4. **Examples** - Common routing scenarios
5. **Troubleshooting** - Common issues and solutions

## Success Criteria

1. All claude-code-router routing patterns supported
2. <10ms routing overhead per request
3. Zero breaking changes for Claude Code users
4. 90%+ test coverage
5. Clear documentation with examples
6. Active monitoring and metrics

## Future Enhancements

- Machine learning-based classification
- Dynamic model selection based on load
- Cost prediction before routing
- Custom routing rules via plugins
- Multi-model ensemble responses
