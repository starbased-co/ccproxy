"""Tests demonstrating classifier extensibility."""

from ccproxy.classifier import ClassificationRule, RequestClassifier, RoutingLabel
from ccproxy.config import CCProxyConfig


class CustomHeaderRule(ClassificationRule):
    """Example custom rule that routes based on headers."""

    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        """Route to BACKGROUND if X-Priority header is 'low'."""
        headers = request.get("headers", {})
        if isinstance(headers, dict) and headers.get("X-Priority") == "low":
            return RoutingLabel.BACKGROUND
        return None


class CustomUserAgentRule(ClassificationRule):
    """Example rule that routes based on user agent."""

    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        """Route to BACKGROUND if user agent contains 'bot'."""
        headers = request.get("headers", {})
        user_agent = headers.get("User-Agent", "").lower()
        if "bot" in user_agent:
            return RoutingLabel.BACKGROUND
        return None


class CustomEnvironmentRule(ClassificationRule):
    """Example rule that uses config for decisions."""

    def __init__(self, env_key: str = "TEST_ENV"):
        """Initialize with environment key to check."""
        self.env_key = env_key

    def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
        """Route based on environment metadata in request."""
        metadata = request.get("metadata", {})
        env = metadata.get("environment", "")
        if env == self.env_key:
            return RoutingLabel.THINK
        return None


class TestClassifierExtensibility:
    """Test suite demonstrating classifier extensibility."""

    def test_add_custom_rule(self) -> None:
        """Test adding a custom rule to the classifier."""
        classifier = RequestClassifier()
        custom_rule = CustomHeaderRule()

        # Add custom rule
        classifier.add_rule(custom_rule)

        # Test that custom rule works
        request = {
            "model": "claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "headers": {"X-Priority": "low"},
        }

        label = classifier.classify(request)
        assert label == RoutingLabel.BACKGROUND

    def test_custom_rule_priority(self) -> None:
        """Test that custom rules respect order of addition."""
        classifier = RequestClassifier()

        # Clear default rules and add custom rules
        classifier.clear_rules()
        classifier.add_rule(CustomHeaderRule())  # Returns BACKGROUND
        classifier.add_rule(CustomUserAgentRule())  # Also returns BACKGROUND

        # Request matches both rules
        request = {
            "headers": {
                "X-Priority": "low",
                "User-Agent": "MyBot/1.0",
            },
        }

        # Should match first rule (CustomHeaderRule)
        label = classifier.classify(request)
        assert label == RoutingLabel.BACKGROUND

        # Now reverse the order
        classifier.clear_rules()
        classifier.add_rule(CustomUserAgentRule())
        classifier.add_rule(CustomHeaderRule())

        # Same request should still return BACKGROUND
        # (both rules return the same label)
        label = classifier.classify(request)
        assert label == RoutingLabel.BACKGROUND

    def test_custom_rule_with_config(self) -> None:
        """Test custom rule that uses configuration."""
        classifier = RequestClassifier()
        env_rule = CustomEnvironmentRule("staging")

        classifier.add_rule(env_rule)

        request = {
            "model": "claude-3-5-sonnet",
            "metadata": {"environment": "staging"},
        }

        label = classifier.classify(request)
        assert label == RoutingLabel.THINK

    def test_replace_all_rules(self) -> None:
        """Test completely replacing default rules with custom ones."""
        classifier = RequestClassifier()

        # Clear all default rules
        classifier.clear_rules()

        # Add only custom rules
        classifier.add_rule(CustomHeaderRule())
        classifier.add_rule(CustomUserAgentRule())

        # Test that default rules no longer apply
        # This would normally trigger TokenCountRule
        request = {
            "model": "claude-3-5-sonnet",
            "token_count": 100000,  # Would trigger token_count normally
        }

        label = classifier.classify(request)
        assert label == RoutingLabel.DEFAULT  # No rules match

        # But custom rules still work
        request["headers"] = {"X-Priority": "low"}
        label = classifier.classify(request)
        assert label == RoutingLabel.BACKGROUND

    def test_reset_to_default_rules(self) -> None:
        """Test resetting to default rules after customization."""
        classifier = RequestClassifier()

        # Add custom rule
        classifier.add_rule(CustomHeaderRule())

        # Clear and add only custom
        classifier.clear_rules()
        classifier.add_rule(CustomHeaderRule())

        # Verify default rules don't work
        request = {"token_count": 100000}
        label = classifier.classify(request)
        assert label == RoutingLabel.DEFAULT

        # Reset to defaults
        classifier.reset_rules()

        # Now default rules work again
        label = classifier.classify(request)
        assert label == RoutingLabel.TOKEN_COUNT

    def test_mixed_default_and_custom_rules(self) -> None:
        """Test using both default and custom rules together."""
        classifier = RequestClassifier()

        # Add custom rule on top of defaults
        classifier.add_rule(CustomEnvironmentRule("production"))

        # Test default rule (large context)
        request = {"token_count": 100000}
        label = classifier.classify(request)
        assert label == RoutingLabel.TOKEN_COUNT

        # Test custom rule
        request = {
            "model": "claude-3-5-sonnet",
            "metadata": {"environment": "production"},
        }
        label = classifier.classify(request)
        assert label == RoutingLabel.THINK

    def test_custom_rule_edge_cases(self) -> None:
        """Test edge cases with custom rules."""
        classifier = RequestClassifier()

        # Rule that always returns None
        class NeverMatchRule(ClassificationRule):
            def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
                return None

        # Rule that checks nested data
        class NestedDataRule(ClassificationRule):
            def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
                try:
                    nested = request.get("data", {}).get("nested", {}).get("value")
                    if nested == "special":
                        return RoutingLabel.WEB_SEARCH
                except (AttributeError, TypeError):
                    pass
                return None

        classifier.add_rule(NeverMatchRule())
        classifier.add_rule(NestedDataRule())

        # Test never-matching rule
        request = {"model": "any"}
        label = classifier.classify(request)
        assert label == RoutingLabel.DEFAULT

        # Test nested data rule
        request = {"data": {"nested": {"value": "special"}}}
        label = classifier.classify(request)
        assert label == RoutingLabel.WEB_SEARCH

    def test_stateful_custom_rule(self) -> None:
        """Test custom rule with internal state."""

        class CounterRule(ClassificationRule):
            """Rule that alternates between labels based on call count."""

            def __init__(self):
                self.count = 0

            def evaluate(self, request: dict, config: CCProxyConfig) -> RoutingLabel | None:
                self.count += 1
                if self.count % 2 == 0:
                    return RoutingLabel.BACKGROUND
                return None

        classifier = RequestClassifier()
        counter_rule = CounterRule()
        classifier.add_rule(counter_rule)

        request = {"model": "claude"}

        # First call - no match (count=1)
        label = classifier.classify(request)
        assert label == RoutingLabel.DEFAULT

        # Second call - match (count=2)
        label = classifier.classify(request)
        assert label == RoutingLabel.BACKGROUND

        # Third call - no match (count=3)
        label = classifier.classify(request)
        assert label == RoutingLabel.DEFAULT
