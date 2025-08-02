"""Tests for Claude Code integration functionality."""

import json
import time
from pathlib import Path

import pytest

from ccproxy.claude_integration import (
    ClaudeCodeReader,
    ClaudeProjectLocator,
    ConversationHistory,
    ProjectInfo,
    ProjectNotFoundError,
)


class TestClaudeProjectLocator:
    """Test suite for ClaudeProjectLocator."""

    @pytest.fixture
    def temp_claude_dir(self, tmp_path: Path) -> Path:
        """Create a temporary Claude directory structure."""
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir(parents=True)
        return claude_dir

    @pytest.fixture
    def temp_project_with_sessions(self, temp_claude_dir: Path) -> tuple[Path, Path]:
        """Create a temporary project with dummy JSONL files."""
        projects_dir = temp_claude_dir / "projects"

        # Create project directory (simulating /home/user/project -> -home--user--project)
        project_dir = projects_dir / "-home--user--project"
        project_dir.mkdir()

        # Create dummy JSONL files
        session1 = project_dir / "session1.jsonl"
        session2 = project_dir / "session2.jsonl"

        # Create dummy JSONL content
        dummy_entry = {
            "sessionId": "test-session-123",
            "timestamp": "2024-01-01T12:00:00.000Z",
            "uuid": "test-uuid",
            "cwd": "/home/user/project",
            "message": {"role": "user", "content": "test message"},
        }

        with session1.open("w") as f:
            f.write(json.dumps(dummy_entry) + "\n")

        with session2.open("w") as f:
            f.write(json.dumps(dummy_entry) + "\n")

        # Make session2 newer
        time.sleep(0.01)
        session2.touch()

        return project_dir, Path("/home/user/project")

    def test_init_default_claude_dir(self):
        """Test initialization with default Claude directory."""
        locator = ClaudeProjectLocator()
        assert locator.claude_dir == Path.home() / ".claude"
        assert locator.projects_dir == Path.home() / ".claude" / "projects"

    def test_init_custom_claude_dir(self, tmp_path: Path):
        """Test initialization with custom Claude directory."""
        custom_dir = tmp_path / "custom_claude"
        locator = ClaudeProjectLocator(claude_dir=custom_dir)
        assert locator.claude_dir == custom_dir
        assert locator.projects_dir == custom_dir / "projects"

    def test_find_project_path_exact_match(self, temp_project_with_sessions):
        """Test finding project path with exact directory match."""
        project_dir, working_dir = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        result = locator.find_project_path(working_dir)
        assert result == project_dir

    def test_find_project_path_parent_match(self, temp_project_with_sessions):
        """Test finding project path by walking up to parent directory."""
        project_dir, working_dir = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        # Test with subdirectory
        subdir = working_dir / "subdir"
        result = locator.find_project_path(subdir)
        assert result == project_dir

    def test_find_project_path_not_found(self, temp_claude_dir: Path):
        """Test handling when no project is found."""
        locator = ClaudeProjectLocator(claude_dir=temp_claude_dir)

        # Test with non-existent project
        non_existent = Path("/completely/different/path")
        result = locator.find_project_path(non_existent)
        assert result is None

    def test_find_project_path_no_projects_dir(self, tmp_path: Path):
        """Test handling when projects directory doesn't exist."""
        locator = ClaudeProjectLocator(claude_dir=tmp_path)

        result = locator.find_project_path(Path("/any/path"))
        assert result is None

    def test_get_session_files_sorts_by_mtime(self, temp_project_with_sessions):
        """Test that session files are sorted by modification time (newest first)."""
        project_dir, _ = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        session_files = locator.get_session_files(project_dir)

        assert len(session_files) == 2
        assert all(f.suffix == ".jsonl" for f in session_files)

        # Should be sorted newest first
        assert session_files[0].name == "session2.jsonl"  # newer
        assert session_files[1].name == "session1.jsonl"  # older

    def test_get_session_files_empty_directory(self, temp_claude_dir: Path):
        """Test handling empty project directory."""
        empty_dir = temp_claude_dir / "projects" / "empty"
        empty_dir.mkdir(parents=True)

        locator = ClaudeProjectLocator(claude_dir=temp_claude_dir)
        session_files = locator.get_session_files(empty_dir)

        assert session_files == []

    def test_get_session_files_nonexistent_directory(self, temp_claude_dir: Path):
        """Test handling non-existent directory."""
        locator = ClaudeProjectLocator(claude_dir=temp_claude_dir)

        non_existent = temp_claude_dir / "nonexistent"
        session_files = locator.get_session_files(non_existent)

        assert session_files == []

    def test_cache_project_info(self, temp_project_with_sessions):
        """Test caching of project information."""
        project_dir, _ = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        # First call should populate cache
        info1 = locator.cache_project_info(project_dir)
        assert isinstance(info1, ProjectInfo)
        assert info1.project_path == project_dir
        assert len(info1.session_files) == 2

        # Second call should use cache (verify by checking timestamp)
        info2 = locator.cache_project_info(project_dir)
        assert info1.last_modified == info2.last_modified

    def test_cache_invalidation_on_directory_change(self, temp_project_with_sessions):
        """Test that cache is invalidated when directory is modified."""
        project_dir, _ = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        # Initial cache
        info1 = locator.cache_project_info(project_dir)

        # Modify directory (add new JSONL file with valid content)
        time.sleep(0.01)  # Ensure different mtime
        new_session = project_dir / "session3.jsonl"
        dummy_entry = {
            "sessionId": "test-session-789",
            "timestamp": "2024-01-01T12:00:10.000Z",
            "uuid": "test-uuid-3",
            "cwd": "/home/user/project",
            "message": {"role": "user", "content": "test message 3"},
        }
        new_session.write_text(json.dumps(dummy_entry) + "\n")

        # Update directory mtime to trigger cache invalidation
        project_dir.touch()

        # Cache should be invalidated and updated
        info2 = locator.cache_project_info(project_dir)
        assert len(info2.session_files) == 3
        assert info2.last_modified > info1.last_modified

    def test_discover_for_working_directory_success(self, temp_project_with_sessions):
        """Test successful discovery of project for working directory."""
        project_dir, working_dir = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        result = locator.discover_for_working_directory(working_dir)

        assert isinstance(result, ProjectInfo)
        assert result.project_path == project_dir
        assert len(result.session_files) == 2

    def test_discover_for_working_directory_string_path(self, temp_project_with_sessions):
        """Test discovery with string path input."""
        project_dir, working_dir = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        result = locator.discover_for_working_directory(str(working_dir))

        assert isinstance(result, ProjectInfo)
        assert result.project_path == project_dir

    def test_discover_for_working_directory_not_found(self, temp_claude_dir: Path):
        """Test ProjectNotFoundError when no project exists."""
        locator = ClaudeProjectLocator(claude_dir=temp_claude_dir)

        with pytest.raises(ProjectNotFoundError) as exc_info:
            locator.discover_for_working_directory("/nonexistent/path")

        assert "No Claude Code project found" in str(exc_info.value)

    def test_path_resolution_consistency(self, temp_project_with_sessions):
        """Test that path resolution is consistent across multiple calls."""
        project_dir, working_dir = temp_project_with_sessions
        locator = ClaudeProjectLocator(claude_dir=project_dir.parent.parent)

        # Multiple calls should return the same result
        result1 = locator.find_project_path(working_dir)
        result2 = locator.find_project_path(working_dir)
        result3 = locator.find_project_path(working_dir)

        assert result1 == result2 == result3 == project_dir


