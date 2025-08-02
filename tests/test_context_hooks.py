"""Tests for context preservation hooks."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccproxy.claude_integration import Message
from ccproxy.context_hooks import (
    cleanup_context_manager,
    context_injection_hook,
    context_recording_hook,
    get_context_manager,
)


class TestContextInjectionHook:
    """Tests for the context injection pre-call hook."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration with context enabled."""
        config = Mock()
        config.context = {"enabled": True}
        return config

    @pytest.fixture
    def mock_context_manager(self):
        """Mock context manager with test messages."""
        manager = Mock()

        # Mock get_context to return test messages
        test_messages = [
            Message(
                role="user",
                content="Previous question",
                timestamp="2024-01-01T12:00:00.000Z",
                uuid="msg-1",
                session_id="test-session-123",
                cwd="/test/project",
                model=None,
                type="user",
            ),
            Message(
                role="assistant",
                content="Previous response",
                timestamp="2024-01-01T12:00:05.000Z",
                uuid="msg-2",
                session_id="test-session-123",
                cwd="/test/project",
                model="claude-3-sonnet",
                type="assistant",
            ),
        ]

        # Convert to async mock
        manager.get_context = AsyncMock(return_value=test_messages)
        manager.record_decision = AsyncMock()
        manager.cleanup = Mock()

        return manager

    @pytest.mark.asyncio
    async def test_hook_disabled_when_config_disabled(self, mock_config):
        """Test that hook returns data unchanged when disabled."""
        mock_config.context = {"enabled": False}

        with patch("ccproxy.context_hooks.get_config", return_value=mock_config):
            data = {"messages": [{"role": "user", "content": "Current question"}]}
            result = await context_injection_hook(data, {})

            # Should return unchanged
            assert result == data
            assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_hook_returns_unchanged_on_no_manager(self, mock_config):
        """Test graceful handling when context manager unavailable."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=None),
        ):
            data = {"messages": [{"role": "user", "content": "Current question"}]}
            result = await context_injection_hook(data, {})

            # Should return unchanged
            assert result == data

    @pytest.mark.asyncio
    async def test_successful_context_injection(self, mock_config, mock_context_manager):
        """Test successful injection of context messages."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
        ):
            data = {
                "messages": [{"role": "user", "content": "Current question"}],
                "proxy_server_request": {"headers": {"x-chat-id": "chat-123", "x-cwd": "/test/project"}},
            }

            result = await context_injection_hook(data, {})

            # Verify get_context was called
            mock_context_manager.get_context.assert_called_once_with(Path("/test/project"), "chat-123")

            # Should have 3 messages total (2 context + 1 current)
            assert len(result["messages"]) == 3

            # Context messages should be first
            assert result["messages"][0]["role"] == "user"
            assert result["messages"][0]["content"] == "Previous question"
            assert result["messages"][1]["role"] == "assistant"
            assert result["messages"][1]["content"] == "Previous response"
            assert result["messages"][1]["model"] == "claude-3-sonnet"

            # Current message should be last
            assert result["messages"][2]["role"] == "user"
            assert result["messages"][2]["content"] == "Current question"

            # Session ID should be stored in metadata
            assert result["metadata"]["claude_session_id"] == "test-session-123"

    @pytest.mark.asyncio
    async def test_context_injection_without_headers(self, mock_config, mock_context_manager):
        """Test context injection using current working directory."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
            patch("pathlib.Path.cwd", return_value=Path("/current/dir")),
        ):
            data = {"messages": [{"role": "user", "content": "Current question"}]}

            result = await context_injection_hook(data, {})

            # Should call get_context with current directory
            mock_context_manager.get_context.assert_called_once_with(Path("/current/dir"), None)

            # Should have injected context
            assert len(result["messages"]) == 3

    @pytest.mark.asyncio
    async def test_empty_context_returns_unchanged(self, mock_config):
        """Test that empty context doesn't modify messages."""
        manager = Mock()
        manager.get_context = AsyncMock(return_value=[])

        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=manager),
        ):
            data = {"messages": [{"role": "user", "content": "Current question"}]}

            result = await context_injection_hook(data, {})

            # Should return unchanged
            assert result == data
            assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_error_handling_continues_without_context(self, mock_config):
        """Test that errors don't break the request."""
        manager = Mock()
        manager.get_context = AsyncMock(side_effect=Exception("Test error"))

        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=manager),
        ):
            data = {"messages": [{"role": "user", "content": "Current question"}]}

            # Should not raise
            result = await context_injection_hook(data, {})

            # Should return unchanged
            assert result == data
            assert len(result["messages"]) == 1


