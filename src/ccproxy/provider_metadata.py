"""Provider metadata storage for tracking routing decisions."""

import asyncio
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import attrs
import fasteners


@attrs.define(slots=True)
class RoutingDecision:
    """Represents a single routing decision."""

    provider: str
    model: str
    timestamp: float = attrs.field(factory=lambda: time.time())
    session_id: str = ""
    request_id: str = ""
    selected_by_rule: str = ""
    metadata: dict[str, Any] = attrs.field(factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "selected_by_rule": self.selected_by_rule,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingDecision":
        """Create from dictionary."""
        return cls(
            provider=data["provider"],
            model=data["model"],
            timestamp=data.get("timestamp", time.time()),
            session_id=data.get("session_id", ""),
            request_id=data.get("request_id", ""),
            selected_by_rule=data.get("selected_by_rule", ""),
            metadata=data.get("metadata", {}),
        )


@attrs.define(slots=True)
class ProviderMetadataStore:
    """Lightweight storage for provider routing decisions."""

    base_path: Path = attrs.field(converter=Path)
    _executor: ThreadPoolExecutor = attrs.field(init=False, factory=lambda: ThreadPoolExecutor(max_workers=2))
    _lock_timeout: int = attrs.field(default=5)
    metadata_dir: Path = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        """Ensure the metadata directory exists."""
        self.metadata_dir = self.base_path / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_metadata_path(self, session_id: str) -> Path:
        """Get the metadata file path for a session."""
        return self.metadata_dir / f"{session_id}.json"

    def _read_metadata_sync(self, session_id: str) -> dict[str, Any]:
        """Synchronously read metadata from file."""
        file_path = self._get_metadata_path(session_id)

        if not file_path.exists():
            return {"provider_history": [], "routing_decisions": []}

        try:
            with file_path.open("r") as f:
                data = json.load(f)
                return data  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            # Return empty structure on read errors
            return {"provider_history": [], "routing_decisions": []}

    def _write_metadata_sync(self, session_id: str, data: dict[str, Any]) -> None:
        """Synchronously write metadata to file with atomic operation."""
        file_path = self._get_metadata_path(session_id)

        # Use atomic write via tempfile + Path.replace
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.metadata_dir, prefix=f".{session_id}.", suffix=".tmp", delete=False
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, sort_keys=True)
            tmp_path = Path(tmp_file.name)

        # Atomic replacement
        tmp_path.replace(file_path)

    async def record_routing_decision(self, decision: RoutingDecision) -> None:
        """Record a routing decision for a session."""
        session_id = decision.session_id
        if not session_id:
            return  # Skip if no session ID

        file_path = self._get_metadata_path(session_id)

        # Use file lock to prevent concurrent writes
        lock = fasteners.InterProcessLock(f"{file_path}.lock")

        def _record() -> None:
            acquired = lock.acquire(timeout=self._lock_timeout)
            if not acquired:
                raise TimeoutError(f"Failed to acquire lock for session {session_id}")
            try:
                # Read existing data
                data = self._read_metadata_sync(session_id)

                # Add new routing decision
                data["routing_decisions"].append(decision.to_dict())

                # Update provider history
                provider_entry = {
                    "provider": decision.provider,
                    "model": decision.model,
                    "ts": int(decision.timestamp * 1000),  # Convert to milliseconds
                }
                data["provider_history"].append(provider_entry)

                # Write back atomically
                self._write_metadata_sync(session_id, data)
            finally:
                lock.release()

        # Run in executor to avoid blocking
        await asyncio.get_event_loop().run_in_executor(self._executor, _record)

    async def get_provider_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get provider history for a session."""
        if not session_id:
            return []

        def _get_history() -> list[dict[str, Any]]:
            data = self._read_metadata_sync(session_id)
            history = data.get("provider_history", [])
            return history  # type: ignore[no-any-return]

        # Run in executor for non-blocking reads
        return await asyncio.get_event_loop().run_in_executor(self._executor, _get_history)

    async def get_routing_decisions(self, session_id: str) -> list[RoutingDecision]:
        """Get all routing decisions for a session."""
        if not session_id:
            return []

        def _get_decisions() -> list[RoutingDecision]:
            data = self._read_metadata_sync(session_id)
            decisions = []
            for decision_data in data.get("routing_decisions", []):
                try:
                    decisions.append(RoutingDecision.from_dict(decision_data))
                except (KeyError, TypeError):
                    # Skip malformed entries
                    continue
            return decisions

        # Run in executor for non-blocking reads
        return await asyncio.get_event_loop().run_in_executor(self._executor, _get_decisions)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._executor.shutdown(wait=True)
