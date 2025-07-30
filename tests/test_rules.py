"""Tests for classification rules."""

import pytest

from ccproxy.classifier import RoutingLabel
from ccproxy.config import CCProxyConfig
from ccproxy.rules import ModelNameRule, ThinkingRule, TokenCountRule, WebSearchRule


class TestTokenCountRule:
    """Tests for TokenCountRule."""

    @pytest.fixture
    def rule(self) -> TokenCountRule:
        """Create a token count rule."""
        return TokenCountRule()

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig(context_threshold=1000)

    def test_no_tokens(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with no token information."""
        request = {"model": "gpt-4"}
        assert rule.evaluate(request, config) is None

    def test_token_count_below_threshold(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with token count below threshold."""
        request = {"token_count": 500}
        assert rule.evaluate(request, config) is None

    def test_token_count_above_threshold(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with token count above threshold."""
        request = {"token_count": 2000}
        assert rule.evaluate(request, config) == RoutingLabel.LARGE_CONTEXT

    def test_num_tokens_field(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with num_tokens field."""
        request = {"num_tokens": 1500}
        assert rule.evaluate(request, config) == RoutingLabel.LARGE_CONTEXT

    def test_input_tokens_field(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with input_tokens field."""
        request = {"input_tokens": 1200}
        assert rule.evaluate(request, config) == RoutingLabel.LARGE_CONTEXT

    def test_messages_estimation(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test token estimation from messages."""
        # Create messages with ~4000 characters (estimated ~1000 tokens)
        long_message = "x" * 4000
        request = {"messages": [{"content": long_message}]}
        assert rule.evaluate(request, config) is None

        # Create messages with >4000 characters (estimated >1000 tokens)
        longer_message = "x" * 5000
        request = {"messages": [{"content": longer_message}]}
        assert rule.evaluate(request, config) == RoutingLabel.LARGE_CONTEXT

    def test_multiple_token_fields(self, rule: TokenCountRule, config: CCProxyConfig) -> None:
        """Test request with multiple token fields (uses max)."""
        request = {
            "token_count": 500,
            "num_tokens": 1500,  # This is above threshold
            "input_tokens": 800,
        }
        assert rule.evaluate(request, config) == RoutingLabel.LARGE_CONTEXT


class TestModelNameRule:
    """Tests for ModelNameRule."""

    @pytest.fixture
    def rule(self) -> ModelNameRule:
        """Create a model name rule."""
        return ModelNameRule()

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_claude_haiku_model(self, rule: ModelNameRule, config: CCProxyConfig) -> None:
        """Test request with claude-3-5-haiku model."""
        request = {"model": "claude-3-5-haiku"}
        assert rule.evaluate(request, config) == RoutingLabel.BACKGROUND

    def test_claude_haiku_with_suffix(self, rule: ModelNameRule, config: CCProxyConfig) -> None:
        """Test request with claude-3-5-haiku variant."""
        request = {"model": "claude-3-5-haiku-20241022"}
        assert rule.evaluate(request, config) == RoutingLabel.BACKGROUND

    def test_other_models(self, rule: ModelNameRule, config: CCProxyConfig) -> None:
        """Test request with other models."""
        models = ["gpt-4", "claude-3-opus", "claude-3-sonnet", "gpt-3.5-turbo"]
        for model in models:
            request = {"model": model}
            assert rule.evaluate(request, config) is None

    def test_no_model_field(self, rule: ModelNameRule, config: CCProxyConfig) -> None:
        """Test request without model field."""
        request = {"messages": []}
        assert rule.evaluate(request, config) is None

    def test_non_string_model(self, rule: ModelNameRule, config: CCProxyConfig) -> None:
        """Test request with non-string model field."""
        request = {"model": 123}
        assert rule.evaluate(request, config) is None


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
        assert rule.evaluate(request, config) == RoutingLabel.THINK

    def test_thinking_field_any_value(self, rule: ThinkingRule, config: CCProxyConfig) -> None:
        """Test that any thinking field value triggers the rule."""
        test_values = [False, None, "", "enabled", 0, []]
        for value in test_values:
            request = {"thinking": value}
            assert rule.evaluate(request, config) == RoutingLabel.THINK

    def test_without_thinking_field(self, rule: ThinkingRule, config: CCProxyConfig) -> None:
        """Test request without thinking field."""
        request = {"model": "gpt-4", "messages": []}
        assert rule.evaluate(request, config) is None


class TestWebSearchRule:
    """Tests for WebSearchRule."""

    @pytest.fixture
    def rule(self) -> WebSearchRule:
        """Create a web search rule."""
        return WebSearchRule()

    @pytest.fixture
    def config(self) -> CCProxyConfig:
        """Create a test configuration."""
        return CCProxyConfig()

    def test_web_search_tool_dict(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request with web_search tool as dict."""
        request = {"tools": [{"name": "web_search", "description": "Search the web"}]}
        assert rule.evaluate(request, config) == RoutingLabel.WEB_SEARCH

    def test_web_search_tool_string(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request with web_search tool as string."""
        request = {"tools": ["web_search"]}
        assert rule.evaluate(request, config) == RoutingLabel.WEB_SEARCH

    def test_web_search_case_insensitive(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test that web_search matching is case insensitive."""
        variations = ["Web_Search", "WEB_SEARCH", "web_SEARCH"]
        for variation in variations:
            request = {"tools": [{"name": variation}]}
            assert rule.evaluate(request, config) == RoutingLabel.WEB_SEARCH

    def test_web_search_partial_match(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test partial matches for web_search."""
        request = {"tools": [{"name": "advanced_web_search_tool"}]}
        assert rule.evaluate(request, config) == RoutingLabel.WEB_SEARCH

    def test_no_web_search_tool(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request without web_search tool."""
        request = {"tools": [{"name": "calculator"}, {"name": "code_interpreter"}]}
        assert rule.evaluate(request, config) is None

    def test_no_tools_field(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request without tools field."""
        request = {"model": "gpt-4"}
        assert rule.evaluate(request, config) is None

    def test_empty_tools_list(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request with empty tools list."""
        request = {"tools": []}
        assert rule.evaluate(request, config) is None

    def test_mixed_tool_types(self, rule: WebSearchRule, config: CCProxyConfig) -> None:
        """Test request with mixed tool types."""
        request = {
            "tools": [
                "calculator",
                {"name": "code_interpreter"},
                "web_search",  # This should match
                {"name": "image_generator"},
            ]
        }
        assert rule.evaluate(request, config) == RoutingLabel.WEB_SEARCH
