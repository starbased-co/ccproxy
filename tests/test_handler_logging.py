"""Additional tests for CCProxyHandler logging hook methods."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from ccproxy.handler import CCProxyHandler, ccproxy_get_model


class TestHandlerLoggingHookMethods:
    """Test suite for individual logging hook methods."""

    @pytest.mark.asyncio
    async def test_log_success_event(self) -> None:
        """Test async_log_success_event method."""
        handler = CCProxyHandler()
        kwargs = {"metadata": {"request_id": "test-123", "ccproxy_label": "default"}, "model": "test-model"}
        response_obj = Mock(model="test-model", usage=Mock(prompt_tokens=20, completion_tokens=10, total_tokens=30))

        # Should not raise any exceptions
        await handler.async_log_success_event(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_log_failure_event(self) -> None:
        """Test async_log_failure_event method."""
        handler = CCProxyHandler()
        kwargs = {"metadata": {"request_id": "test-123", "ccproxy_label": "default"}, "model": "test-model"}
        response_obj = Exception("Test error")

        # Should not raise any exceptions
        await handler.async_log_failure_event(kwargs, response_obj, 1234567890, 1234567900)

    @pytest.mark.asyncio
    async def test_async_log_stream_event(self) -> None:
        """Test async_log_stream_event method."""
        handler = CCProxyHandler()
        kwargs = {"metadata": {"request_id": "test-123", "ccproxy_label": "default"}, "model": "test-model"}
        response_obj = Mock()
        start_time = 1234567890
        end_time = 1234567900

        # Should not raise any exceptions
        await handler.async_log_stream_event(kwargs, response_obj, start_time, end_time)

    @pytest.mark.asyncio
    async def test_async_pre_call_hook_with_invalid_request(self) -> None:
        """Test async_pre_call_hook with invalid request format."""
        handler = CCProxyHandler()

        # Missing model field - should use default
        data = {"messages": [{"role": "user", "content": "test"}]}

        # Should not raise - adds metadata and uses original model
        result = await handler.async_pre_call_hook(data, {})
        assert "metadata" in result
        assert result["metadata"]["ccproxy_label"] == "default"
        assert result["metadata"]["ccproxy_original_model"] == "unknown"

    @patch("ccproxy.handler.get_config")
    @patch("ccproxy.handler.get_router")
    @patch("ccproxy.handler.RequestClassifier")
    def test_ccproxy_get_model(self, mock_classifier_class: Mock, mock_get_router: Mock, mock_get_config: Mock) -> None:
        """Test ccproxy_get_model function."""
        # Setup mocks
        mock_config = Mock(debug=True)
        mock_get_config.return_value = mock_config

        mock_router = Mock()
        mock_router.get_available_models.return_value = ["default", "large_context"]
        mock_router.get_model_for_label.return_value = {"litellm_params": {"model": "gemini-2.0-flash-exp"}}
        mock_get_router.return_value = mock_router

        mock_classifier = Mock()
        mock_classifier.classify.return_value = "large_context"
        mock_classifier_class.return_value = mock_classifier

        # Test with label that exists
        data = {"model": "claude-3-5-sonnet", "messages": []}
        result = ccproxy_get_model(data)

        assert result == "gemini-2.0-flash-exp"
        mock_classifier.classify.assert_called_once_with(data)

    @patch("ccproxy.handler.get_config")
    @patch("ccproxy.handler.get_router")
    @patch("ccproxy.handler.RequestClassifier")
    def test_ccproxy_get_model_label_not_configured(
        self, mock_classifier_class: Mock, mock_get_router: Mock, mock_get_config: Mock
    ) -> None:
        """Test ccproxy_get_model when label is not in available models."""
        # Setup mocks
        mock_config = Mock(debug=False)
        mock_get_config.return_value = mock_config

        mock_router = Mock()
        mock_router.get_available_models.return_value = ["default"]  # "large_context" not available
        mock_get_router.return_value = mock_router

        mock_classifier = Mock()
        mock_classifier.classify.return_value = "large_context"
        mock_classifier_class.return_value = mock_classifier

        # Test with label that doesn't exist
        data = {"model": "claude-3-5-sonnet", "messages": []}
        result = ccproxy_get_model(data)

        # Should return original model
        assert result == "claude-3-5-sonnet"

    @patch("ccproxy.handler.logger")
    def test_log_routing_decision(self, mock_logger: Mock) -> None:
        """Test _log_routing_decision method."""
        handler = CCProxyHandler()

        # Test with model config
        model_config = {
            "model_info": {
                "provider": "google",
                "max_tokens": 1000000,
                "api_key": "secret",  # Should be filtered out
            }
        }

        handler._log_routing_decision(
            label="large_context",
            original_model="claude-3-5-sonnet",
            routed_model="gemini-2.0-flash-exp",
            request_id="test-123",
            model_config=model_config,
        )

        # Check logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "CCProxy routing decision"

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event"] == "ccproxy_routing"
        assert extra["label"] == "large_context"
        assert extra["original_model"] == "claude-3-5-sonnet"
        assert extra["routed_model"] == "gemini-2.0-flash-exp"
        assert extra["request_id"] == "test-123"
        assert extra["fallback_used"] is False

        # Check sensitive data was filtered
        assert "api_key" not in extra["model_info"]
        assert extra["model_info"]["provider"] == "google"
        assert extra["model_info"]["max_tokens"] == 1000000

    @pytest.mark.asyncio
    async def test_timedelta_duration_handling(self) -> None:
        """Test that handler correctly handles timedelta objects for timestamps."""
        handler = CCProxyHandler()
        kwargs = {"metadata": {"request_id": "test-123", "ccproxy_label": "default"}, "model": "test-model"}
        response_obj = Mock()

        # Test with timedelta objects (simulating LiteLLM's behavior)
        start_time = timedelta(seconds=100)
        end_time = timedelta(seconds=102, milliseconds=500)

        # Should not raise any exceptions - test success logging
        await handler.async_log_success_event(kwargs, response_obj, start_time, end_time)

        # Should not raise any exceptions - test failure logging
        await handler.async_log_failure_event(kwargs, response_obj, start_time, end_time)

        # Should not raise any exceptions - test streaming logging
        await handler.async_log_stream_event(kwargs, response_obj, start_time, end_time)

    @pytest.mark.asyncio
    async def test_mixed_timestamp_types_handling(self) -> None:
        """Test that handler correctly handles mixed float/timedelta timestamp types."""
        handler = CCProxyHandler()
        kwargs = {"metadata": {"request_id": "test-123", "ccproxy_label": "default"}, "model": "test-model"}
        response_obj = Mock()

        # Test with mixed types (float start, timedelta end)
        start_time = 100.0
        end_time = timedelta(seconds=102, milliseconds=500)

        # Should not raise any exceptions and handle gracefully
        await handler.async_log_success_event(kwargs, response_obj, start_time, end_time)
        await handler.async_log_failure_event(kwargs, response_obj, start_time, end_time)
        await handler.async_log_stream_event(kwargs, response_obj, start_time, end_time)
