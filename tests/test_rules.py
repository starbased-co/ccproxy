"""Tests for classification rules."""

import pytest

from ccproxy.config import CCProxyConfig
from ccproxy.rules import MatchModelRule, MatchToolRule, ThinkingRule, TokenCountRule


class TestTokenCountRule:
    """Tests for TokenCountRule."""

    @pytest.fixture
    def rule(self) -> TokenCountRule:
        """Create a token count rule."""
        return TokenCountRule(threshold=1000)

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_no_tokens(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with no token information."""
        request = {"model": "gpt-4"}
        assert rule.evaluate(request, config) is False

    def test_token_count_below_threshold(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with token count below threshold."""
        request = {"token_count": 500}
        assert rule.evaluate(request, config) is False

    def test_token_count_above_threshold(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with token count above threshold."""
        request = {"token_count": 2000}
        assert rule.evaluate(request, config) is True

    def test_num_tokens_field(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with num_tokens field."""
        request = {"num_tokens": 1500}
        assert rule.evaluate(request, config) is True

    def test_input_tokens_field(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with input_tokens field."""
        request = {"input_tokens": 1200}
        assert rule.evaluate(request, config) is True

    def test_messages_estimation(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test token estimation from messages."""
        # Create messages with realistic text that tokenizes properly
        # ~800 tokens (below threshold of 1000)
        base_text = "The quick brown fox jumps over the lazy dog. " * 10
        short_message = base_text * 8  # ~800 tokens
        request = {"messages": [{"content": short_message}]}
        assert rule.evaluate(request, config) is False

        # Create messages with >1000 tokens
        longer_message = base_text * 15  # ~1501 tokens
        request = {"messages": [{"content": longer_message}]}
        assert rule.evaluate(request, config) is True

    def test_multiple_token_fields(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with multiple token fields (uses max)."""
        request = {
            "token_count": 500,
            "num_tokens": 1500,  # This is above threshold
            "input_tokens": 800,
        }
        assert rule.evaluate(request, config) is True

    def test_configurable_threshold(self) -> None:
        """Test that context threshold is configurable."""
        config = CCProxyConfig()

        # Test with low threshold
        low_rule = TokenCountRule(threshold=5000)
        request = {"token_count": 6000}
        assert low_rule.evaluate(request, config) is True

        # Same request with high threshold
        high_rule = TokenCountRule(threshold=10000)
        assert high_rule.evaluate(request, config) is False

        # Test threshold boundary
        boundary_rule = TokenCountRule(threshold=6000)
        assert boundary_rule.evaluate(request, config) is False  # Equal to threshold, not above


class TestModelMatchRule:
    """Tests for MatchModelRule."""

    @pytest.fixture
    def rule(self) -> MatchModelRule:
        """Create a model name rule for claude-3-5-haiku."""
        return MatchModelRule(model_name="claude-3-5-haiku")

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_claude_haiku_model(self, rule: MatchModelRule, config: CCProxyConfig) -> None:
        """Test request with claude-3-5-haiku model."""
        request = {"model": "claude-3-5-haiku"}
        assert rule.evaluate(request, config) is True

    def test_claude_haiku_with_suffix(self, rule: MatchModelRule, config: CCProxyConfig) -> None:
        """Test request with claude-3-5-haiku variant."""
        request = {"model": "claude-3-5-haiku-20241022"}
        assert rule.evaluate(request, config) is True

    def test_other_models(self, rule: MatchModelRule, config: CCProxyConfig) -> None:
        """Test request with other models."""
        models = ["gpt-4", "claude-3-opus", "claude-3-sonnet", "gpt-3.5-turbo"]
        for model in models:
            request = {"model": model}
            assert rule.evaluate(request, config) is False

    def test_no_model_field(self, rule: MatchModelRule, config: CCProxyConfig) -> None:
        """Test request without model field."""
        request = {"messages": []}
        assert rule.evaluate(request, config) is False

    def test_non_string_model(self, rule: MatchModelRule, config: CCProxyConfig) -> None:
        """Test request with non-string model field."""
        request = {"model": 123}
        assert rule.evaluate(request, config) is False


class TestThinkingRule:
    """Tests for ThinkingRule."""

    @pytest.fixture
    def rule(self) -> ThinkingRule:
        """Create a thinking rule."""
        return ThinkingRule()

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_with_thinking_field(self, rule: ThinkingRule, config: CCProxyConfig) -> None:
        """Test request with thinking field."""
        request = {"thinking": True}
        assert rule.evaluate(request, config) is True

    def test_thinking_field_any_value(self, rule: ThinkingRule, config: CCProxyConfig) -> None:
        """Test that any thinking field value triggers the rule."""
        test_values = [False, None, "", "enabled", 0, []]
        for value in test_values:
            request = {"thinking": value}
            assert rule.evaluate(request, config) is True

    def test_without_thinking_field(self, rule: ThinkingRule, config: CCProxyConfig) -> None:
        """Test request without thinking field."""
        request = {"model": "gpt-4", "messages": []}
        assert rule.evaluate(request, config) is False


class TestMatchToolRule:
    """Tests for MatchToolRule."""

    @pytest.fixture
    def rule(self) -> MatchToolRule:
        """Create a web search rule."""
        return MatchToolRule(tool_name="web_search")

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_web_search_tool_dict(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request with web_search tool as dict."""
        request = {"tools": [{"name": "web_search", "description": "Search the web"}]}
        assert rule.evaluate(request, config) is True

    def test_web_search_tool_string(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request with web_search tool as string."""
        request = {"tools": ["web_search"]}
        assert rule.evaluate(request, config) is True

    def test_web_search_case_insensitive(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test that web_search matching is case insensitive."""
        variations = ["Web_Search", "WEB_SEARCH", "web_SEARCH"]
        for variation in variations:
            request = {"tools": [{"name": variation}]}
            assert rule.evaluate(request, config) is True

    def test_web_search_partial_match(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test partial matches for web_search."""
        request = {"tools": [{"name": "advanced_web_search_tool"}]}
        assert rule.evaluate(request, config) is True

    def test_no_web_search_tool(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request without web_search tool."""
        request = {"tools": [{"name": "calculator"}, {"name": "code_interpreter"}]}
        assert rule.evaluate(request, config) is False

    def test_no_tools_field(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request without tools field."""
        request = {"model": "gpt-4"}
        assert rule.evaluate(request, config) is False

    def test_empty_tools_list(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request with empty tools list."""
        request = {"tools": []}
        assert rule.evaluate(request, config) is False

    def test_mixed_tool_types(self, rule: MatchToolRule, config: CCProxyConfig) -> None:
        """Test request with mixed tool types."""
        request = {
            "tools": [
                "calculator",
                {"name": "code_interpreter"},
                "web_search",  # This should match
                {"name": "image_generator"},
            ]
        }
        assert rule.evaluate(request, config) is True


class TestParameterizedModelNameRule:
    """Tests for parameterized MatchModelRule."""

    def test_custom_model_routing(self) -> None:
        """Test creating MatchModelRule with custom parameters."""
        config = CCProxyConfig()

        # Test with GPT-4o-mini rule
        rule = MatchModelRule(model_name="gpt-4o-mini")
        request = {"model": "gpt-4o-mini"}
        assert rule.evaluate(request, config) is True

        # Test non-matching
        request = {"model": "gpt-4"}
        assert rule.evaluate(request, config) is False

    def test_multiple_model_rules(self) -> None:
        """Test using multiple MatchModelRule instances."""
        config = CCProxyConfig()

        # Create rules for different models
        gpt_rule = MatchModelRule(model_name="gpt-4o-mini")
        custom_rule = MatchModelRule(model_name="my-fast-model")
        reasoning_rule = MatchModelRule(model_name="reasoning-v2")

        # Test each rule
        assert gpt_rule.evaluate({"model": "gpt-4o-mini"}, config) is True
        assert custom_rule.evaluate({"model": "my-fast-model"}, config) is True
        assert reasoning_rule.evaluate({"model": "reasoning-v2"}, config) is True

        # Test non-matching
        assert gpt_rule.evaluate({"model": "claude"}, config) is False
        assert custom_rule.evaluate({"model": "gpt-4"}, config) is False
        assert reasoning_rule.evaluate({"model": "fast-model"}, config) is False