class TestContextRecordingHook:
    """Tests for the context recording post-call hook."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration with context enabled."""
        config = Mock()
        config.context = {"enabled": True}
        return config

    @pytest.fixture
    def mock_context_manager(self):
        """Mock context manager."""
        manager = Mock()
        manager.record_decision = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_hook_disabled_when_config_disabled(self, mock_config):
        """Test that hook does nothing when disabled."""
        mock_config.context = {"enabled": False}

        with patch("ccproxy.context_hooks.get_config", return_value=mock_config):
            # Should complete without error
            await context_recording_hook({}, Mock())

    @pytest.mark.asyncio
    async def test_hook_returns_on_no_manager(self, mock_config):
        """Test graceful handling when context manager unavailable."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=None),
        ):
            # Should complete without error
            await context_recording_hook({}, Mock())

    @pytest.mark.asyncio
    async def test_successful_recording_with_session_id(self, mock_config, mock_context_manager):
        """Test successful recording of routing decision."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
        ):
            data = {
                "metadata": {
                    "claude_session_id": "test-session-123",
                    "ccproxy_litellm_model": "anthropic/claude-3-sonnet",
                    "request_id": "req-456",
                    "ccproxy_label": "default",
                    "ccproxy_alias_model": "claude-3-sonnet",
                }
            }

            response_obj = Mock()
            response_obj._hidden_params = {"custom_llm_provider": "anthropic"}

            await context_recording_hook(data, response_obj)

            # Should have called record_decision
            mock_context_manager.record_decision.assert_called_once()

            # Check call arguments
            call_args = mock_context_manager.record_decision.call_args[1]
            assert call_args["session_id"] == "test-session-123"
            assert call_args["provider"] == "anthropic"
            assert call_args["model"] == "anthropic/claude-3-sonnet"
            assert call_args["request_id"] == "req-456"
            assert call_args["selected_by_rule"] == "default"
            assert call_args["metadata"]["original_model"] == "claude-3-sonnet"

    @pytest.mark.asyncio
    async def test_recording_without_session_id_skips(self, mock_config, mock_context_manager):
        """Test that recording is skipped without session ID."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
        ):
            data = {"metadata": {}}

            await context_recording_hook(data, Mock())

            # Should not have called record_decision
            mock_context_manager.record_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_extraction_from_model_string(self, mock_config, mock_context_manager):
        """Test extracting provider from model string format."""
        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
        ):
            data = {"metadata": {"claude_session_id": "test-session-123", "ccproxy_litellm_model": "openai/gpt-4"}}

            response_obj = Mock()
            response_obj._hidden_params = None

            await context_recording_hook(data, response_obj)

            # Should extract provider from model string
            call_args = mock_context_manager.record_decision.call_args[1]
            assert call_args["provider"] == "openai"
            assert call_args["model"] == "openai/gpt-4"

    @pytest.mark.asyncio
    async def test_error_handling_continues_silently(self, mock_config, mock_context_manager):
        """Test that errors don't break the response."""
        mock_context_manager.record_decision = AsyncMock(side_effect=Exception("Test error"))

        with (
            patch("ccproxy.context_hooks.get_config", return_value=mock_config),
            patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
        ):
            data = {"metadata": {"claude_session_id": "test-session-123", "ccproxy_litellm_model": "test/model"}}

            # Should not raise
            await context_recording_hook(data, Mock())


class TestContextManagerLifecycle:
    """Tests for context manager initialization and cleanup."""

    def test_get_context_manager_initialization(self):
        """Test context manager is properly initialized."""
        # Clean up any existing instance
        cleanup_context_manager()

        with (
            patch("ccproxy.context_hooks.ClaudeProjectLocator") as mock_locator,
            patch("ccproxy.context_hooks.ClaudeCodeReader") as mock_reader,
            patch("ccproxy.context_hooks.ProviderMetadataStore") as mock_store,
        ):
            manager = get_context_manager()

            assert manager is not None
            mock_locator.assert_called_once()
            mock_reader.assert_called_once()
            mock_store.assert_called_once()

            # Should return same instance on subsequent calls
            manager2 = get_context_manager()
            assert manager2 is manager

    def test_get_context_manager_error_handling(self):
        """Test error handling during initialization."""
        # Clean up any existing instance
        cleanup_context_manager()

        with patch("ccproxy.context_hooks.ClaudeProjectLocator", side_effect=Exception("Init error")):
            manager = get_context_manager()
            assert manager is None

    def test_cleanup_context_manager(self):
        """Test cleanup properly releases resources."""
        # Clean up any existing instance first
        cleanup_context_manager()

        # Initialize a manager
        with (
            patch("ccproxy.context_hooks.ClaudeProjectLocator"),
            patch("ccproxy.context_hooks.ClaudeCodeReader"),
            patch("ccproxy.context_hooks.ProviderMetadataStore"),
            patch("ccproxy.context_hooks.ContextManager") as mock_context_manager_cls,
        ):
            # Create mock instances
            mock_instance1 = Mock()
            mock_instance1.cleanup = Mock()
            mock_instance2 = Mock()
            mock_instance2.cleanup = Mock()

            # Return different instances on each call
            mock_context_manager_cls.side_effect = [mock_instance1, mock_instance2]

            # Get the first manager
            manager1 = get_context_manager()
            assert manager1 is mock_instance1

            # Clean up
            cleanup_context_manager()

            # Should have called cleanup on first instance
            mock_instance1.cleanup.assert_called_once()

            # Should create new instance after cleanup
            manager2 = get_context_manager()
            assert manager2 is mock_instance2
            assert manager2 is not manager1
