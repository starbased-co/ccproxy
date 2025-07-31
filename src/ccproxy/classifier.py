"""Request classification module for context-aware routing."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol

from ccproxy.config import CCProxyConfig, ConfigProvider


class RoutingLabel(str, Enum):
    """Routing labels for request classification."""

    DEFAULT = "default"
    BACKGROUND = "background"
    THINK = "think"
    TOKEN_COUNT = "token_count"  # noqa: S105
    WEB_SEARCH = "web_search"

    def __str__(self) -> str:
        """Return the string value of the label."""
        return self.value


class ClassificationRule(ABC):
    """Abstract base class for classification rules.

    To create a custom classification rule:

    1. Inherit from ClassificationRule
    2. Implement the evaluate method
    3. Return a RoutingLabel if the rule matches, None otherwise

    Example:
        >>> class CustomHeaderRule(ClassificationRule):
        ...     def evaluate(self, request, config):
        ...         headers = request.get("headers", {})
        ...         if headers.get("X-Priority") == "low":
        ...             return RoutingLabel.BACKGROUND
        ...         return None
        ...
        >>> classifier = RequestClassifier()
        >>> classifier.add_rule(CustomHeaderRule())
    """

    @abstractmethod
    def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
        """Evaluate the rule against the request.

        Args:
            request: The request to evaluate
            config: The current configuration

        Returns:
            The routing label if the rule matches, None otherwise
        """


class Classifier(Protocol):
    """Protocol for request classifiers."""

    def classify(self, request: dict[str, Any]) -> RoutingLabel:
        """Classify a request and return the appropriate routing label.

        Args:
            request: The request to classify

        Returns:
            The routing label for the request
        """


class RequestClassifier:
    """Main request classifier implementing rule-based classification.

    The classifier uses a rule-based system where rules are evaluated in
    the order they are added. The first matching rule determines the
    routing label.

    Extension Points:
    - Create custom rules by inheriting from ClassificationRule
    - Add rules dynamically using add_rule()
    - Replace default rules using clear_rules() then add_rule()
    - Reset to default rules using reset_rules()

    Example:
        >>> # Create a custom rule
        >>> class CustomAPIKeyRule(ClassificationRule):
        ...     def evaluate(self, request, config):
        ...         api_key = request.get("api_key", "")
        ...         if api_key.startswith("test_"):
        ...             return RoutingLabel.BACKGROUND
        ...         return None
        ...
        >>> # Use with classifier
        >>> classifier = RequestClassifier()
        >>> classifier.add_rule(CustomAPIKeyRule())
        >>>
        >>> # Or replace all rules
        >>> classifier.clear_rules()
        >>> classifier.add_rule(CustomAPIKeyRule())
        >>> classifier.add_rule(TokenCountRule())
    """

    def __init__(self, config_provider: ConfigProvider | None = None) -> None:
        """Initialize the request classifier.

        Args:
            config_provider: Optional config provider. If None, uses global config.
        """
        self._config_provider = config_provider or ConfigProvider()
        self._rules: list[ClassificationRule] = []
        self._setup_rules()

    def _setup_rules(self) -> None:
        """Set up classification rules in priority order.

        Priority order (from PRD):
        1. Token count (tokens > threshold) → token_count
        2. Model is claude-3-5-haiku → background
        3. Request has thinking field → think
        4. Tools contain web_search → web_search
        5. Default case → default (handled in classify method)
        """
        from ccproxy.rules import ModelNameRule, ThinkingRule, TokenCountRule, WebSearchRule

        # Clear any existing rules
        self.clear_rules()

        # Add rules in priority order
        self.add_rule(TokenCountRule())  # Priority 1: Token count
        self.add_rule(ModelNameRule("claude-3-5-haiku", RoutingLabel.BACKGROUND))  # Priority 2: Background models
        self.add_rule(ThinkingRule())  # Priority 3: Thinking requests
        self.add_rule(WebSearchRule())  # Priority 4: Web search tools

    def classify(self, request: dict[str, Any]) -> RoutingLabel:
        """Classify a request based on configured rules.

        Args:
            request: The request to classify. Can be a dict or will accept
                     pydantic models via dict conversion.

        Returns:
            The routing label for the request

        Note:
            Rules are evaluated in priority order. The first matching rule
            determines the routing label. If no rules match, DEFAULT is returned.
        """
        # Convert pydantic model to dict if needed
        if hasattr(request, "model_dump"):
            request = request.model_dump()

        config = self._config_provider.get()

        # Evaluate rules in priority order
        for rule in self._rules:
            label = rule.evaluate(request, config)
            if label is not None:
                return label

        # Default if no rules match
        return RoutingLabel.DEFAULT

    def add_rule(self, rule: ClassificationRule) -> None:
        """Add a classification rule.

        Args:
            rule: The rule to add

        Note:
            Rules are evaluated in the order they are added.
            For proper priority, use _setup_rules() to configure
            the standard rule set.
        """
        self._rules.append(rule)

    def clear_rules(self) -> None:
        """Clear all classification rules."""
        self._rules.clear()

    def reset_rules(self) -> None:
        """Reset rules to the default configuration."""
        self.clear_rules()
        self._setup_rules()
