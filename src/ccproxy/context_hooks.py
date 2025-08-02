"""Context preservation hooks for CCProxy."""

import logging
from pathlib import Path
from typing import Any

from ccproxy.claude_integration import ClaudeCodeReader, ClaudeProjectLocator
from ccproxy.config import get_config
from ccproxy.context_manager import ContextManager
from ccproxy.provider_metadata import ProviderMetadataStore

logger = logging.getLogger(__name__)

# Global context manager instance
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager | None:
    """Get or create the global context manager instance."""
    global _context_manager

    if _context_manager is None:
        try:
            # Initialize components
            locator = ClaudeProjectLocator()
            reader = ClaudeCodeReader()
            store = ProviderMetadataStore(base_path=Path.home() / ".ccproxy")

            _context_manager = ContextManager(locator=locator, reader=reader, store=store)
            logger.info("Context manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize context manager: {e}")
            return None

    return _context_manager


async def context_injection_hook(
    data: dict[str, Any], user_api_key_dict: dict[str, Any], **kwargs: Any
) -> dict[str, Any]:
    """
    Pre-call hook to inject conversation context from Claude Code.

    This hook:
    1. Checks if context preservation is enabled
    2. Extracts session/chat ID from headers
    3. Gets conversation history from Claude Code
    4. Prepends context messages to the request

    Args:
        data: Request data dictionary
        user_api_key_dict: User API key information
        **kwargs: Additional arguments from LiteLLM

    Returns:
        Modified request data with injected context
    """
    config = get_config()

    # Check if context preservation is enabled
    context_config = config.context if hasattr(config, "context") else None
    if not context_config or not context_config.get("enabled", False):
        return data

    try:
        # Get context manager
        context_manager = get_context_manager()
        if not context_manager:
            logger.warning("Context manager not available")
            return data

        # Extract chat ID from headers if available
        # This would come from X-Chat-Id header in Claude Code requests
        chat_id = None
        request = data.get("proxy_server_request")
        if request:
            headers = request.get("headers", {})
            chat_id = headers.get("x-chat-id") or headers.get("X-Chat-Id")

        # Get current working directory
        # Try to get from request metadata or fall back to process cwd
        cwd = Path.cwd()
        if request:
            # Claude Code might send cwd in headers or metadata
            cwd_str = headers.get("x-cwd") or headers.get("X-Cwd")
            if cwd_str:
                cwd = Path(cwd_str)

        # Extract session ID from metadata.user_id if available
        # Claude Code embeds session ID in the format:
        # user_<hash>_account_<uuid>_session_<session-id>
        session_id = None
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id", "")
        if user_id and "_session_" in user_id:
            # Extract session ID from the user_id string
            parts = user_id.split("_session_")
            if len(parts) == 2:
                session_id = parts[1]
                logger.debug(f"Extracted session ID from metadata: {session_id}")

        # Get conversation context
        # Pass session_id if extracted from metadata
        context_messages = await context_manager.get_context(cwd, chat_id, session_id)

        if context_messages:
            # Convert Message objects to dict format expected by LiteLLM
            context_dicts = []
            for msg in context_messages:
                msg_dict = {"role": msg.role, "content": msg.content}
                # Include model info if present and it's an assistant message
                if msg.role == "assistant" and msg.model:
                    msg_dict["model"] = msg.model
                context_dicts.append(msg_dict)

            # Get current messages
            current_messages = data.get("messages", [])

            # Prepend context to current messages
            data["messages"] = context_dicts + current_messages

            # Store session ID in metadata for later use
            if context_messages and hasattr(context_messages[0], "session_id"):
                if "metadata" not in data:
                    data["metadata"] = {}
                data["metadata"]["claude_session_id"] = context_messages[0].session_id

            logger.info(f"Injected {len(context_dicts)} context messages (total messages: {len(data['messages'])})")

    except Exception as e:
        logger.error(f"Error in context injection hook: {e}", exc_info=True)
        # Continue without context on error

    return data


async def context_recording_hook(data: dict[str, Any], response_obj: Any, **kwargs: Any) -> None:
    """
    Post-call success hook to record routing decisions.

    This hook:
    1. Extracts session ID from metadata
    2. Extracts provider and model info from response
    3. Records the routing decision for future reference

    Args:
        data: Original request data
        response_obj: LiteLLM response object
        **kwargs: Additional arguments
    """
    config = get_config()

    # Check if context preservation is enabled
    context_config = config.context if hasattr(config, "context") else None
    if not context_config or not context_config.get("enabled", False):
        return

    try:
        # Get context manager
        context_manager = get_context_manager()
        if not context_manager:
            return

        # Extract session ID from metadata
        metadata = data.get("metadata", {})
        session_id = metadata.get("claude_session_id")

        if not session_id:
            logger.debug("No session ID found, skipping routing record")
            return

        # Extract provider and model info from response
        # LiteLLM includes this in response metadata
        provider = "unknown"
        model = metadata.get("ccproxy_litellm_model", "unknown")

        # Try to extract provider from model string or response
        if hasattr(response_obj, "_hidden_params") and response_obj._hidden_params:
            provider = response_obj._hidden_params.get("custom_llm_provider", "unknown")
        elif "/" in model:
            # Extract provider from model format like "anthropic/claude-3"
            provider = model.split("/")[0]

        # Get other metadata
        request_id = metadata.get("request_id", "")
        selected_by_rule = metadata.get("ccproxy_label", "")

        # Additional metadata to record
        routing_metadata = {
            "original_model": metadata.get("ccproxy_alias_model"),
            "routed_model": model,
            "label": selected_by_rule,
        }

        # Record the decision
        await context_manager.record_decision(
            session_id=session_id,
            provider=provider,
            model=model,
            request_id=request_id,
            selected_by_rule=selected_by_rule,
            metadata=routing_metadata,
        )

        logger.debug(
            f"Recorded routing decision for session {session_id[:8]}...: {provider}/{model} (rule: {selected_by_rule})"
        )

    except Exception as e:
        logger.error(f"Error in context recording hook: {e}", exc_info=True)
        # Continue on error - don't fail the request


def cleanup_context_manager() -> None:
    """Clean up the global context manager instance."""
    global _context_manager

    if _context_manager:
        _context_manager.cleanup()
        _context_manager = None
        logger.info("Context manager cleaned up")
