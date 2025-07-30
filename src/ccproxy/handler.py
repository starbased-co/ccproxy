"""CCProxyHandler - Main LiteLLM CustomLogger implementation."""

from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]


class CCProxyHandler(CustomLogger):  # type: ignore[misc]
    """LiteLLM CustomLogger for context-aware request routing."""

    def __init__(self) -> None:
        """Initialize CCProxyHandler."""
        super().__init__()
