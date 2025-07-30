"""LiteLLM hook compatibility module.

This module provides a singleton ModelRouter instance that can be imported
by LiteLLM hooks as if it were litellm.proxy.proxy_server.llm_router.

Usage in LiteLLM hooks:
    from ccproxy.llm_router import llm_router

    # Get all available models
    models = llm_router.get_model_list()

    # Access via property
    models = llm_router.model_list

    # Get model groups
    groups = llm_router.model_group_alias

    # Get available model names
    available = llm_router.get_available_models()
"""

from typing import Any


class _LazyRouter:
    """Lazy wrapper for ModelRouter to avoid initialization on import."""

    def __getattr__(self, name: str) -> Any:
        """Lazily initialize and delegate to the actual router."""
        from ccproxy.router import get_router

        router = get_router()
        return getattr(router, name)


# Global singleton instance for LiteLLM hook access
llm_router = _LazyRouter()

# Export the instance
__all__ = ["llm_router"]
