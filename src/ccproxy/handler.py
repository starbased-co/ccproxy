"""CCProxyHandler - Main LiteLLM CustomLogger implementation."""

import logging
from typing import Any, TypedDict

from litellm.integrations.custom_logger import CustomLogger

from ccproxy.classifier import RequestClassifier
from ccproxy.config import get_config
from ccproxy.router import get_router
from ccproxy.utils import calculate_duration_ms

# Set up structured logging
logger = logging.getLogger(__name__)


class RequestData(TypedDict, total=False):
    """Type definition for LiteLLM request data."""

    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    metadata: dict[str, Any] | None


def _determine_routed_model(
    data: dict[str, Any],
    label: str,
    router: Any,
    original_model: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Determine which model to route to based on classification label.

    Args:
        data: Request data from LiteLLM
        label: Classification label from the classifier
        router: The model router instance
        original_model: Original model from request (optional)

    Returns:
        Tuple of (routed_model, model_config)
    """
    # Get model for label from router - but only if the specific label exists
    router_available_models = router.get_available_models()

    if label in router_available_models:
        # The specific label is configured, use it
        model_config = router.get_model_for_label(label)
        if model_config is not None:
            routed_model = str(model_config["litellm_params"]["model"])
            return routed_model, model_config

    # The specific label is not configured or no config found, use original model
    if original_model is None:
        original_model = str(data.get("model", "claude-3-5-sonnet-20241022"))
    return original_model, None


class CCProxyHandler(CustomLogger):
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

        # Determine the routed model using shared logic
        routed_model, model_config = _determine_routed_model(data, label, self.router, original_model)

        # Update the model in the request
        data["model"] = routed_model

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

        # Handle OAuth token forwarding for Claude CLI
        # Check if this is a claude-cli request and targeting an Anthropic model
        request = data.get("proxy_server_request")
        if request:
            headers = request.get("headers") or {}
            user_agent = headers.get("user-agent", "")

            # Check if this is a claude-cli request and an Anthropic model
            if (
                user_agent
                and "claude-cli" in user_agent
                and ("anthropic/" in routed_model or routed_model.startswith("claude"))
            ):
                # Get the raw headers containing the OAuth token
                secret_fields = data.get("secret_fields") or {}
                raw_headers = secret_fields.get("raw_headers") or {}
                auth_header = raw_headers.get("authorization", "")

                # Only forward if we have an auth header
                if auth_header:
                    # Ensure the provider_specific_header structure exists
                    if "provider_specific_header" not in data:
                        data["provider_specific_header"] = {}
                    if "extra_headers" not in data["provider_specific_header"]:
                        data["provider_specific_header"]["extra_headers"] = {}

                    # Set the authorization header
                    data["provider_specific_header"]["extra_headers"]["authorization"] = auth_header

                    # Log OAuth forwarding
                    logger.info(
                        "Forwarding request with Claude Code OAuth token",
                        extra={
                            "event": "oauth_forwarding",
                            "user_agent": user_agent,
                            "model": routed_model,
                            "request_id": data["metadata"]["request_id"],
                        },
                    )

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
        # Display colored routing decision
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        # Color scheme based on routing
        if model_config is None:
            # Fallback - yellow
            color = "yellow"
            routing_type = "FALLBACK"
        elif original_model == routed_model:
            # No change - dim
            color = "dim"
            routing_type = "PASSTHROUGH"
        else:
            # Routed - green
            color = "green"
            routing_type = "ROUTED"

        # Create the routing message
        routing_text = Text()
        routing_text.append("🚀 CCProxy Routing Decision\n", style="bold cyan")
        routing_text.append("├─ Type: ", style="dim")
        routing_text.append(f"{routing_type}\n", style=f"bold {color}")
        routing_text.append("├─ Label: ", style="dim")
        routing_text.append(f"{label}\n", style="magenta")
        routing_text.append("├─ Original: ", style="dim")
        routing_text.append(f"{original_model}\n", style="blue")
        routing_text.append("└─ Routed to: ", style="dim")
        routing_text.append(f"{routed_model}", style=f"bold {color}")

        # Print the panel
        console.print(Panel(routing_text, border_style=color, padding=(0, 1)))

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

        # Calculate duration using utility function
        duration_ms = calculate_duration_ms(start_time, end_time)

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

        # Calculate duration using utility function
        duration_ms = calculate_duration_ms(start_time, end_time)

        log_data = {
            "event": "ccproxy_failure",
            "request_id": request_id,
            "label": label,
            "duration_ms": round(duration_ms, 2),
            "model": kwargs.get("model", "unknown"),
            "error_type": type(response_obj).__name__,
        }

        # Add error message if available
        if hasattr(response_obj, "message"):
            error_message = str(response_obj.message)
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

        # Calculate duration using utility function
        duration_ms = calculate_duration_ms(start_time, end_time)

        log_data = {
            "event": "ccproxy_stream_complete",
            "request_id": request_id,
            "label": label,
            "duration_ms": round(duration_ms, 2),
            "model": kwargs.get("model", "unknown"),
            "streaming": True,
        }

        logger.info("CCProxy streaming request completed", extra=log_data)
