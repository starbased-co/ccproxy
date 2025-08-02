"""Integration with Claude Code's JSONL conversation storage system.

This module provides functionality to discover and read Claude Code project directories
and session files for context preservation across provider routing.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when Claude Code project directory cannot be found."""

    pass


@dataclass
class ProjectInfo:
    """Information about a discovered Claude Code project."""

    project_path: Path
    project_name: str
    session_files: list[Path]
    last_modified: float


@dataclass
class Message:
    """Represents a conversation message extracted from JSONL."""

    role: str
    content: Any
    timestamp: str
    uuid: str
    session_id: str
    cwd: str | None = None
    model: str | None = None
    type: str | None = None


@dataclass
class ConversationHistory:
    """Complete conversation history reconstructed from JSONL."""

    session_id: str
    messages: list[Message]
    project_path: Path
    cwd: str | None = None


class ClaudeProjectLocator:
    """Service for discovering Claude Code project directories and session files."""

    def __init__(self, claude_dir: Path | None = None) -> None:
        """Initialize the project locator.

        Args:
            claude_dir: Override Claude Code directory (defaults to ~/.claude)
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"
        self._cache: dict[str, ProjectInfo] = {}

    def find_project_path(self, cwd: Path) -> Path | None:
        """Find the Claude Code project directory for a given working directory.

        Walks upward from cwd until reaching the root, then checks if a corresponding
        Claude Code project directory exists in ~/.claude/projects/.

        Args:
            cwd: Current working directory to search from

        Returns:
            Path to the Claude Code project directory, or None if not found
        """
        if not self.projects_dir.exists():
            logger.debug(f"Claude Code projects directory not found: {self.projects_dir}")
            return None

        # Normalize and resolve the path
        cwd = cwd.resolve()

        # Try current directory and walk upward
        current_path = cwd
        while True:
            # Convert path to Claude Code project name format
            # Replace path separators with double dashes and prefix with dash
            path_str = str(current_path)
            if path_str == "/":
                project_name = "-"
            else:
                # Remove leading slash and replace remaining slashes with double dashes
                path_without_leading_slash = path_str.lstrip("/")
                project_name = "-" + path_without_leading_slash.replace("/", "--")
            candidate_project_path = self.projects_dir / project_name

            if candidate_project_path.exists() and candidate_project_path.is_dir():
                logger.debug(f"Found Claude Code project: {candidate_project_path}")
                return candidate_project_path

            # Try parent directory
            parent = current_path.parent
            if parent == current_path:  # Reached root
                break
            current_path = parent

        logger.debug(f"No Claude Code project found for directory: {cwd}")
        return None

    def get_session_files(self, project_path: Path) -> list[Path]:
        """Get all JSONL session files in a project directory.

        Args:
            project_path: Path to the Claude Code project directory

        Returns:
            List of JSONL session files sorted by modification time (newest first)
        """
        if not project_path.exists() or not project_path.is_dir():
            return []

        session_files = []
        try:
            for file_path in project_path.iterdir():
                if file_path.is_file() and file_path.suffix == ".jsonl":
                    session_files.append(file_path)

            # Sort by modification time, newest first
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        except (OSError, PermissionError) as e:
            logger.warning(f"Error reading session files from {project_path}: {e}")
            return []

        return session_files

    def cache_project_info(self, project_path: Path) -> ProjectInfo:
        """Cache project information for performance optimization.

        Args:
            project_path: Path to the Claude Code project directory

        Returns:
            ProjectInfo with cached data
        """
        cache_key = str(project_path)

        # Check if cache is still valid (based on directory modification time)
        try:
            current_mtime = project_path.stat().st_mtime
            cached_info = self._cache.get(cache_key)

            if cached_info and cached_info.last_modified >= current_mtime:
                return cached_info

        except (OSError, PermissionError):
            # If we can't stat the directory, don't use cache
            pass

        # Update cache
        session_files = self.get_session_files(project_path)
        project_info = ProjectInfo(
            project_path=project_path,
            project_name=project_path.name,
            session_files=session_files,
            last_modified=time.time(),
        )

        self._cache[cache_key] = project_info
        return project_info

    def discover_for_working_directory(self, cwd: str | Path) -> ProjectInfo | None:
        """Discover Claude Code project for a given working directory.

        Args:
            cwd: Working directory path (can be string or Path)

        Returns:
            ProjectInfo if found, None otherwise

        Raises:
            ProjectNotFoundError: If no Claude Code project can be found
        """
        cwd_path = Path(cwd) if isinstance(cwd, str) else cwd

        project_path = self.find_project_path(cwd_path)
        if not project_path:
            raise ProjectNotFoundError(f"No Claude Code project found for directory: {cwd_path}")

        return self.cache_project_info(project_path)


class ClaudeCodeReader:
    """Parser for Claude Code JSONL files to reconstruct conversation history."""

    def read_conversation(self, session_file: Path) -> ConversationHistory:
        """Read and parse a JSONL session file into conversation history.

        Args:
            session_file: Path to the JSONL session file

        Returns:
            ConversationHistory with parsed messages

        Raises:
            FileNotFoundError: If session file doesn't exist
        """
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        jsonl_entries = []
        with session_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    jsonl_entries.append(entry)

        session_id = self.get_session_id(jsonl_entries)
        messages = self.extract_messages(jsonl_entries)

        # Extract CWD from first entry if available
        cwd = jsonl_entries[0].get("cwd") if jsonl_entries else None

        return ConversationHistory(
            session_id=session_id,
            messages=messages,
            project_path=session_file.parent,
            cwd=cwd,
        )

    def extract_messages(self, jsonl_entries: list[dict[str, Any]]) -> list[Message]:
        """Extract and convert JSONL entries into Message objects.

        Args:
            jsonl_entries: List of parsed JSONL entries

        Returns:
            List of Message objects in chronological order
        """
        messages = []

        for entry in jsonl_entries:
            # Extract common fields
            session_id = entry.get("sessionId", "")
            timestamp = entry.get("timestamp", "")
            uuid = entry.get("uuid", "")
            cwd = entry.get("cwd")
            msg_type = entry.get("type", "")

            # Extract message content
            message_data = entry.get("message", {})
            if not message_data:
                continue

            role = message_data.get("role", "")
            content = message_data.get("content", "")
            model = message_data.get("model")

            if role and content:
                message = Message(
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    uuid=uuid,
                    session_id=session_id,
                    cwd=cwd,
                    model=model,
                    type=msg_type,
                )
                messages.append(message)

        # Sort by timestamp to ensure chronological order
        messages.sort(key=lambda m: m.timestamp)
        return messages

    def get_session_id(self, jsonl_entries: list[dict[str, Any]]) -> str:
        """Extract session ID from JSONL entries.

        Args:
            jsonl_entries: List of parsed JSONL entries

        Returns:
            Session ID string from the first entry containing one
        """
        for entry in jsonl_entries:
            session_id = entry.get("sessionId")
            if isinstance(session_id, str) and session_id:
                return session_id
        return ""
