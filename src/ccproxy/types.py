"""Type definitions for ccproxy."""

from typing import Literal, TypeAlias

# Routing labels
RoutingLabel: TypeAlias = Literal["default", "background", "think", "large_context", "web_search"]

# Model provider types
ModelProvider: TypeAlias = Literal[
    "openai",
    "anthropic",
    "google",
    "azure",
    "openrouter",
    "perplexity",
    "ollama",
    "bedrock",
    "vertex",
]

# Log formats
LogFormat: TypeAlias = Literal["json", "text"]

# Log levels
LogLevel: TypeAlias = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
