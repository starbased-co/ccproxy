"""CCProxyHandler - Main LiteLLM CustomLogger implementation."""

from typing import Any, TypedDict

from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]

from ccproxy.classifier import RequestClassifier
from ccproxy.config import get_config


class RequestData(TypedDict, total=False):
    """Type definition for LiteLLM request data."""

    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    metadata: dict[str, Any] | None


def ccproxy_get_model(data: dict[str, Any]) -> str:
    """Main routing function that determines which model to use.

    This function is called by LiteLLM to determine model routing.

    Args:
        data: Request data from LiteLLM

    Returns:
        Model name to route to
    """
    config = get_config()
    classifier = RequestClassifier()

    # Classify the request
    label = classifier.classify(data)

    # Get model for label from LiteLLM config
    model = config.get_model_for_label(label.value)

    if model is None:
        # Fallback to original model if no mapping found
        model = data.get("model", "claude-3-5-sonnet-20241022")

    # Log routing decision if debug enabled
    if config.debug:
        print(f"[ccproxy] Routed to {model} (label: {label.value})")

    return model


class CCProxyHandler(CustomLogger):  # type: ignore[misc]
    """LiteLLM CustomLogger for context-aware request routing.

    This handler integrates with LiteLLM's callback system to provide
    context-aware routing for Claude Code requests.
    """

    def __init__(self) -> None:
        """Initialize CCProxyHandler."""
        super().__init__()
        self.config = get_config()
        self.classifier = RequestClassifier()

    async def async_pre_call_hook(
        self,
        data: dict[str, Any],
        user_api_key_dict: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Pre-call hook for request routing.

        This hook is called before the LLM request is made, allowing us to
        modify the request data including the target model.

        Args:
            data: Request data dictionary
            user_api_key_dict: User API key information
            **kwargs: Additional arguments from LiteLLM

        Returns:
            Modified request data
        """
        # Use ccproxy_get_model for routing
        data["model"] = ccproxy_get_model(data)

        # Add metadata for tracking
        if "metadata" not in data:
            data["metadata"] = {}

        label = self.classifier.classify(data)
        data["metadata"]["ccproxy_label"] = label.value
        data["metadata"]["ccproxy_original_model"] = data.get("model")

        return data
