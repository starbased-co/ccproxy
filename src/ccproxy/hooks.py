import logging
import uuid
from typing import Any

from ccproxy.classifier import RequestClassifier
from ccproxy.router import ModelRouter

# Set up structured logging
logger = logging.getLogger(__name__)


def classify_hook(data: dict[str, Any], user_api_key_dict: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    classifier = kwargs["classifier"]
    assert isinstance(classifier, RequestClassifier)
    if "metadata" not in data:
        data["metadata"] = {}

    # Store original model
    data["metadata"]["ccproxy_alias_model"] = data.get("model")

    # Classify the request
    data["metadata"]["ccproxy_label"] = classifier.classify(data)
    return data


def rewrite_model_hook(data: dict[str, Any], user_api_key_dict: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    router = kwargs["router"]
    assert isinstance(router, ModelRouter)

    label = data.get("metadata", {}).get("ccproxy_label", None)
    assert label is not None

    # Get model for label from router (includes fallback to 'default' label)
    model_config = router.get_model_for_label(label)

    if model_config is not None:
        routed_model = model_config.get("litellm_params", {}).get("model")
        assert routed_model is not None
        data["model"] = routed_model
        data["metadata"]["ccproxy_litellm_model"] = routed_model
        data["metadata"]["ccproxy_model_config"] = model_config
    else:
        # No model config found (not even default)
        # This should only happen if no 'default' model is configured
        raise ValueError(f"No model configured for label '{label}' and no 'default' model available as fallback")

    # Generate request ID if not present
    if "request_id" not in data["metadata"]:
        data["metadata"]["request_id"] = str(uuid.uuid4())
    return data


def forward_oauth_hook(data: dict[str, Any], user_api_key_dict: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    request = data.get("proxy_server_request")
    if request is None:
        # No proxy server request, skip OAuth forwarding
        return data

    headers = request.get("headers", {})
    user_agent = headers.get("user-agent", "")

    # Check if this is a claude-cli request and the routed model is going to Anthropic provider
    # Forward OAuth token only when the final destination is Anthropic's API directly
    # (not Vertex, Bedrock, or other providers hosting Anthropic models)
    metadata = data.get("metadata", {})
    is_anthropic_provider = False
    routed_model = metadata.get("ccproxy_litellm_model", "")
    model_config = metadata.get("ccproxy_model_config", {})
    litellm_params = model_config.get("litellm_params", {})

    api_base = litellm_params.get("api_base", "")
    custom_provider = litellm_params.get("custom_llm_provider", "")

    # Check if this is going to Anthropic's API directly
    if "anthropic.com" in api_base or custom_provider == "anthropic":
        is_anthropic_provider = True
    elif (
        not api_base
        and not custom_provider
        and (routed_model.startswith("anthropic/") or routed_model.startswith("claude"))
    ):
        # Default provider for anthropic/ prefix or claude models is Anthropic
        is_anthropic_provider = True

    if user_agent and "claude-cli" in user_agent and is_anthropic_provider:
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
                    "request_id": data["metadata"].get("request_id", None),
                },
            )

    return data