class TestClaudeCodeReader:
    """Test suite for ClaudeCodeReader."""

    @pytest.fixture
    def sample_jsonl_content(self) -> list[dict]:
        """Create sample JSONL content for testing."""
        return [
            {
                "sessionId": "12345678-1234-1234-1234-123456789012",
                "timestamp": "2024-01-01T12:00:00.000Z",
                "uuid": "user-msg-1",
                "cwd": "/test/project",
                "type": "user",
                "message": {"role": "user", "content": "Hello, world!"},
            },
            {
                "sessionId": "12345678-1234-1234-1234-123456789012",
                "timestamp": "2024-01-01T12:00:05.000Z",
                "uuid": "assistant-msg-1",
                "cwd": "/test/project",
                "type": "assistant",
                "message": {"role": "assistant", "content": "Hello! How can I help you?", "model": "claude-3-sonnet"},
            },
        ]

    @pytest.fixture
    def temp_jsonl_file(self, tmp_path: Path, sample_jsonl_content: list[dict]) -> Path:
        """Create a temporary JSONL file with sample content."""
        jsonl_file = tmp_path / "test_session.jsonl"

        with jsonl_file.open("w") as f:
            for entry in sample_jsonl_content:
                f.write(json.dumps(entry) + "\n")

        return jsonl_file

    def test_read_conversation_success(self, temp_jsonl_file: Path):
        """Test successful reading of conversation from JSONL file."""
        reader = ClaudeCodeReader()

        conversation = reader.read_conversation(temp_jsonl_file)

        assert isinstance(conversation, ConversationHistory)
        assert conversation.session_id == "12345678-1234-1234-1234-123456789012"
        assert len(conversation.messages) == 2
        assert conversation.project_path == temp_jsonl_file.parent
        assert conversation.cwd == "/test/project"

    def test_read_conversation_file_not_found(self):
        """Test handling of non-existent JSONL file."""
        reader = ClaudeCodeReader()

        with pytest.raises(FileNotFoundError):
            reader.read_conversation(Path("/nonexistent/file.jsonl"))

    def test_read_conversation_empty_file(self, tmp_path: Path):
        """Test handling of empty JSONL file."""
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()

        reader = ClaudeCodeReader()
        conversation = reader.read_conversation(empty_file)

        # Should have empty session ID and no messages
        assert conversation.session_id == ""
        assert len(conversation.messages) == 0

    def test_extract_messages_chronological_order(self, sample_jsonl_content: list[dict]):
        """Test that messages are returned in chronological order."""
        reader = ClaudeCodeReader()

        # Reverse the order to test sorting
        reversed_content = list(reversed(sample_jsonl_content))
        messages = reader.extract_messages(reversed_content)

        assert len(messages) == 2
        assert messages[0].timestamp == "2024-01-01T12:00:00.000Z"  # Earlier
        assert messages[1].timestamp == "2024-01-01T12:00:05.000Z"  # Later

    def test_extract_messages_filters_empty_content(self):
        """Test that entries without message content are filtered out."""
        entries = [
            {
                "sessionId": "test",
                "timestamp": "2024-01-01T12:00:00.000Z",
                "uuid": "uuid1",
                "message": {},  # Empty message
            },
            {
                "sessionId": "test",
                "timestamp": "2024-01-01T12:00:01.000Z",
                "uuid": "uuid2",
                "message": {"role": "user", "content": "Valid message"},
            },
        ]

        reader = ClaudeCodeReader()
        messages = reader.extract_messages(entries)

        assert len(messages) == 1
        assert messages[0].content == "Valid message"

    def test_get_session_id_success(self, sample_jsonl_content: list[dict]):
        """Test successful extraction of session ID."""
        reader = ClaudeCodeReader()

        session_id = reader.get_session_id(sample_jsonl_content)
        assert session_id == "12345678-1234-1234-1234-123456789012"

    def test_get_session_id_not_found(self):
        """Test handling when no session ID is found."""
        entries = [{"timestamp": "2024-01-01T12:00:00.000Z", "uuid": "test"}, {"other_field": "value"}]

        reader = ClaudeCodeReader()
        session_id = reader.get_session_id(entries)
        assert session_id == ""

    def test_get_session_id_empty_list(self):
        """Test handling of empty JSONL entries list."""
        reader = ClaudeCodeReader()
        session_id = reader.get_session_id([])
        assert session_id == ""

    def test_get_session_id_multiple_same_ids(self):
        """Test handling of multiple identical session IDs (should work)."""
        valid_session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        entries = [
            {"sessionId": valid_session_id, "timestamp": "2024-01-01T12:00:00.000Z"},
            {"sessionId": valid_session_id, "timestamp": "2024-01-01T12:01:00.000Z"},
        ]

        reader = ClaudeCodeReader()

        session_id = reader.get_session_id(entries)
        assert session_id == valid_session_id

    def test_message_dataclass_fields(self, temp_jsonl_file: Path):
        """Test that Message objects have all expected fields."""
        reader = ClaudeCodeReader()
        conversation = reader.read_conversation(temp_jsonl_file)

        message = conversation.messages[0]

        assert hasattr(message, "role")
        assert hasattr(message, "content")
        assert hasattr(message, "timestamp")
        assert hasattr(message, "uuid")
        assert hasattr(message, "session_id")
        assert hasattr(message, "cwd")
        assert hasattr(message, "model")
        assert hasattr(message, "type")

        # Check specific values
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.session_id == "12345678-1234-1234-1234-123456789012"
        assert message.cwd == "/test/project"
