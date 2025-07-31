"""Classification rules for request routing."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccproxy.config import CCProxyConfig


class ClassificationRule(ABC):
    """Abstract base class for classification rules.

    To create a custom classification rule:

    1. Inherit from ClassificationRule
    2. Implement the evaluate method
    3. Return True if the rule matches, False otherwise

    The rule can accept parameters in __init__ to configure its behavior.
    """

    @abstractmethod
    def evaluate(self, request: dict[str, Any], config: "CCProxyConfig") -> bool:
        """Evaluate the rule against the request.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            True if the rule matches, False otherwise
        """


class TokenCountRule(ClassificationRule):
    """Rule for classifying requests based on token count."""

    def __init__(self, threshold: int) -> None:
        """Initialize the rule with a threshold.

        Args:
            threshold: The token count threshold
        """
        self.threshold = threshold

    def evaluate(self, request: dict[str, Any], config: "CCProxyConfig") -> bool:
        """Evaluate if request has high token count based on threshold.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            True if token count exceeds threshold, False otherwise
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
        return token_count > self.threshold


class MatchModelRule(ClassificationRule):
    """Rule for classifying requests based on model name."""

    def __init__(self, model_name: str) -> None:
        """Initialize the rule with a model name to match.

        Args:
            model_name: The model name substring to match
        """
        self.model_name = model_name

    def evaluate(self, request: dict[str, Any], config: "CCProxyConfig") -> bool:
        """Evaluate if request matches the configured model name.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            True if model matches, False otherwise
        """
        model = request.get("model", "")
        return isinstance(model, str) and self.model_name in model


class ThinkingRule(ClassificationRule):
    """Rule for classifying requests with thinking field."""

    def evaluate(self, request: dict[str, Any], config: "CCProxyConfig") -> bool:
        """Evaluate if request has thinking field.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            True if request has thinking field, False otherwise
        """
        # Check top-level thinking field
        return "thinking" in request


class MatchToolRule(ClassificationRule):
    """Rule for classifying requests with specified tools."""

    def __init__(self, tool_name: str) -> None:
        """Initialize the rule with a tool name to match.

        Args:
            tool_name: The tool name substring to match
        """
        self.tool_name = tool_name.lower()

    def evaluate(self, request: dict[str, Any], config: "CCProxyConfig") -> bool:
        """Evaluate if request uses the specified tool.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            True if request has the specified tool, False otherwise
        """
        tools = request.get("tools", [])
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict):
                    # Check direct name field
                    name = tool.get("name", "")
                    if isinstance(name, str) and self.tool_name in name.lower():
                        return True

                    # Check function.name field (OpenAI format)
                    function = tool.get("function", {})
                    if isinstance(function, dict):
                        function_name = function.get("name", "")
                        if isinstance(function_name, str) and self.tool_name in function_name.lower():
                            return True
                elif isinstance(tool, str) and self.tool_name in tool.lower():
                    return True

        return False
