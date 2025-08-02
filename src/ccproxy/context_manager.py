"""Context manager orchestrator for combining Claude Code conversations with provider metadata."""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import attrs

from ccproxy.claude_integration import (
    ClaudeCodeReader,
    ClaudeProjectLocator,
    Message,
    ProjectNotFoundError,
)
from ccproxy.provider_metadata import ProviderMetadataStore, RoutingDecision

logger = logging.getLogger(__name__)


@attrs.define(slots=True)
class ContextManager:
    """
    Orchestrates Claude Code conversation reading with provider metadata.

    This class serves as the central coordination point for:
    1. Discovering Claude Code project directories
    2. Reading conversation history from JSONL files
    3. Enriching context with provider routing history
    4. Caching for performance optimization
    """

    locator: ClaudeProjectLocator
    reader: ClaudeCodeReader
    store: ProviderMetadataStore
    cache_size: int = attrs.field(default=256)
    _cached_read_session: Any = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize the LRU cache for session data."""
        # Create a cached version of the internal implementation
        # The cache key is (session_file_str, mtime) to handle Path objects
        self._cached_read_session = lru_cache(maxsize=self.cache_size)(self._read_session_uncached)

    def _read_session_uncached(self, session_file_str: str, mtime: float) -> tuple[list[Message], str]:
        """
        Internal uncached implementation for reading session data.

        Args:
            session_file_str: String path to the session file (for cache key)
            mtime: File modification time (for cache invalidation)

        Returns:
            Tuple of (messages, session_id)
        """
        session_file = Path(session_file_str)
        logger.debug(f"Reading session from {session_file} (mtime={mtime})")

        try:
            conversation = self.reader.read_conversation(session_file)
            return conversation.messages, conversation.session_id
        except Exception as e:
            logger.error(f"Failed to read session {session_file}: {e}")
            return [], ""

    async def get_context(self, cwd: Path, chat_id: str | None = None, session_id: str | None = None) -> list[Message]:
        """
        Get conversation context for the current working directory or session ID.

        This method:
        1. Finds the Claude Code project from the working directory or session ID
        2. Locates the appropriate session file
        3. Reads the conversation (with caching)
        4. Enriches with provider routing history
        5. Returns the message list

        Args:
            cwd: Current working directory
            chat_id: Optional chat ID for future session mapping
            session_id: Optional session ID to find specific JSONL file

        Returns:
            List of conversation messages, empty list if none found
        """
        try:
            # If session_id is provided, try to find the session file directly
            if session_id:
                session_file = await self._find_session_by_id(session_id)
                if session_file:
                    loop = asyncio.get_event_loop()
                    mtime = await loop.run_in_executor(None, lambda: session_file.stat().st_mtime)
                    messages, _ = self._cached_read_session(str(session_file), mtime)

                    if messages:
                        await self._log_provider_history(session_id)
                        return messages  # type: ignore[no-any-return]

            # Fallback to directory-based discovery
            # Step 1: Find Claude Code project
            project_path = self.locator.find_project_path(cwd)

            # Step 2: Get session files
            if project_path is None:
                return []
            session_files = self.locator.get_session_files(project_path)
            if not session_files:
                logger.info(f"No session files found in {project_path}")
                return []

            # Step 3: Use the latest session file
            latest_session = session_files[-1]
            loop = asyncio.get_event_loop()
            mtime = await loop.run_in_executor(None, lambda: latest_session.stat().st_mtime)

            # Step 4: Read conversation (cached)
            messages, found_session_id = self._cached_read_session(str(latest_session), mtime)

            if not messages:
                return []

            # Step 5: Enrich with provider history (async)
            await self._log_provider_history(found_session_id)

            # TODO: Implement context window truncation based on model limits
            # For now, return all messages as-is
            return messages  # type: ignore[no-any-return]

        except ProjectNotFoundError:
            logger.debug(f"No Claude Code project found from {cwd}")
            return []
        except Exception as e:
            logger.error(f"Error getting context from {cwd}: {e}", exc_info=True)
            return []

    async def _find_session_by_id(self, session_id: str) -> Path | None:
        """
        Find a session file by its ID across all Claude Code projects.

        Args:
            session_id: The session ID to search for

        Returns:
            Path to the session file if found, None otherwise
        """
        try:
            # Search in all project directories
            if not self.locator.projects_dir.exists():
                return None

            # Look for a file named {session_id}.jsonl in any project
            for project_dir in self.locator.projects_dir.iterdir():
                if project_dir.is_dir():
                    session_file = project_dir / f"{session_id}.jsonl"
                    if session_file.exists():
                        logger.debug(f"Found session file by ID: {session_file}")
                        return session_file

            logger.debug(f"No session file found for ID: {session_id}")
            return None

        except Exception as e:
            logger.error(f"Error finding session by ID {session_id}: {e}")
            return None

    async def _log_provider_history(self, session_id: str) -> None:
        """
        Log provider routing history for debugging.

        This enriches our understanding of the conversation context
        but doesn't modify the messages themselves.
        """
        try:
            provider_history = await self.store.get_provider_history(session_id)

            if provider_history:
                logger.info(f"Session {session_id}: {len(provider_history)} routing decisions")
                # Log recent routing decisions for debugging
                for entry in provider_history[-3:]:
                    logger.debug(f"  → {entry.get('provider')}/{entry.get('model')} at {entry.get('ts', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to get provider history: {e}")

    async def record_decision(
        self,
        session_id: str,
        provider: str,
        model: str,
        request_id: str = "",
        selected_by_rule: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a routing decision for the session.

        Args:
            session_id: Claude Code session ID
            provider: Provider name (e.g., "anthropic")
            model: Model name (e.g., "claude-3-5-sonnet")
            request_id: Optional request identifier
            selected_by_rule: Rule that triggered this routing
            metadata: Additional context about the decision
        """
        if not session_id:
            logger.warning("Cannot record decision without session_id")
            return

        decision = RoutingDecision(
            provider=provider,
            model=model,
            session_id=session_id,
            request_id=request_id,
            selected_by_rule=selected_by_rule,
            metadata=metadata or {},
        )

        logger.info(
            f"Recording: {provider}/{model} for session {session_id[:8]}... (rule: {selected_by_rule or 'default'})"
        )

        try:
            await self.store.record_routing_decision(decision)
        except Exception as e:
            logger.error(f"Failed to record routing decision: {e}")

    def clear_cache(self) -> None:
        """Clear the session cache."""
        self._cached_read_session.cache_clear()
        logger.info("Context cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        info = self._cached_read_session.cache_info()
        total_requests = info.hits + info.misses

        return {
            "hits": info.hits,
            "misses": info.misses,
            "maxsize": info.maxsize,
            "currsize": info.currsize,
            "hit_rate": (round(info.hits / total_requests, 3) if total_requests > 0 else 0.0),
            "total_requests": total_requests,
        }

    def cleanup(self) -> None:
        """Clean up resources."""
        self.clear_cache()
        self.store.cleanup()
