"""Tests for CCProxyHandler and routing function."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

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


class TestHandlerHookMethods:
    """Test suite for individual hook methods that haven't been covered."""

    @pytest.mark.asyncio
    async def test_log_success_hook(self, handler: CCProxyHandler) -> None:
        """Test async_log_success_hook method."""
        kwargs = {
            "litellm_params": {},
            "start_time": 1234567890,
            "end_time": 1234567900,
            "cache_hit": False,
        }
        response_obj = Mock(model="test-model", usage=Mock(completion_tokens=10, prompt_tokens=20, total_tokens=30))

        # Should not raise any exceptions
        await handler.async_log_success_hook(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_log_failure_hook(self, handler: CCProxyHandler) -> None:
        """Test async_log_failure_hook method."""
        kwargs = {
            "litellm_params": {},
            "start_time": 1234567890,
            "end_time": 1234567900,
        }
        response_obj = Mock()

        # Should not raise any exceptions
        await handler.async_log_failure_hook(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_logging_hook_with_completion(self, handler: CCProxyHandler) -> None:
        """Test async_logging_hook with completion call type."""
        # Create mock data
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        call_type = "completion"

        # Should return without error
        result = await handler.async_logging_hook(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=None,
            end_time=None,
            user_api_key_dict={},
            call_type=call_type,
        )

        # Should return None or the response_obj
        assert result is None or result == response_obj

    @pytest.mark.asyncio
    async def test_logging_hook_with_unsupported_call_type(self, handler: CCProxyHandler) -> None:
        """Test async_logging_hook with unsupported call type."""
        # Create mock data
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        call_type = "embeddings"  # Not supported

        # Should return without error
        result = await handler.async_logging_hook(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=None,
            end_time=None,
            user_api_key_dict={},
            call_type=call_type,
        )

        # Should return None or the response_obj
        assert result is None or result == response_obj

    @pytest.mark.asyncio
    async def test_log_stream_event(self, handler: CCProxyHandler) -> None:
        """Test log_stream_event method."""
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        start_time = 1234567890
        end_time = 1234567900

        # Should not raise any exceptions
        handler.log_stream_event(kwargs, response_obj, start_time, end_time)

    @pytest.mark.asyncio
    async def test_async_log_stream_event(self, handler: CCProxyHandler) -> None:
        """Test async_log_stream_event method."""
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        start_time = 1234567890
        end_time = 1234567900

        # Should not raise any exceptions
        await handler.async_log_stream_event(kwargs, response_obj, start_time, end_time)

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


class TestHandlerLoggingHookMethods:
    """Test suite for individual hook methods that haven't been covered."""

    @pytest.mark.asyncio
    async def test_log_success_hook(self) -> None:
        """Test async_log_success_hook method."""
        handler = CCProxyHandler()
        kwargs = {
            "litellm_params": {},
            "start_time": 1234567890,
            "end_time": 1234567900,
            "cache_hit": False,
        }
        response_obj = Mock(model="test-model", usage=Mock(completion_tokens=10, prompt_tokens=20, total_tokens=30))

        # Should not raise any exceptions
        await handler.async_log_success_hook(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_log_failure_hook(self, handler: CCProxyHandler) -> None:
        """Test async_log_failure_hook method."""
        kwargs = {
            "litellm_params": {},
            "start_time": 1234567890,
            "end_time": 1234567900,
        }
        response_obj = Mock()

        # Should not raise any exceptions
        await handler.async_log_failure_hook(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_logging_hook_with_completion(self, handler: CCProxyHandler) -> None:
        """Test async_logging_hook with completion call type."""
        # Create mock data
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        call_type = "completion"

        # Should return without error
        result = await handler.async_logging_hook(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=None,
            end_time=None,
            user_api_key_dict={},
            call_type=call_type,
        )

        # Should return None or the response_obj
        assert result is None or result == response_obj

    @pytest.mark.asyncio
    async def test_logging_hook_with_unsupported_call_type(self, handler: CCProxyHandler) -> None:
        """Test async_logging_hook with unsupported call type."""
        # Create mock data
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        call_type = "embeddings"  # Not supported

        # Should return without error
        result = await handler.async_logging_hook(
            kwargs=kwargs,
            response_obj=response_obj,
            start_time=None,
            end_time=None,
            user_api_key_dict={},
            call_type=call_type,
        )

        # Should return None or the response_obj
        assert result is None or result == response_obj

    @pytest.mark.asyncio
    async def test_log_stream_event(self, handler: CCProxyHandler) -> None:
        """Test log_stream_event method."""
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        start_time = 1234567890
        end_time = 1234567900

        # Should not raise any exceptions
        handler.log_stream_event(kwargs, response_obj, start_time, end_time)

    @pytest.mark.asyncio
    async def test_async_log_stream_event(self, handler: CCProxyHandler) -> None:
        """Test async_log_stream_event method."""
        kwargs = {"litellm_params": {}}
        response_obj = Mock()
        start_time = 1234567890
        end_time = 1234567900

        # Should not raise any exceptions
        await handler.async_log_stream_event(kwargs, response_obj, start_time, end_time)
