"""Tests for the ContextManager orchestrator."""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from ccproxy.claude_integration import ConversationHistory, Message, ProjectNotFoundError
from ccproxy.context_manager import ContextManager


@pytest.fixture
def mock_locator():
    """Create a mock ClaudeProjectLocator."""
    locator = Mock()
    return locator


@pytest.fixture
def mock_reader():
    """Create a mock ClaudeCodeReader."""
    reader = Mock()
    return reader


@pytest.fixture
def mock_store():
    """Create a mock ProviderMetadataStore."""
    store = AsyncMock()
    store.cleanup = Mock()
    return store


@pytest.fixture
def context_manager(mock_locator, mock_reader, mock_store):
    """Create a ContextManager with mocked dependencies."""
    return ContextManager(
        locator=mock_locator,
        reader=mock_reader,
        store=mock_store,
        cache_size=10,  # Small cache for testing
    )


@pytest.fixture
def sample_messages() -> list[Message]:
    """Create sample messages for testing."""
    return [
        Message(
            role="user",
            content="Hello, can you help me?",
            timestamp="2024-01-01T12:00:00Z",
            uuid=str(uuid4()),
            session_id="test-session-123",
            cwd="/test/project",
        ),
        Message(
            role="assistant",
            content="Of course! How can I assist you?",
            timestamp="2024-01-01T12:00:01Z",
            uuid=str(uuid4()),
            session_id="test-session-123",
        ),
    ]


@pytest.fixture
def sample_conversation(sample_messages) -> ConversationHistory:
    """Create a sample conversation history."""
    return ConversationHistory(
        session_id="test-session-123", messages=sample_messages, project_path=Path("/test/project"), cwd="/test/project"
    )


