"""Tests for CCProxyHandler and routing function."""

import tempfile
from pathlib import Path

import pytest
import yaml

from ccproxy.config import CCProxyConfig, clear_config_instance, set_config_instance
from ccproxy.handler import CCProxyHandler, ccproxy_get_model


class TestCCProxyGetModel:
    """Tests for ccproxy_get_model routing function."""

    @pytest.fixture
    def litellm_config_file(self):
        """Create a temporary LiteLLM config file."""
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
                {
                    "model_name": "background",
                    "litellm_params": {
                        "model": "claude-3-5-haiku-20241022",
                    },
                },
                {
                    "model_name": "think",
                    "litellm_params": {
                        "model": "claude-3-5-opus-20250514",
                    },
                },
                {
                    "model_name": "large_context",
                    "litellm_params": {
                        "model": "gemini-2.5-pro",
                    },
                },
                {
                    "model_name": "web_search",
                    "litellm_params": {
                        "model": "perplexity/llama-3.1-sonar-large-128k-online",
                    },
                },
            ],
            "ccproxy_settings": {
                "context_threshold": 60000,
                "debug": False,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            yield Path(f.name)

        # Cleanup
        Path(f.name).unlink()

    def test_route_to_default(self, litellm_config_file):
        """Test routing simple request to default model."""
        # Set up config
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Hello"}],
            }

            model = ccproxy_get_model(request_data)
            assert model == "claude-3-5-sonnet-20241022"
        finally:
            clear_config_instance()

    def test_route_to_background(self, litellm_config_file):
        """Test routing haiku model to background."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            request_data = {
                "model": "claude-3-5-haiku-20241022",
                "messages": [{"role": "user", "content": "Format this code"}],
            }

            model = ccproxy_get_model(request_data)
            assert model == "claude-3-5-haiku-20241022"
        finally:
            clear_config_instance()

    def test_route_to_think(self, litellm_config_file):
        """Test routing thinking request to think model."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "system", "content": "<thinking>Let me analyze this problem</thinking>"},
                    {"role": "user", "content": "Complex problem"},
                ],
            }

            model = ccproxy_get_model(request_data)
            assert model == "claude-3-5-opus-20250514"
        finally:
            clear_config_instance()

    def test_route_to_large_context(self, litellm_config_file):
        """Test routing large context to appropriate model."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            # Create a request with >60k tokens
            large_message = "a" * 15000  # ~15k chars ≈ ~3.75k tokens, need multiple messages
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": large_message} for _ in range(20)],
            }

            model = ccproxy_get_model(request_data)
            assert model == "gemini-2.5-pro"
        finally:
            clear_config_instance()

    def test_route_to_web_search(self, litellm_config_file):
        """Test routing web search request."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Search for latest news"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Search the web",
                        },
                    },
                ],
            }

            model = ccproxy_get_model(request_data)
            assert model == "perplexity/llama-3.1-sonar-large-128k-online"
        finally:
            clear_config_instance()

    def test_priority_order(self, litellm_config_file):
        """Test that priority order is respected."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)

        try:
            # Large context + thinking should route to large_context (higher priority)
            large_message = "a" * 15000
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "system", "content": "<thinking>Analyzing</thinking>"},
                ]
                + [{"role": "user", "content": large_message} for _ in range(20)],
            }

            model = ccproxy_get_model(request_data)
            assert model == "gemini-2.5-pro"  # large_context wins
        finally:
            clear_config_instance()

    def test_fallback_to_original_model(self, litellm_config_file):
        """Test fallback when no routing label model is configured."""
        # Create config without some models
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
            ],
            "ccproxy_settings": {
                "context_threshold": 60000,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(config_path)
            set_config_instance(config)

            # Request that would route to "think" but model not configured
            request_data = {
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "<thinking>Analyzing</thinking>"},
                    {"role": "user", "content": "Problem"},
                ],
            }

            model = ccproxy_get_model(request_data)
            assert model == "gpt-4"  # Falls back to original
        finally:
            config_path.unlink()
            clear_config_instance()

    def test_debug_logging(self, litellm_config_file, capsys):
        """Test debug logging output."""
        # Enable debug in config
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
            ],
            "ccproxy_settings": {
                "context_threshold": 60000,
                "debug": True,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(config_path)
            set_config_instance(config)

            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Hello"}],
            }

            model = ccproxy_get_model(request_data)
            assert model == "claude-3-5-sonnet-20241022"

            # Check debug output
            captured = capsys.readouterr()
            assert "[ccproxy] Routed to claude-3-5-sonnet-20241022 (label: default)" in captured.out
        finally:
            config_path.unlink()
            clear_config_instance()


class TestCCProxyHandler:
    """Tests for CCProxyHandler class."""

    @pytest.fixture
    def handler(self, litellm_config_file):
        """Create handler with test config."""
        config = CCProxyConfig.from_litellm_config(litellm_config_file)
        set_config_instance(config)
        yield CCProxyHandler()
        clear_config_instance()

    @pytest.fixture
    def litellm_config_file(self):
        """Create a temporary LiteLLM config file."""
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
                {
                    "model_name": "background",
                    "litellm_params": {
                        "model": "claude-3-5-haiku-20241022",
                    },
                },
            ],
            "ccproxy_settings": {
                "context_threshold": 60000,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            yield Path(f.name)

        # Cleanup
        Path(f.name).unlink()

    async def test_async_pre_call_hook(self, handler):
        """Test async_pre_call_hook modifies request correctly."""
        request_data = {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        user_api_key_dict = {}

        # Call the hook
        modified_data = await handler.async_pre_call_hook(
            request_data,
            user_api_key_dict,
        )

        # Check model was routed
        assert modified_data["model"] == "claude-3-5-haiku-20241022"

        # Check metadata was added
        assert "metadata" in modified_data
        assert modified_data["metadata"]["ccproxy_label"] == "background"
        assert modified_data["metadata"]["ccproxy_original_model"] == "claude-3-5-haiku-20241022"

    async def test_async_pre_call_hook_preserves_existing_metadata(self, handler):
        """Test that existing metadata is preserved."""
        request_data = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "metadata": {
                "existing_key": "existing_value",
            },
        }
        user_api_key_dict = {}

        # Call the hook
        modified_data = await handler.async_pre_call_hook(
            request_data,
            user_api_key_dict,
        )

        # Check existing metadata preserved
        assert modified_data["metadata"]["existing_key"] == "existing_value"

        # Check new metadata added
        assert modified_data["metadata"]["ccproxy_label"] == "default"
        assert modified_data["metadata"]["ccproxy_original_model"] == "claude-3-5-sonnet-20241022"

    async def test_handler_uses_config_threshold(self, litellm_config_file):
        """Test that handler uses context threshold from config."""
        # Create config with custom threshold
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
                {
                    "model_name": "large_context",
                    "litellm_params": {
                        "model": "gemini-2.5-pro",
                    },
                },
            ],
            "ccproxy_settings": {
                "context_threshold": 10000,  # Lower threshold
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(config_path)
            set_config_instance(config)

            handler = CCProxyHandler()

            # Verify config threshold
            assert handler.config.context_threshold == 10000

            # Create request with >10k tokens (10k threshold * 4 chars/token = 40k+ chars)
            large_message = "a" * 45000  # ~11.25k tokens
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": large_message}],
            }
            user_api_key_dict = {}

            # Call the hook
            modified_data = await handler.async_pre_call_hook(
                request_data,
                user_api_key_dict,
            )

            # Should route to large_context
            assert modified_data["model"] == "gemini-2.5-pro"
            assert modified_data["metadata"]["ccproxy_label"] == "large_context"

        finally:
            config_path.unlink()
            clear_config_instance()
