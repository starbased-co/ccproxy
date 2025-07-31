"""Example custom rule for ccproxy.

This file demonstrates how to create custom classification rules for ccproxy.
Copy this template and modify it to create your own rules.

To use this rule:
1. Copy this file to your project
2. Add it to your ccproxy.yaml configuration:

ccproxy:
  rules:
    - label: high_priority
      rule: myproject.rules.PriorityUserRule
      params:
        - priority_users: ["admin@example.com", "vip@example.com"]
        - priority_keywords: ["urgent", "critical", "emergency"]

3. Ensure you have a model configured in config.yaml with model_name: high_priority
"""

from typing import Any

from ccproxy.config import CCProxyConfig
from ccproxy.rules import ClassificationRule


class PriorityUserRule(ClassificationRule):
    """Routes requests from priority users or containing priority keywords.

    This example rule demonstrates:
    - Constructor with multiple parameters
    - Accessing request metadata (user information)
    - Checking message content for keywords
    - Proper type hints and documentation
    """

    def __init__(
        self,
        priority_users: list[str] | None = None,
        priority_keywords: list[str] | None = None,
    ) -> None:
        """Initialize the priority user rule.

        Args:
            priority_users: List of email addresses that should be prioritized
            priority_keywords: List of keywords that trigger priority routing
        """
        self.priority_users = set(priority_users or [])
        self.priority_keywords = [kw.lower() for kw in (priority_keywords or [])]

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        """Check if request is from a priority user or contains priority keywords.

        Args:
            request: The incoming request data containing:
                - metadata: Dict with user information
                - messages: List of message dicts with content
                - Other LiteLLM request fields
            config: The ccproxy configuration instance

        Returns:
            True if this is a priority request, False otherwise
        """
        # Check if request is from a priority user
        metadata = request.get("metadata", {})
        user_email = metadata.get("user_email", "")

        if user_email in self.priority_users:
            return True

        # Check if any messages contain priority keywords
        messages = request.get("messages", [])
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content", "").lower()
                if any(keyword in content for keyword in self.priority_keywords):
                    return True

        return False


class TimeBasedRule(ClassificationRule):
    """Routes requests based on time of day.

    This example shows how to use external dependencies and
    implement time-based routing logic.
    """

    def __init__(
        self,
        start_hour: int = 9,
        end_hour: int = 17,
        timezone: str = "UTC",
    ) -> None:
        """Initialize the time-based rule.

        Args:
            start_hour: Hour to start using this route (0-23)
            end_hour: Hour to stop using this route (0-23)
            timezone: Timezone name (e.g., "US/Eastern", "UTC")
        """
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.timezone = timezone

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        """Check if current time is within the specified range.

        Args:
            request: The incoming request data
            config: The ccproxy configuration instance

        Returns:
            True if current time is within range, False otherwise
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Get current time in specified timezone
        try:
            tz = ZoneInfo(self.timezone)
            current_time = datetime.now(tz)
            current_hour = current_time.hour

            # Handle ranges that cross midnight
            if self.start_hour <= self.end_hour:
                return self.start_hour <= current_hour < self.end_hour
            else:
                # Range like 22:00 to 02:00
                return current_hour >= self.start_hour or current_hour < self.end_hour

        except Exception:
            # If timezone is invalid or any error occurs, don't route
            return False


class ContentLengthRule(ClassificationRule):
    """Routes requests based on total content length across all messages.

    This example demonstrates:
    - Aggregating data across multiple messages
    - Different parameter styles (single value vs dict)
    - Graceful error handling
    """

    def __init__(self, max_length: int) -> None:
        """Initialize the content length rule.

        Args:
            max_length: Maximum total content length before routing
        """
        self.max_length = max_length

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        """Check if total content length exceeds threshold.

        Args:
            request: The incoming request data
            config: The ccproxy configuration instance

        Returns:
            True if content length exceeds max_length, False otherwise
        """
        total_length = 0
        messages = request.get("messages", [])

        for message in messages:
            if isinstance(message, dict):
                content = message.get("content", "")
                if isinstance(content, str):
                    total_length += len(content)
                elif isinstance(content, list):
                    # Handle multi-modal content (text + images)
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            total_length += len(item.get("text", ""))

        return total_length > self.max_length


class ModelCapabilityRule(ClassificationRule):
    """Routes requests that require specific model capabilities.

    This advanced example shows:
    - Checking for specific request features
    - Using configuration data
    - Complex boolean logic
    """

    def __init__(
        self,
        require_vision: bool = False,
        require_function_calling: bool = False,
        require_streaming: bool = False,
    ) -> None:
        """Initialize the capability rule.

        Args:
            require_vision: Route if request contains images
            require_function_calling: Route if request uses tools/functions
            require_streaming: Route if request requires streaming
        """
        self.require_vision = require_vision
        self.require_function_calling = require_function_calling
        self.require_streaming = require_streaming

    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
        """Check if request requires specific capabilities.

        Args:
            request: The incoming request data
            config: The ccproxy configuration instance

        Returns:
            True if request matches required capabilities, False otherwise
        """
        # Check for vision requirements
        if self.require_vision:
            messages = request.get("messages", [])
            for message in messages:
                if isinstance(message, dict):
                    content = message.get("content", "")
                    # Check for multi-modal content
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "image_url":
                                return True

        # Check for function calling
        if self.require_function_calling and (request.get("tools") or request.get("functions")):
            return True

        # Check for streaming
        return bool(self.require_streaming and request.get("stream", False))


# Example of how to test your custom rules
if __name__ == "__main__":
    # Create a test rule
    rule = PriorityUserRule(
        priority_users=["admin@example.com"],
        priority_keywords=["urgent", "help"],
    )

    # Test with a priority user
    test_request = {
        "metadata": {"user_email": "admin@example.com"},
        "messages": [{"role": "user", "content": "Hello"}],
    }

    # This should return True
    print(f"Priority user test: {rule.evaluate(test_request, None)}")  # type: ignore

    # Test with priority keyword
    test_request2 = {
        "metadata": {"user_email": "regular@example.com"},
        "messages": [{"role": "user", "content": "This is urgent!"}],
    }

    # This should also return True
    print(f"Priority keyword test: {rule.evaluate(test_request2, None)}")  # type: ignore
