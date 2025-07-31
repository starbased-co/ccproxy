"""CCProxyHandler - Main LiteLLM CustomLogger implementation."""

import logging
from typing import Any, TypedDict

from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]

from ccproxy.classifier import RequestClassifier
from ccproxy.config import get_config
from ccproxy.router import get_router

# Set up structured logging
logger = logging.getLogger(__name__)


class RequestData(TypedDict, total=False):
    """Type definition for LiteLLM request data."""

    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    metadata: dict[str, Any] | None


def ccproxy_get_model(data: dict[str, Any]) -> str:
    """Main routing function that determines which model to use.

    This function is called by LiteLLM to determine model routing.
    It provides backward compatibility for direct function calls.

    Args:
        data: Request data from LiteLLM

    Returns:
        Model name to route to
    """
    config = get_config()
    router = get_router()
    classifier = RequestClassifier()

    # Classify the request
    label = classifier.classify(data)

    # Get model for label from router - but only if the specific label exists
    router_available_models = router.get_available_models()

    if label in router_available_models:
        # The specific label is configured, use it
        model_config = router.get_model_for_label(label)
        if model_config is not None:
            model: str = str(model_config["litellm_params"]["model"])
        else:
            # Should not happen, but fallback to original
            model = str(data.get("model", "claude-3-5-sonnet-20241022"))
    else:
        # The specific label is not configured, use original model
        model = str(data.get("model", "claude-3-5-sonnet-20241022"))

    # Log routing decision if debug enabled
    if config.debug:
        print(f"[ccproxy] Routed to {model} (label: {label})")

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
        self.router = get_router()

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
        # Store original model for logging
        original_model = data.get("model", "unknown")

        # Classify the request
        label = self.classifier.classify(data)

        # Get model configuration from router - but only if the specific label exists
        router_available_models = self.router.get_available_models()
        model_config = None

        if label in router_available_models:
            # The specific label is configured, use it
            model_config = self.router.get_model_for_label(label)
            if model_config is not None:
                data["model"] = model_config["litellm_params"]["model"]
                routed_model = data["model"]
            else:
                # Should not happen, but keep original
                routed_model = original_model
        else:
            # The specific label is not configured, keep original model
            routed_model = original_model

        # Add metadata for tracking
        if "metadata" not in data:
            data["metadata"] = {}

        data["metadata"]["ccproxy_label"] = label
        data["metadata"]["ccproxy_original_model"] = original_model
        data["metadata"]["ccproxy_routed_model"] = routed_model

        # Generate request ID if not present
        if "request_id" not in data["metadata"]:
            import uuid

            data["metadata"]["request_id"] = str(uuid.uuid4())

        # Log routing decision with structured logging
        self._log_routing_decision(
            label=label,
            original_model=original_model,
            routed_model=routed_model,
            request_id=data["metadata"]["request_id"],
            model_config=model_config,
        )

        return data

    def _log_routing_decision(
        self,
        label: str,
        original_model: str,
        routed_model: str,
        request_id: str,
        model_config: dict[str, Any] | None,
    ) -> None:
        """Log routing decision with structured logging.

        Args:
            label: Classification label
            original_model: Original model requested
            routed_model: Model after routing
            request_id: Unique request identifier
            model_config: Model configuration from router (None if fallback)
        """
        log_data = {
            "event": "ccproxy_routing",
            "label": label,
            "original_model": original_model,
            "routed_model": routed_model,
            "request_id": request_id,
            "fallback_used": model_config is None,
        }

        # Add model info if available (excluding sensitive data)
        if model_config and "model_info" in model_config:
            model_info = model_config["model_info"]
            # Only include non-sensitive metadata
            safe_info = {}
            for key, value in model_info.items():
                if key not in ("api_key", "secret", "token", "password"):
                    safe_info[key] = value

            if safe_info:
                log_data["model_info"] = safe_info

        logger.info("CCProxy routing decision", extra=log_data)

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Log successful completion of a request.

        Args:
            kwargs: Request arguments
            response_obj: LiteLLM response object
            start_time: Request start timestamp
            end_time: Request completion timestamp
        """
        metadata = kwargs.get("metadata", {})
        request_id = metadata.get("request_id", "unknown")
        label = metadata.get("ccproxy_label", "unknown")

        # Calculate duration
        duration_ms = (end_time - start_time) * 1000

        log_data = {
            "event": "ccproxy_success",
            "request_id": request_id,
            "label": label,
            "duration_ms": round(duration_ms, 2),
            "model": kwargs.get("model", "unknown"),
        }

        # Add usage stats if available (non-sensitive)
        if hasattr(response_obj, "usage") and response_obj.usage:
            usage = response_obj.usage
            log_data["usage"] = {
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        logger.info("CCProxy request completed", extra=log_data)

    async def async_log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Log failed request.

        Args:
            kwargs: Request arguments
            response_obj: LiteLLM response object (error)
            start_time: Request start timestamp
            end_time: Request completion timestamp
        """
        metadata = kwargs.get("metadata", {})
        request_id = metadata.get("request_id", "unknown")
        label = metadata.get("ccproxy_label", "unknown")

        # Calculate duration
        duration_ms = (end_time - start_time) * 1000

        log_data = {
            "event": "ccproxy_failure",
            "request_id": request_id,
            "label": label,
            "duration_ms": round(duration_ms, 2),
            "model": kwargs.get("model", "unknown"),
            "error_type": type(response_obj).__name__,
        }

        # Add error message if available (but mask sensitive content)
        if hasattr(response_obj, "message"):
            error_message = str(response_obj.message)
            # Basic masking of potential API keys or tokens
            import re

            error_message = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", error_message)
            error_message = re.sub(r"[a-fA-F0-9]{32,}", "[REDACTED_TOKEN]", error_message)
            log_data["error_message"] = error_message[:500]  # Truncate long messages

        logger.error("CCProxy request failed", extra=log_data)

    async def async_log_stream_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Log streaming request completion.

        Args:
            kwargs: Request arguments
            response_obj: LiteLLM streaming response object
            start_time: Request start timestamp
            end_time: Request completion timestamp
        """
        metadata = kwargs.get("metadata", {})
        request_id = metadata.get("request_id", "unknown")
        label = metadata.get("ccproxy_label", "unknown")

        # Calculate duration
        duration_ms = (end_time - start_time) * 1000

        log_data = {
            "event": "ccproxy_stream_complete",
            "request_id": request_id,
            "label": label,
            "duration_ms": round(duration_ms, 2),
            "model": kwargs.get("model", "unknown"),
            "streaming": True,
        }

        logger.info("CCProxy streaming request completed", extra=log_data)