class TestContextManager:
    """Test ContextManager functionality."""

    async def test_get_context_success(
        self, context_manager, mock_locator, mock_reader, mock_store, sample_conversation, sample_messages
    ):
        """Test successful context retrieval."""
        # Setup mocks
        project_path = Path("/test/project")
        session_file = Path("/test/project/.claude/sessions/session.jsonl")

        mock_locator.find_project_path.return_value = project_path
        mock_locator.get_session_files.return_value = [session_file]

        # Mock file stats
        with patch.object(Path, "stat") as mock_stat_method:
            mock_stat = Mock()
            mock_stat.st_mtime = 1234567890.0
            mock_stat_method.return_value = mock_stat

            mock_reader.read_conversation.return_value = sample_conversation
            mock_store.get_provider_history.return_value = [
                {"provider": "anthropic", "model": "claude-3", "ts": 1234567890000}
            ]

            # Execute
            cwd = Path("/test/project/src")
            messages = await context_manager.get_context(cwd)

            # Verify
            assert messages == sample_messages
            mock_locator.find_project_path.assert_called_once_with(cwd)
            mock_locator.get_session_files.assert_called_once_with(project_path)
            mock_reader.read_conversation.assert_called_once_with(session_file)
            mock_store.get_provider_history.assert_called_once_with("test-session-123")

    async def test_get_context_no_project(self, context_manager, mock_locator):
        """Test when no Claude Code project is found."""
        mock_locator.find_project_path.side_effect = ProjectNotFoundError("No project")

        messages = await context_manager.get_context(Path("/random/dir"))

        assert messages == []
        mock_locator.find_project_path.assert_called_once()

    async def test_get_context_no_session_files(self, context_manager, mock_locator):
        """Test when no session files exist."""
        project_path = Path("/test/project")
        mock_locator.find_project_path.return_value = project_path
        mock_locator.get_session_files.return_value = []

        messages = await context_manager.get_context(Path("/test/project"))

        assert messages == []

    async def test_get_context_empty_conversation(self, context_manager, mock_locator, mock_reader):
        """Test when conversation has no messages."""
        project_path = Path("/test/project")
        session_file = Path("/test/project/.claude/sessions/session.jsonl")

        mock_locator.find_project_path.return_value = project_path
        mock_locator.get_session_files.return_value = [session_file]

        # Mock file stats
        with patch.object(Path, "stat") as mock_stat_method:
            mock_stat = Mock()
            mock_stat.st_mtime = 1234567890.0
            mock_stat_method.return_value = mock_stat

            # Empty conversation
            mock_reader.read_conversation.return_value = ConversationHistory(
                session_id="empty-session", messages=[], project_path=project_path, cwd=str(project_path)
            )

            messages = await context_manager.get_context(Path("/test/project"))

            assert messages == []

    async def test_cache_behavior(self, context_manager, mock_locator, mock_reader, mock_store, sample_conversation):
        """Test LRU cache behavior."""
        project_path = Path("/test/project")
        session_file = Path("/test/project/.claude/sessions/session.jsonl")

        mock_locator.find_project_path.return_value = project_path
        mock_locator.get_session_files.return_value = [session_file]

        # Mock file stats
        with patch.object(Path, "stat") as mock_stat_method:
            mock_stat = Mock()
            mock_stat.st_mtime = 1234567890.0
            mock_stat_method.return_value = mock_stat

            mock_reader.read_conversation.return_value = sample_conversation
            mock_store.get_provider_history.return_value = []

            # First call - cache miss
            await context_manager.get_context(Path("/test/project"))
            assert mock_reader.read_conversation.call_count == 1

            # Second call - cache hit
            await context_manager.get_context(Path("/test/project"))
            assert mock_reader.read_conversation.call_count == 1  # No additional call

            # Check cache stats
            stats = context_manager.get_cache_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1
            assert stats["hit_rate"] == 0.5

    async def test_cache_invalidation_on_mtime_change(
        self, context_manager, mock_locator, mock_reader, mock_store, sample_conversation
    ):
        """Test cache invalidation when file modification time changes."""
        project_path = Path("/test/project")
        session_file = Path("/test/project/.claude/sessions/session.jsonl")

        mock_locator.find_project_path.return_value = project_path
        mock_locator.get_session_files.return_value = [session_file]
        mock_reader.read_conversation.return_value = sample_conversation
        mock_store.get_provider_history.return_value = []

        # First call with mtime = 1000
        with patch.object(Path, "stat") as mock_stat_method:
            mock_stat = Mock()
            mock_stat.st_mtime = 1000.0
            mock_stat_method.return_value = mock_stat

            await context_manager.get_context(Path("/test/project"))
            assert mock_reader.read_conversation.call_count == 1

            # Second call with same mtime - cache hit
            await context_manager.get_context(Path("/test/project"))
            assert mock_reader.read_conversation.call_count == 1

            # Third call with different mtime - cache miss
            mock_stat.st_mtime = 2000.0
            await context_manager.get_context(Path("/test/project"))
            assert mock_reader.read_conversation.call_count == 2

    async def test_record_decision(self, context_manager, mock_store):
        """Test recording routing decisions."""
        await context_manager.record_decision(
            session_id="test-session-123",
            provider="anthropic",
            model="claude-3-5-sonnet",
            request_id="req-456",
            selected_by_rule="large_context",
            metadata={"tokens": 50000},
        )

        # Verify store was called
        mock_store.record_routing_decision.assert_called_once()
        decision = mock_store.record_routing_decision.call_args[0][0]

        assert decision.session_id == "test-session-123"
        assert decision.provider == "anthropic"
        assert decision.model == "claude-3-5-sonnet"
        assert decision.request_id == "req-456"
        assert decision.selected_by_rule == "large_context"
        assert decision.metadata == {"tokens": 50000}

    async def test_record_decision_no_session_id(self, context_manager, mock_store):
        """Test that recording without session_id is skipped."""
        await context_manager.record_decision(session_id="", provider="anthropic", model="claude-3")

        mock_store.record_routing_decision.assert_not_called()

    async def test_error_handling_in_get_context(self, context_manager, mock_locator, mock_reader):
        """Test error handling in get_context."""
        mock_locator.find_project_path.side_effect = Exception("Unexpected error")

        messages = await context_manager.get_context(Path("/test/project"))

        assert messages == []

    async def test_error_handling_in_record_decision(self, context_manager, mock_store):
        """Test error handling in record_decision."""
        mock_store.record_routing_decision.side_effect = Exception("Storage error")

        # Should not raise
        await context_manager.record_decision(session_id="test-session", provider="test", model="test-model")

    def test_clear_cache(self, context_manager):
        """Test cache clearing."""
        # Add some fake cache entries by accessing the internal method
        context_manager._cached_read_session("test1", 1.0)
        context_manager._cached_read_session("test2", 2.0)

        stats_before = context_manager.get_cache_stats()
        assert stats_before["currsize"] > 0

        context_manager.clear_cache()

        stats_after = context_manager.get_cache_stats()
        assert stats_after["currsize"] == 0
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0

    def test_cleanup(self, context_manager, mock_store):
        """Test cleanup method."""
        context_manager.cleanup()

        # Verify store cleanup was called
        mock_store.cleanup.assert_called_once()

        # Verify cache was cleared
        stats = context_manager.get_cache_stats()
        assert stats["currsize"] == 0


