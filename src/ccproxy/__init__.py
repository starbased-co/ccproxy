"""CCProxy - LiteLLM-based transformation hook system for context-aware routing."""

from ccproxy.config import CCProxyConfig, ConfigProvider, get_config, reload_config
from ccproxy.handler import CCProxyHandler
from ccproxy.llm_router import llm_router
from ccproxy.router import ModelRouter, get_router, reload_router
from ccproxy.watcher import start_config_watcher, stop_config_watcher

proxy_handler_instance = CCProxyHandler()

__version__ = "0.1.0"
__all__ = [
    "CCProxyHandler",
    "CCProxyConfig",
    "ConfigProvider",
    "get_config",
    "reload_config",
    "start_config_watcher",
    "stop_config_watcher",
    "ModelRouter",
    "get_router",
    "reload_router",
    "llm_router",
    "proxy_handler_instance",
]
