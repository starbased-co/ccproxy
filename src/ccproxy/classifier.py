"""Request classification module for context-aware routing."""

import logging
from typing import Any

from ccproxy.config import get_config
from ccproxy.rules import ClassificationRule

logger = logging.getLogger(__name__)


class RequestClassifier:
    """Main request classifier implementing rule-based classification.

    The classifier uses a rule-based system where rules are evaluated in
    the order they are configured. The first matching rule determines the
    routing label.

    The rules are loaded from the CCProxyConfig which reads from ccproxy.yaml.
    Each rule in the configuration specifies:
    - label: The routing label to use if the rule matches
    - rule: The Python import path to the rule class
    - params: Optional parameters to pass to the rule constructor

    Example configuration in ccproxy.yaml:
        ccproxy:
          rules:
            - label: token_count
              rule: ccproxy.rules.TokenCountRule
              params:
                - threshold: 60000
            - label: background
              rule: ccproxy.rules.MatchModelRule
              params:
                - model_name: claude-3-5-haiku-20241022
    """

    def __init__(self) -> None:
        """Initialize the request classifier."""
        self._rules: list[tuple[str, ClassificationRule]] = []
        self._setup_rules()

    def _setup_rules(self) -> None:
        """Set up classification rules from configuration.

        Rules are loaded from the ccproxy.yaml configuration file.
        Each rule configuration specifies the label and rule class to use.
        """
        # Clear any existing rules
        self._clear_rules()

        # Get configuration
        config = get_config()

        # Load rules from configuration
        for rule_config in config.rules:
            try:
                # Create rule instance
                rule_instance = rule_config.create_instance()
                # Add rule with its label
                self.add_rule(rule_config.label, rule_instance)
            except (ImportError, TypeError, AttributeError) as e:
                # Log error but continue loading other rules
                if config.debug:
                    print(f"Failed to load rule {rule_config.rule_path}: {e}")

    def classify(self, request: Any) -> str:
        """Classify a request based on configured rules.

        Args:
            request: The request to classify. Can be a dict or will accept
                     pydantic models via dict conversion.

        Returns:
            The routing label for the request

        Note:
            Rules are evaluated in the order they are configured. The first matching rule
            determines the routing label. If no rules match, "default" is returned.
        """
        # Convert pydantic model to dict if needed
        try:
            if hasattr(request, "model_dump") and callable(getattr(request, "model_dump", None)):
                request = request.model_dump()
        except Exception as e:
            logger.warning(f"Failed to convert request to dict: {e}")
            # If conversion fails, try to use request as-is

        if not isinstance(request, dict):
            logger.error("Request is not a dict and could not be converted")
            return "default"

        config = get_config()

        # Evaluate rules in order
        for label, rule in self._rules:
            if rule.evaluate(request, config):
                return label

        # Default if no rules match
        return "default"

    def add_rule(self, label: str, rule: ClassificationRule) -> None:
        """Add a classification rule with its associated label.

        Args:
            label: The routing label to use if this rule matches
            rule: The rule to add

        Note:
            Rules are evaluated in the order they are added.
            For proper priority, use _setup_rules() to configure
            the standard rule set from ccproxy.yaml.
        """
        self._rules.append((label, rule))

    def _clear_rules(self) -> None:
        """Clear all classification rules."""
        self._rules.clear()