class TestContextManagerIntegration:
    """Integration tests with real file system operations."""

    async def test_end_to_end_with_real_files(self, tmp_path):
        """Test end-to-end with real temporary files."""
        from ccproxy.claude_integration import ClaudeCodeReader, ClaudeProjectLocator
        from ccproxy.provider_metadata import ProviderMetadataStore

        # Setup Claude Code directory structure
        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        projects_dir.mkdir(parents=True)

        # Create a project directory with the correct naming convention
        # For path /test/project, the Claude Code project name is "-test--project"
        claude_project_dir = projects_dir / "-test--project"
        claude_project_dir.mkdir()

        # Create a session file
        session_id = str(uuid4())
        session_file = claude_project_dir / "test_session.jsonl"

        messages = [
            {
                "role": "user",
                "content": "Test message",
                "timestamp": "2024-01-01T12:00:00Z",
                "uuid": str(uuid4()),
                "sessionId": session_id,
                "message": {"role": "user", "content": "Test message"},
            },
            {
                "role": "assistant",
                "content": "Test response",
                "timestamp": "2024-01-01T12:00:01Z",
                "uuid": str(uuid4()),
                "sessionId": session_id,
                "message": {"role": "assistant", "content": "Test response"},
            },
        ]

        with session_file.open("w") as f:
            for msg in messages:
                json.dump(msg, f)
                f.write("\n")

        # Create real components with custom claude_dir
        locator = ClaudeProjectLocator(claude_dir=claude_home)
        reader = ClaudeCodeReader()
        store = ProviderMetadataStore(base_path=tmp_path / ".ccproxy")

        # Create context manager
        context_manager = ContextManager(locator=locator, reader=reader, store=store)

        try:
            # Test get_context - use /test/project as the working directory
            # This will be found as "-test--project" in the claude projects
            start_time = time.time()
            result_messages = await context_manager.get_context(Path("/test/project"))
            elapsed = time.time() - start_time

            # Verify results
            assert len(result_messages) == 2
            assert result_messages[0].content == "Test message"
            assert result_messages[1].content == "Test response"

            # Verify performance (should be < 100ms)
            assert elapsed < 0.1, f"Latency {elapsed:.3f}s exceeds 100ms limit"

            # Test record_decision
            await context_manager.record_decision(
                session_id=session_id, provider="test-provider", model="test-model", selected_by_rule="test-rule"
            )

            # Verify decision was recorded
            history = await store.get_provider_history(session_id)
            assert len(history) == 1
            assert history[0]["provider"] == "test-provider"

        finally:
            context_manager.cleanup()

    async def test_cache_invalidation_on_file_update(self, tmp_path):
        """Test that cache is invalidated when session file is updated."""
        from ccproxy.claude_integration import ClaudeCodeReader, ClaudeProjectLocator
        from ccproxy.provider_metadata import ProviderMetadataStore

        # Setup Claude Code directory structure
        claude_home = tmp_path / ".claude"
        projects_dir = claude_home / "projects"
        projects_dir.mkdir(parents=True)

        # Create project for /test/project path
        claude_project_dir = projects_dir / "-test--project"
        claude_project_dir.mkdir()

        session_file = claude_project_dir / "test_session.jsonl"
        session_id = str(uuid4())

        # Initial content
        initial_messages = [
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "uuid": str(uuid4()),
                "sessionId": session_id,
                "message": {"role": "user", "content": "Initial"},
            }
        ]

        with session_file.open("w") as f:
            for msg in initial_messages:
                json.dump(msg, f)
                f.write("\n")

        # Create context manager with custom claude_dir
        context_manager = ContextManager(
            locator=ClaudeProjectLocator(claude_dir=claude_home),
            reader=ClaudeCodeReader(),
            store=ProviderMetadataStore(base_path=tmp_path / ".ccproxy"),
        )

        try:
            # First read - use /test/project path
            messages1 = await context_manager.get_context(Path("/test/project"))
            assert len(messages1) == 1
            assert messages1[0].content == "Initial"

            # Wait a bit to ensure different mtime
            await asyncio.sleep(0.01)

            # Update file
            updated_messages = initial_messages + [
                {
                    "timestamp": "2024-01-01T12:00:01Z",
                    "uuid": str(uuid4()),
                    "sessionId": session_id,
                    "message": {"role": "assistant", "content": "Response"},
                }
            ]

            with session_file.open("w") as f:
                for msg in updated_messages:
                    json.dump(msg, f)
                    f.write("\n")

            # Second read - should get updated content
            messages2 = await context_manager.get_context(Path("/test/project"))
            assert len(messages2) == 2
            assert messages2[1].content == "Response"

            # Verify cache stats
            stats = context_manager.get_cache_stats()
            assert stats["hits"] == 0  # Both were misses due to mtime change
            assert stats["misses"] == 2

        finally:
            context_manager.cleanup()
