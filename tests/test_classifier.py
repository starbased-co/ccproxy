"""Tests for request classifier module."""

from typing import Any
from unittest import mock

import pytest

from ccproxy.classifier import RequestClassifier
from ccproxy.config import CCProxyConfig, RuleConfig, clear_config_instance, set_config_instance
from ccproxy.rules import ClassificationRule


class TestRequestClassifier:
    """Tests for RequestClassifier."""

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        # Create config with test rules
        config = CCProxyConfig(debug=True)
        config.rules = [
            RuleConfig("token_count", "ccproxy.rules.TokenCountRule", [{"threshold": 50000}]),
            RuleConfig("background", "ccproxy.rules.MatchModelRule", [{"model_name": "claude-3-5-haiku"}]),
            RuleConfig("think", "ccproxy.rules.ThinkingRule", []),
            RuleConfig("web_search", "ccproxy.rules.MatchToolRule", [{"tool_name": "web_search"}]),
        ]
        return config

    @pytest.fixture
    def classifier(self, config: CCProxyConfig) -> RequestClassifier:
        """Create a classifier with test config."""
        # Set the test config as the global config
        clear_config_instance()
        set_config_instance(config)
        try:
            yield RequestClassifier()
        finally:
            clear_config_instance()

    def test_initialization(self, classifier: RequestClassifier) -> None:
        """Test classifier initialization."""
        assert len(classifier._rules) == 4  # 4 default rules are set up

    def test_initialization_without_provider(self) -> None:
        """Test classifier initialization without config provider."""
        clear_config_instance()
        try:
            classifier = RequestClassifier()
            assert classifier is not None
        finally:
            clear_config_instance()

    def test_classify_default(self, classifier: RequestClassifier) -> None:
        """Test that classify returns DEFAULT when no rules match."""
        request = {"model": "gpt-4", "messages": []}
        assert classifier.classify(request) == "default"

    def test_classify_with_pydantic_model(self, classifier: RequestClassifier) -> None:
        """Test classify with a pydantic-like model."""
        # Mock a pydantic model
        mock_model = mock.Mock()
        mock_model.model_dump.return_value = {"model": "gpt-4", "messages": []}

        result = classifier.classify(mock_model)
        assert result == "default"
        mock_model.model_dump.assert_called_once()

    def test_add_rule(self, classifier: RequestClassifier) -> None:
        """Test adding a classification rule."""
        # Get initial rule count
        initial_count = len(classifier._rules)

        # Create a mock rule
        mock_rule = mock.Mock(spec=ClassificationRule)
        mock_rule.evaluate.return_value = True

        # Add the rule with label
        classifier.add_rule("think", mock_rule)
        assert len(classifier._rules) == initial_count + 1

        # Test classification with the rule
        request = {"model": "gpt-4", "messages": []}
        result = classifier.classify(request)

        assert result == "think"
        mock_rule.evaluate.assert_called_once()

    def test_multiple_rules_priority(self, classifier: RequestClassifier, config: CCProxyConfig) -> None:
        """Test that rules are evaluated in order."""
        # Create mock rules
        rule1 = mock.Mock(spec=ClassificationRule)
        rule1.evaluate.return_value = False  # Doesn't match

        rule2 = mock.Mock(spec=ClassificationRule)
        rule2.evaluate.return_value = True  # Matches

        rule3 = mock.Mock(spec=ClassificationRule)
        rule3.evaluate.return_value = True  # Also matches but shouldn't be reached

        # Add rules in order with labels
        classifier.add_rule("token_count", rule1)
        classifier.add_rule("background", rule2)
        classifier.add_rule("think", rule3)

        # Classify
        request = {"model": "claude-3-haiku", "messages": []}
        result = classifier.classify(request)

        # Should return the first matching rule
        assert result == "background"

        # Verify evaluation order
        rule1.evaluate.assert_called_once_with(request, config)
        rule2.evaluate.assert_called_once_with(request, config)
        rule3.evaluate.assert_not_called()  # Should not be reached

    def test_clear_rules(self, classifier: RequestClassifier) -> None:
        """Test clearing all rules."""
        # Clear existing rules first
        classifier._clear_rules()
        assert len(classifier._rules) == 0

        # Add some rules
        mock_rule = mock.Mock(spec=ClassificationRule)
        classifier.add_rule("test1", mock_rule)
        classifier.add_rule("test2", mock_rule)

        assert len(classifier._rules) == 2

        # Clear rules
        classifier._clear_rules()
        assert len(classifier._rules) == 0

    def test_setup_rules(self, classifier: RequestClassifier) -> None:
        """Test setting up rules from config."""
        # Clear existing rules
        classifier._clear_rules()

        # Add a custom rule
        mock_rule = mock.Mock(spec=ClassificationRule)
        classifier.add_rule("custom", mock_rule)
        assert len(classifier._rules) == 1

        # Setup rules from config
        classifier._setup_rules()

        # Should have cleared custom rules and set up defaults
        assert len(classifier._rules) == 4  # Back to 4 default rules


class TestClassificationRuleProtocol:
    """Tests for ClassificationRule abstract base class."""

    def test_cannot_instantiate_abstract_rule(self) -> None:
        """Test that ClassificationRule cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ClassificationRule()  # type: ignore[abstract]

    def test_concrete_rule_implementation(self) -> None:
        """Test implementing a concrete classification rule."""

        class TestRule(ClassificationRule):
            def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> bool:
                return request.get("test") == "value"

        # Should be able to instantiate
        rule = TestRule()
        config = CCProxyConfig()

        # Test evaluation
        assert rule.evaluate({"test": "value"}, config) is True
        assert rule.evaluate({"test": "other"}, config) is False
