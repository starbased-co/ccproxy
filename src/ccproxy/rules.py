"""Classification rules for request routing."""

from typing import Any

from ccproxy.classifier import ClassificationRule, RoutingLabel
from ccproxy.config import CCProxyConfig


class TokenCountRule(ClassificationRule):
    """Rule for classifying requests based on token count."""

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
        """Evaluate if request has high token count based on threshold.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            TOKEN_COUNT if token count exceeds threshold, None otherwise
        """
        # Check various token count fields
        token_count = 0

        # Check messages token count
        messages = request.get("messages", [])
        if isinstance(messages, list):
            # Simple estimation: ~4 chars per token
            total_chars = 0
            for msg in messages:
                if isinstance(msg, dict):
                    # Handle message dict format
                    content = msg.get("content", "")
                    total_chars += len(str(content))
                else:
                    # Handle simple string messages
                    total_chars += len(str(msg))
            token_count = total_chars // 4

        # Check explicit token count fields
        token_count = max(
            token_count,
            request.get("token_count", 0) or 0,
            request.get("num_tokens", 0) or 0,
            request.get("input_tokens", 0) or 0,
        )

        # Check against threshold
        if token_count > config.token_count_threshold:
            return RoutingLabel.TOKEN_COUNT

        return None


class MatchModelRule(ClassificationRule):
    """Rule for classifying requests based on model name."""

    def __init__(self, model_name: str, label: RoutingLabel) -> None:
        """Initialize the rule with a model name to match.

        Args:
            model_name: The model name substring to match
            label: The routing label to return if matched
        """
        self.model_name = model_name
        self.label = label

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
        """Evaluate if request matches the configured model name.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            The configured label if model matches, None otherwise
        """
        model = request.get("model", "")
        if isinstance(model, str) and self.model_name in model:
            return self.label

        return None


class ThinkingRule(ClassificationRule):
    """Rule for classifying requests with thinking field."""

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
        """Evaluate if request has thinking field.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            THINK if request has thinking field, None otherwise
        """
        # Check top-level thinking field
        if "thinking" in request:
            return RoutingLabel.THINK

        return None


class MatchToolRule(ClassificationRule):
    """Rule for classifying requests with web search tools."""

    def __init__(self, tool_name: str) -> None:
        """Initialize the rule with a model name to match.

        Args:
            model_name: The model name substring to match
            label: The routing label to return if matched
        """
        self.tool_name: str = tool_name

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
        """Evaluate if request uses web search tools.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            WEB_SEARCH if request has web_search tool, None otherwise
        """
        tools = request.get("tools", [])
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict):
                    # Check direct name field
                    tool_name = tool.get("name", "")
                    if isinstance(tool_name, str) and "web_search" in tool_name.lower():
                        return RoutingLabel.WEB_SEARCH

                    # Check function.name field (OpenAI format)
                    function = tool.get("function", {})
                    if isinstance(function, dict):
                        function_name = function.get("name", "")
                        if isinstance(function_name, str) and "web_search" in function_name.lower():
                            return RoutingLabel.WEB_SEARCH
                elif isinstance(tool, str) and "web_search" in tool.lower():
                    return RoutingLabel.WEB_SEARCH

        return None
