"""CCProxy - LiteLLM-based transformation hook system for context-aware routing."""

from ccproxy.config import CCProxyConfig, ConfigProvider, get_config
from ccproxy.handler import CCProxyHandler
from ccproxy.llm_router import llm_router
from ccproxy.router import ModelRouter, get_router

__version__ = "0.1.0"
__all__ = [
    "CCProxyHandler",
    "CCProxyConfig",
    "ConfigProvider",
    "get_config",
    "ModelRouter",
    "get_router",
    "llm_router",
]
