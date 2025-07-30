"""Tests for request classifier module."""

from typing import Any
from unittest import mock

import pytest

from ccproxy.classifier import ClassificationRule, RequestClassifier, RoutingLabel
from ccproxy.config import CCProxyConfig, ConfigProvider


class TestRoutingLabel:
    """Tests for RoutingLabel enum."""

    def test_routing_labels(self) -> None:
        """Test that all expected routing labels are defined."""
        assert RoutingLabel.DEFAULT == "default"
        assert RoutingLabel.BACKGROUND == "background"
        assert RoutingLabel.THINK == "think"
        assert RoutingLabel.LARGE_CONTEXT == "large_context"
        assert RoutingLabel.WEB_SEARCH == "web_search"

    def test_routing_label_is_string(self) -> None:
        """Test that routing labels behave as strings."""
        assert isinstance(RoutingLabel.DEFAULT, str)
        assert str(RoutingLabel.DEFAULT) == "default"


class TestRequestClassifier:
    """Tests for RequestClassifier."""

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig(context_threshold=50000)

    @pytest.fixture
    def config_provider(self, config: CCProxyConfig) -> ConfigProvider:
        """Create a config provider with test config."""
        return ConfigProvider(config)

    @pytest.fixture
    def classifier(self, config_provider: ConfigProvider) -> RequestClassifier:
        """Create a classifier with test config."""
        return RequestClassifier(config_provider)

    def test_initialization(self, classifier: RequestClassifier) -> None:
        """Test classifier initialization."""
        assert classifier._config_provider is not None
        assert len(classifier._rules) == 4  # 4 default rules are set up

    def test_initialization_without_provider(self) -> None:
        """Test classifier initialization without config provider."""
        classifier = RequestClassifier()
        assert classifier._config_provider is not None

    def test_classify_default(self, classifier: RequestClassifier) -> None:
        """Test that classify returns DEFAULT when no rules match."""
        request = {"model": "gpt-4", "messages": []}
        assert classifier.classify(request) == RoutingLabel.DEFAULT

    def test_classify_with_pydantic_model(self, classifier: RequestClassifier) -> None:
        """Test classify with a pydantic-like model."""
        # Mock a pydantic model
        mock_model = mock.Mock()
        mock_model.model_dump.return_value = {"model": "gpt-4", "messages": []}

        result = classifier.classify(mock_model)
        assert result == RoutingLabel.DEFAULT
        mock_model.model_dump.assert_called_once()

    def test_add_rule(self, classifier: RequestClassifier) -> None:
        """Test adding a classification rule."""
        # Get initial rule count
        initial_count = len(classifier._rules)

        # Create a mock rule
        mock_rule = mock.Mock(spec=ClassificationRule)
        mock_rule.evaluate.return_value = RoutingLabel.THINK

        # Add the rule
        classifier.add_rule(mock_rule)
        assert len(classifier._rules) == initial_count + 1

        # Test classification with the rule
        request = {"model": "gpt-4", "messages": []}
        result = classifier.classify(request)

        assert result == RoutingLabel.THINK
        mock_rule.evaluate.assert_called_once()

    def test_multiple_rules_priority(self, classifier: RequestClassifier, config: CCProxyConfig) -> None:
        """Test that rules are evaluated in order."""
        # Create mock rules
        rule1 = mock.Mock(spec=ClassificationRule)
        rule1.evaluate.return_value = None  # Doesn't match

        rule2 = mock.Mock(spec=ClassificationRule)
        rule2.evaluate.return_value = RoutingLabel.BACKGROUND  # Matches

        rule3 = mock.Mock(spec=ClassificationRule)
        rule3.evaluate.return_value = RoutingLabel.THINK  # Also matches but shouldn't be reached

        # Add rules in order
        classifier.add_rule(rule1)
        classifier.add_rule(rule2)
        classifier.add_rule(rule3)

        # Classify
        request = {"model": "claude-3-haiku", "messages": []}
        result = classifier.classify(request)

        # Should return the first matching rule
        assert result == RoutingLabel.BACKGROUND

        # Verify evaluation order
        rule1.evaluate.assert_called_once_with(request, config)
        rule2.evaluate.assert_called_once_with(request, config)
        rule3.evaluate.assert_not_called()  # Should not be reached

    def test_clear_rules(self, classifier: RequestClassifier) -> None:
        """Test clearing all rules."""
        # Clear existing rules first
        classifier.clear_rules()
        assert len(classifier._rules) == 0

        # Add some rules
        mock_rule = mock.Mock(spec=ClassificationRule)
        classifier.add_rule(mock_rule)
        classifier.add_rule(mock_rule)

        assert len(classifier._rules) == 2

        # Clear rules
        classifier.clear_rules()
        assert len(classifier._rules) == 0

    def test_reset_rules(self, classifier: RequestClassifier) -> None:
        """Test resetting rules to default."""
        # Clear existing rules
        classifier.clear_rules()

        # Add a custom rule
        mock_rule = mock.Mock(spec=ClassificationRule)
        classifier.add_rule(mock_rule)
        assert len(classifier._rules) == 1

        # Reset rules
        classifier.reset_rules()

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
            def evaluate(self, request: dict[str, Any], config: CCProxyConfig) -> RoutingLabel | None:
                if request.get("test") == "value":
                    return RoutingLabel.THINK
                return None

        # Should be able to instantiate
        rule = TestRule()
        config = CCProxyConfig()

        # Test evaluation
        assert rule.evaluate({"test": "value"}, config) == RoutingLabel.THINK
        assert rule.evaluate({"test": "other"}, config) is None
