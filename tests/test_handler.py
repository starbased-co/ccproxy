"""Tests for CCProxyHandler and routing function."""

import tempfile
from pathlib import Path

import pytest
import yaml

from ccproxy.config import CCProxyConfig, clear_config_instance, set_config_instance
from ccproxy.handler import CCProxyHandler, ccproxy_get_model
from ccproxy.router import clear_router


class TestCCProxyGetModel:
    """Tests for ccproxy_get_model routing function."""

    @pytest.fixture
    def config_files(self):
        """Create temporary ccproxy.yaml and litellm config files."""
        # Create litellm config
        litellm_data = {
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
                    "model_name": "token_count",
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
        }

        # Create ccproxy config
        ccproxy_data = {
            "ccproxy": {
                "debug": False,
                "rules": [
                    {
                        "label": "token_count",
                        "rule": "ccproxy.rules.TokenCountRule",
                        "params": [{"threshold": 60000}],
                    },
                    {
                        "label": "background",
                        "rule": "ccproxy.rules.MatchModelRule",
                        "params": [{"model_name": "claude-3-5-haiku-20241022"}],
                    },
                    {
                        "label": "think",
                        "rule": "ccproxy.rules.ThinkingRule",
                        "params": [],
                    },
                    {
                        "label": "web_search",
                        "rule": "ccproxy.rules.MatchToolRule",
                        "params": [{"tool_name": "web_search"}],
                    },
                ],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            yaml.dump(litellm_data, litellm_file)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            yaml.dump(ccproxy_data, ccproxy_file)
            ccproxy_path = Path(ccproxy_file.name)

        yield ccproxy_path, litellm_path

        # Cleanup
        litellm_path.unlink()
        ccproxy_path.unlink()

    def test_route_to_default(self, config_files):
        """Test routing simple request to default model."""
        ccproxy_path, litellm_path = config_files

        # Set up config
        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
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
            clear_router()

    def test_route_to_background(self, config_files):
        """Test routing haiku model to background."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
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
            clear_router()

    def test_route_to_think(self, config_files):
        """Test routing thinking request to think model - only works with top-level thinking field."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
        set_config_instance(config)

        try:
            # This should NOT route to think model (thinking tags in messages are ignored)
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "system", "content": "<thinking>Let me analyze this problem</thinking>"},
                    {"role": "user", "content": "Complex problem"},
                ],
            }

            model = ccproxy_get_model(request_data)
            assert model == "claude-3-5-sonnet-20241022"  # Should use default

            # This SHOULD route to think model (top-level thinking field)
            request_data_with_think = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Complex problem"}],
                "thinking": True,  # Top-level thinking field
            }

            model = ccproxy_get_model(request_data_with_think)
            assert model == "claude-3-5-opus-20250514"  # Should route to think
        finally:
            clear_config_instance()
            clear_router()

    def test_route_to_token_count(self, config_files):
        """Test routing large context to appropriate model."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
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
            clear_router()

    def test_route_to_web_search(self, config_files):
        """Test routing web search request."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
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
            clear_router()

    def test_priority_order(self, config_files):
        """Test that priority order is respected."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
        set_config_instance(config)

        try:
            # Large context + thinking field should route to token_count (higher priority)
            large_message = "a" * 15000
            request_data = {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": large_message} for _ in range(20)],
                "thinking": True,  # Top-level thinking field
            }

            model = ccproxy_get_model(request_data)
            assert model == "gemini-2.5-pro"  # token_count wins over thinking
        finally:
            clear_config_instance()
            clear_router()

    def test_fallback_to_original_model(self):
        """Test fallback when no routing label model is configured."""
        # Create config without "think" model - only has default
        litellm_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
            ],
        }

        ccproxy_data = {
            "ccproxy": {
                "debug": False,
                "rules": [
                    {
                        "label": "think",
                        "rule": "ccproxy.rules.ThinkingRule",
                        "params": [],
                    },
                ],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            yaml.dump(litellm_data, litellm_file)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            yaml.dump(ccproxy_data, ccproxy_file)
            ccproxy_path = Path(ccproxy_file.name)

        try:
            config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
            set_config_instance(config)

            # Request that would route to "think" but model not configured in model_list
            request_data = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Problem"}],
                "thinking": True,  # Top-level thinking field
            }

            model = ccproxy_get_model(request_data)
            # Since "think" label is not in model_list, it should fall back to original
            assert model == "gpt-4"  # Falls back to original
        finally:
            litellm_path.unlink()
            ccproxy_path.unlink()
            clear_config_instance()
            clear_router()

    def test_debug_logging(self, capsys):
        """Test debug logging output."""
        # Enable debug in config
        litellm_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
            ],
        }

        ccproxy_data = {
            "ccproxy": {
                "debug": True,
                "rules": [],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            yaml.dump(litellm_data, litellm_file)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            yaml.dump(ccproxy_data, ccproxy_file)
            ccproxy_path = Path(ccproxy_file.name)

        try:
            config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
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
            litellm_path.unlink()
            ccproxy_path.unlink()
            clear_config_instance()
            clear_router()


class TestCCProxyHandler:
    """Tests for CCProxyHandler class."""

    @pytest.fixture
    def handler(self, config_files):
        """Create handler with test config."""
        ccproxy_path, litellm_path = config_files

        config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
        set_config_instance(config)
        yield CCProxyHandler()
        clear_config_instance()
        clear_router()

    @pytest.fixture
    def config_files(self):
        """Create temporary ccproxy.yaml and litellm config files."""
        # Create litellm config
        litellm_data = {
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
        }

        # Create ccproxy config
        ccproxy_data = {
            "ccproxy": {
                "debug": False,
                "rules": [
                    {
                        "label": "background",
                        "rule": "ccproxy.rules.MatchModelRule",
                        "params": [{"model_name": "claude-3-5-haiku-20241022"}],
                    },
                ],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            yaml.dump(litellm_data, litellm_file)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            yaml.dump(ccproxy_data, ccproxy_file)
            ccproxy_path = Path(ccproxy_file.name)

        yield ccproxy_path, litellm_path

        # Cleanup
        litellm_path.unlink()
        ccproxy_path.unlink()

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

    async def test_handler_uses_config_threshold(self):
        """Test that handler uses context threshold from config."""
        # Create config with custom threshold
        litellm_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                    },
                },
                {
                    "model_name": "token_count",
                    "litellm_params": {
                        "model": "gemini-2.5-pro",
                    },
                },
            ],
        }

        ccproxy_data = {
            "ccproxy": {
                "debug": False,
                "rules": [
                    {
                        "label": "token_count",
                        "rule": "ccproxy.rules.TokenCountRule",
                        "params": [{"threshold": 10000}],  # Lower threshold
                    },
                ],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            yaml.dump(litellm_data, litellm_file)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            yaml.dump(ccproxy_data, ccproxy_file)
            ccproxy_path = Path(ccproxy_file.name)

        try:
            config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)
            set_config_instance(config)

            handler = CCProxyHandler()

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

            # Should route to token_count
            assert modified_data["model"] == "gemini-2.5-pro"
            assert modified_data["metadata"]["ccproxy_label"] == "token_count"

        finally:
            litellm_path.unlink()
            ccproxy_path.unlink()
            clear_config_instance()
            clear_router()
