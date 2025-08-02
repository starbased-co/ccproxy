"""Test session ID extraction from Claude Code metadata."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccproxy.claude_integration import Message
from ccproxy.context_hooks import context_injection_hook
from ccproxy.context_manager import ContextManager


@pytest.mark.asyncio
async def test_session_id_extraction_from_metadata():
    """Test that session ID is extracted from metadata.user_id field."""
    # Create mock request data with Claude Code metadata format
    data = {
        "model": "claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test message"}],
        "metadata": {
            "user_id": (
                "user_19f2f4ee153d47fb2ef3e7954239ff16d3bff6daddd7cac0b1e7e3794fcaae80_"
                "account_a929b7ef-d758-4a98-b88e-07166e6c8537_"
                "session_2978ad57-d800-4a88-85fb-490d108ed665"
            )
        },
    }

    # Mock config to enable context preservation
    mock_config = Mock()
    mock_config.context = {"enabled": True}

    # Mock context manager
    mock_context_manager = AsyncMock(spec=ContextManager)
    mock_messages = [
        Message(
            role="user",
            content="Previous message",
            timestamp="2025-01-01T00:00:00Z",
            uuid="test-uuid",
            session_id="2978ad57-d800-4a88-85fb-490d108ed665",
        )
    ]
    mock_context_manager.get_context.return_value = mock_messages

    with (
        patch("ccproxy.context_hooks.get_config", return_value=mock_config),
        patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
    ):
        # Call the hook
        result = await context_injection_hook(data, {})

        # Verify session ID was extracted and passed to context manager
        mock_context_manager.get_context.assert_called_once()
        call_args = mock_context_manager.get_context.call_args

        # Check that session ID was passed as third argument
        assert len(call_args[0]) == 3
        assert call_args[0][2] == "2978ad57-d800-4a88-85fb-490d108ed665"

        # Verify context was injected
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "Previous message"


@pytest.mark.asyncio
async def test_session_id_extraction_with_invalid_format():
    """Test handling of invalid metadata.user_id format."""
    # Create request with invalid user_id format
    data = {
        "model": "claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test message"}],
        "metadata": {"user_id": "invalid_format_without_session"},
    }

    mock_config = Mock()
    mock_config.context = {"enabled": True}

    mock_context_manager = AsyncMock(spec=ContextManager)
    mock_context_manager.get_context.return_value = []

    with (
        patch("ccproxy.context_hooks.get_config", return_value=mock_config),
        patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
    ):
        # Call the hook
        await context_injection_hook(data, {})

        # Verify session ID was None (not extracted)
        call_args = mock_context_manager.get_context.call_args
        assert call_args[0][2] is None  # session_id should be None


@pytest.mark.asyncio
async def test_session_id_extraction_without_metadata():
    """Test handling when metadata is missing."""
    # Create request without metadata
    data = {"model": "claude-3-5-haiku-20241022", "messages": [{"role": "user", "content": "test message"}]}

    mock_config = Mock()
    mock_config.context = {"enabled": True}

    mock_context_manager = AsyncMock(spec=ContextManager)
    mock_context_manager.get_context.return_value = []

    with (
        patch("ccproxy.context_hooks.get_config", return_value=mock_config),
        patch("ccproxy.context_hooks.get_context_manager", return_value=mock_context_manager),
    ):
        # Call the hook
        await context_injection_hook(data, {})

        # Verify session ID was None
        call_args = mock_context_manager.get_context.call_args
        assert call_args[0][2] is None


@pytest.mark.asyncio
async def test_context_manager_find_session_by_id():
    """Test the _find_session_by_id method."""
    from ccproxy.claude_integration import ClaudeCodeReader, ClaudeProjectLocator
    from ccproxy.provider_metadata import ProviderMetadataStore

    # Create mock components
    mock_locator = Mock(spec=ClaudeProjectLocator)
    mock_locator.projects_dir = Path("/home/test/.claude/projects")

    mock_reader = Mock(spec=ClaudeCodeReader)
    mock_store = Mock(spec=ProviderMetadataStore)

    # Create context manager
    context_manager = ContextManager(locator=mock_locator, reader=mock_reader, store=mock_store)

    # Mock the file system operations properly
    mock_project1 = Mock(spec=Path)
    mock_project1.is_dir.return_value = True
    mock_project1.__truediv__ = lambda self, other: Path(f"/home/test/.claude/projects/project1/{other}")

    mock_project2 = Mock(spec=Path)
    mock_project2.is_dir.return_value = True
    mock_project2.__truediv__ = lambda self, other: Path(f"/home/test/.claude/projects/project2/{other}")

    # Patch the specific methods we need
    with patch.object(Path, "exists") as mock_exists, patch.object(Path, "iterdir") as mock_iterdir:
        # Set up the mocks
        def exists_side_effect(self):
            path_str = str(self)
            if path_str == "/home/test/.claude/projects":
                return True
            # Session file exists in project2
            return path_str == "/home/test/.claude/projects/project2/2978ad57-d800-4a88-85fb-490d108ed665.jsonl"

        mock_exists.side_effect = exists_side_effect
        mock_iterdir.return_value = [mock_project1, mock_project2]

        # Test finding a session
        result = await context_manager._find_session_by_id("2978ad57-d800-4a88-85fb-490d108ed665")
        assert result is not None
        assert str(result) == "/home/test/.claude/projects/project2/2978ad57-d800-4a88-85fb-490d108ed665.jsonl"
