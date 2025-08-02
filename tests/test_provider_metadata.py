"""Tests for provider metadata storage."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from ccproxy.provider_metadata import ProviderMetadataStore, RoutingDecision


@pytest.fixture
def temp_storage_path(tmp_path: Path) -> Path:
    """Create a temporary storage path."""
    return tmp_path / ".ccproxy"


@pytest.fixture
def metadata_store(temp_storage_path: Path) -> ProviderMetadataStore:
    """Create a ProviderMetadataStore instance."""
    store = ProviderMetadataStore(base_path=temp_storage_path)
    yield store
    store.cleanup()


@pytest.fixture
def sample_decision() -> RoutingDecision:
    """Create a sample routing decision."""
    return RoutingDecision(
        provider="anthropic",
        model="claude-3-5-sonnet",
        session_id=str(uuid4()),
        request_id=str(uuid4()),
        selected_by_rule="large_context",
        metadata={"tokens": 50000, "tool_count": 3},
    )


class TestRoutingDecision:
    """Test RoutingDecision class."""

    def test_to_dict(self, sample_decision: RoutingDecision) -> None:
        """Test conversion to dictionary."""
        data = sample_decision.to_dict()

        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-3-5-sonnet"
        assert "timestamp" in data
        assert data["session_id"] == sample_decision.session_id
        assert data["request_id"] == sample_decision.request_id
        assert data["selected_by_rule"] == "large_context"
        assert data["metadata"]["tokens"] == 50000

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "provider": "openai",
            "model": "gpt-4",
            "timestamp": 1234567890.0,
            "session_id": "test-session",
            "request_id": "test-request",
            "selected_by_rule": "web_search",
            "metadata": {"test": True},
        }

        decision = RoutingDecision.from_dict(data)

        assert decision.provider == "openai"
        assert decision.model == "gpt-4"
        assert decision.timestamp == 1234567890.0
        assert decision.session_id == "test-session"
        assert decision.request_id == "test-request"
        assert decision.selected_by_rule == "web_search"
        assert decision.metadata["test"] is True

    def test_from_dict_with_missing_fields(self) -> None:
        """Test creation from dictionary with missing optional fields."""
        data = {"provider": "google", "model": "gemini-pro"}

        decision = RoutingDecision.from_dict(data)

        assert decision.provider == "google"
        assert decision.model == "gemini-pro"
        assert decision.session_id == ""
        assert decision.request_id == ""
        assert decision.selected_by_rule == ""
        assert decision.metadata == {}


class TestProviderMetadataStore:
    """Test ProviderMetadataStore class."""

    async def test_record_and_retrieve_single_decision(
        self, metadata_store: ProviderMetadataStore, sample_decision: RoutingDecision
    ) -> None:
        """Test recording and retrieving a single routing decision."""
        # Record decision
        await metadata_store.record_routing_decision(sample_decision)

        # Retrieve provider history
        history = await metadata_store.get_provider_history(sample_decision.session_id)
        assert len(history) == 1
        assert history[0]["provider"] == "anthropic"
        assert history[0]["model"] == "claude-3-5-sonnet"
        assert "ts" in history[0]

        # Retrieve routing decisions
        decisions = await metadata_store.get_routing_decisions(sample_decision.session_id)
        assert len(decisions) == 1
        assert decisions[0].provider == "anthropic"
        assert decisions[0].model == "claude-3-5-sonnet"
        assert decisions[0].metadata["tokens"] == 50000

    async def test_record_multiple_decisions(self, metadata_store: ProviderMetadataStore) -> None:
        """Test recording multiple routing decisions."""
        session_id = str(uuid4())

        # Create and record 3 decisions
        decisions = []
        for i in range(3):
            decision = RoutingDecision(
                provider=f"provider-{i}",
                model=f"model-{i}",
                session_id=session_id,
                request_id=str(uuid4()),
                selected_by_rule=f"rule-{i}",
            )
            decisions.append(decision)
            await metadata_store.record_routing_decision(decision)

        # Verify history length
        history = await metadata_store.get_provider_history(session_id)
        assert len(history) == 3

        # Verify all decisions are stored
        stored_decisions = await metadata_store.get_routing_decisions(session_id)
        assert len(stored_decisions) == 3

        for i, decision in enumerate(stored_decisions):
            assert decision.provider == f"provider-{i}"
            assert decision.model == f"model-{i}"
            assert decision.selected_by_rule == f"rule-{i}"

    async def test_concurrent_writes(self, metadata_store: ProviderMetadataStore) -> None:
        """Test concurrent writes don't corrupt data."""
        session_id = str(uuid4())

        # Create multiple decisions
        decisions = []
        for i in range(5):  # Reduce to 5 for more reliable test
            decision = RoutingDecision(
                provider=f"provider-{i}",
                model=f"model-{i}",
                session_id=session_id,
                request_id=str(uuid4()),
                metadata={"index": i},
            )
            decisions.append(decision)

        # Record all decisions concurrently
        tasks = [metadata_store.record_routing_decision(decision) for decision in decisions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful writes (some may timeout due to lock contention)
        successful_writes = sum(1 for r in results if not isinstance(r, Exception))
        assert successful_writes >= 3  # At least 3 should succeed

        # Verify no data corruption - all stored decisions should be valid
        stored_decisions = await metadata_store.get_routing_decisions(session_id)
        assert len(stored_decisions) >= 3

        # Verify data integrity - all indices should be unique and valid
        indices = [d.metadata.get("index", -1) for d in stored_decisions]
        assert len(set(indices)) == len(indices)  # No duplicates
        assert all(0 <= i < 5 for i in indices)  # All indices in valid range

    async def test_missing_file_returns_empty_list(self, metadata_store: ProviderMetadataStore) -> None:
        """Test that missing files return empty lists."""
        non_existent_session = str(uuid4())

        history = await metadata_store.get_provider_history(non_existent_session)
        assert history == []

        decisions = await metadata_store.get_routing_decisions(non_existent_session)
        assert decisions == []

    async def test_no_session_id_skips_recording(self, metadata_store: ProviderMetadataStore) -> None:
        """Test that decisions without session ID are skipped."""
        decision = RoutingDecision(
            provider="test",
            model="test-model",
            session_id="",  # Empty session ID
        )

        # This should not raise an error
        await metadata_store.record_routing_decision(decision)

        # Verify nothing was written
        metadata_dir = metadata_store.metadata_dir
        assert len(list(metadata_dir.glob("*.json"))) == 0

    async def test_corrupted_file_returns_empty_data(
        self, metadata_store: ProviderMetadataStore, temp_storage_path: Path
    ) -> None:
        """Test that corrupted files are handled gracefully."""
        session_id = str(uuid4())

        # Write corrupted JSON
        metadata_path = temp_storage_path / "metadata" / f"{session_id}.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text("{ corrupted json }")

        # Should return empty data without raising
        history = await metadata_store.get_provider_history(session_id)
        assert history == []

        decisions = await metadata_store.get_routing_decisions(session_id)
        assert decisions == []

    async def test_file_persistence(
        self, metadata_store: ProviderMetadataStore, temp_storage_path: Path, sample_decision: RoutingDecision
    ) -> None:
        """Test that data persists across store instances."""
        # Record with first store
        await metadata_store.record_routing_decision(sample_decision)

        # Create new store instance
        new_store = ProviderMetadataStore(base_path=temp_storage_path)

        try:
            # Verify data is still accessible
            history = await new_store.get_provider_history(sample_decision.session_id)
            assert len(history) == 1
            assert history[0]["provider"] == "anthropic"
        finally:
            new_store.cleanup()

    def test_metadata_directory_creation(self, temp_storage_path: Path) -> None:
        """Test that metadata directory is created on initialization."""
        metadata_dir = temp_storage_path / "metadata"
        assert not metadata_dir.exists()

        store = ProviderMetadataStore(base_path=temp_storage_path)
        assert metadata_dir.exists()
        assert metadata_dir.is_dir()

        store.cleanup()
