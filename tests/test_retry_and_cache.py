"""Tests for retry configuration and global tokenizer cache."""

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from ccproxy.config import CCProxyConfig
from ccproxy.hooks import calculate_retry_delay, configure_retry
from ccproxy.rules import TokenCountRule, _tokenizer_cache, _tokenizer_cache_lock


class TestGlobalTokenizerCache:
    """Tests for global tokenizer cache in rules.py."""

    def test_tokenizer_cache_is_global(self) -> None:
        """Test that tokenizer cache is shared between instances."""
        rule1 = TokenCountRule(threshold=1000)
        rule2 = TokenCountRule(threshold=2000)

        # Both should use the same global cache
        # Access the global cache through one rule
        tok1 = rule1._get_tokenizer("claude-3")

        # Clear instance doesn't affect cache
        # The second rule should get the cached tokenizer
        tok2 = rule2._get_tokenizer("claude-3")

        assert tok1 is tok2  # Same object from cache

    def test_tokenizer_cache_thread_safe(self) -> None:
        """Test that cache operations are thread-safe."""
        import threading

        rule = TokenCountRule(threshold=1000)
        results = []

        def get_tokenizer():
            tok = rule._get_tokenizer("gemini-test")
            results.append(tok)

        threads = [threading.Thread(target=get_tokenizer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should get the same tokenizer
        assert len(set(id(r) for r in results if r)) <= 1


class TestRetryConfiguration:
    """Tests for request retry configuration."""

    def test_retry_config_defaults(self) -> None:
        """Test default retry configuration values."""
        config = CCProxyConfig()

        assert config.retry_enabled is False
        assert config.retry_max_attempts == 3
        assert config.retry_initial_delay == 1.0
        assert config.retry_max_delay == 60.0
        assert config.retry_multiplier == 2.0
        assert config.retry_fallback_model is None

    def test_retry_config_from_yaml(self) -> None:
        """Test loading retry configuration from YAML."""
        yaml_content = """
ccproxy:
  retry_enabled: true
  retry_max_attempts: 5
  retry_initial_delay: 2.0
  retry_max_delay: 120.0
  retry_multiplier: 3.0
  retry_fallback_model: gpt-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)

            assert config.retry_enabled is True
            assert config.retry_max_attempts == 5
            assert config.retry_initial_delay == 2.0
            assert config.retry_max_delay == 120.0
            assert config.retry_multiplier == 3.0
            assert config.retry_fallback_model == "gpt-4"

            config.stop_background_refresh()
        finally:
            yaml_path.unlink()


class TestConfigureRetryHook:
    """Tests for the configure_retry hook."""

    def test_configure_retry_when_disabled(self) -> None:
        """Test that hook does nothing when retry is disabled."""
        config = CCProxyConfig(retry_enabled=False)
        data = {"model": "test", "messages": []}

        result = configure_retry(data, {}, config_override=config)

        assert "num_retries" not in result
        assert "fallbacks" not in result

    def test_configure_retry_when_enabled(self) -> None:
        """Test that hook configures retry settings."""
        config = CCProxyConfig(
            retry_enabled=True,
            retry_max_attempts=5,
            retry_initial_delay=2.0,
        )
        data = {"model": "test", "messages": []}

        result = configure_retry(data, {}, config_override=config)

        assert result["num_retries"] == 5
        assert result["retry_after"] == 2.0
        assert result["metadata"]["ccproxy_retry_enabled"] is True

    def test_configure_retry_with_fallback(self) -> None:
        """Test that fallback model is configured."""
        config = CCProxyConfig(
            retry_enabled=True,
            retry_fallback_model="gpt-4-fallback",
        )
        data = {"model": "test", "messages": []}

        result = configure_retry(data, {}, config_override=config)

        assert {"model": "gpt-4-fallback"} in result["fallbacks"]
        assert result["metadata"]["ccproxy_retry_fallback"] == "gpt-4-fallback"


class TestCalculateRetryDelay:
    """Tests for exponential backoff calculation."""

    def test_first_attempt_delay(self) -> None:
        """Test delay for first retry attempt."""
        delay = calculate_retry_delay(attempt=1, initial_delay=1.0)
        assert delay == 1.0

    def test_exponential_backoff(self) -> None:
        """Test exponential increase in delay."""
        assert calculate_retry_delay(1, 1.0, 60.0, 2.0) == 1.0
        assert calculate_retry_delay(2, 1.0, 60.0, 2.0) == 2.0
        assert calculate_retry_delay(3, 1.0, 60.0, 2.0) == 4.0
        assert calculate_retry_delay(4, 1.0, 60.0, 2.0) == 8.0

    def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        delay = calculate_retry_delay(attempt=10, initial_delay=1.0, max_delay=60.0)
        assert delay == 60.0  # Capped

    def test_custom_multiplier(self) -> None:
        """Test custom multiplier."""
        delay = calculate_retry_delay(attempt=2, initial_delay=1.0, multiplier=3.0)
        assert delay == 3.0
