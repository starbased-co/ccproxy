"""Tests for cost tracking functionality."""

import pytest

from ccproxy.metrics import (
    DEFAULT_MODEL_PRICING,
    CostSnapshot,
    MetricsCollector,
    get_metrics,
    reset_metrics,
)


class TestCostCalculation:
    """Tests for cost calculation."""

    def setup_method(self) -> None:
        """Reset metrics before each test."""
        reset_metrics()

    def test_calculate_cost_known_model(self) -> None:
        """Test cost calculation for known models."""
        metrics = MetricsCollector()

        # Claude 3.5 Sonnet: $3/M input, $15/M output
        cost = metrics.calculate_cost("claude-3-5-sonnet", 1000, 500)

        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert cost == pytest.approx(expected)

    def test_calculate_cost_unknown_model(self) -> None:
        """Test cost calculation uses default for unknown models."""
        metrics = MetricsCollector()

        cost = metrics.calculate_cost("unknown-model-xyz", 1000, 500)

        # Default: $1/M input, $3/M output
        expected = (1000 / 1_000_000) * 1.0 + (500 / 1_000_000) * 3.0
        assert cost == pytest.approx(expected)

    def test_calculate_cost_partial_match(self) -> None:
        """Test cost calculation with partial model name match."""
        metrics = MetricsCollector()

        # Should match "gpt-4" in the pricing table
        cost = metrics.calculate_cost("openai/gpt-4-1106-preview", 1000, 500)

        # GPT-4: $30/M input, $60/M output
        expected = (1000 / 1_000_000) * 30.0 + (500 / 1_000_000) * 60.0
        assert cost == pytest.approx(expected)

    def test_custom_pricing(self) -> None:
        """Test custom pricing overrides default."""
        metrics = MetricsCollector()

        metrics.set_pricing("my-custom-model", input_price=5.0, output_price=10.0)
        cost = metrics.calculate_cost("my-custom-model", 1000, 500)

        expected = (1000 / 1_000_000) * 5.0 + (500 / 1_000_000) * 10.0
        assert cost == pytest.approx(expected)


class TestCostRecording:
    """Tests for cost recording."""

    def setup_method(self) -> None:
        """Reset metrics before each test."""
        reset_metrics()

    def test_record_cost(self) -> None:
        """Test recording cost updates totals."""
        metrics = MetricsCollector()

        cost = metrics.record_cost("claude-3-5-sonnet", 10000, 5000)

        snapshot = metrics.get_cost_snapshot()
        assert snapshot.total_cost == pytest.approx(cost)
        assert "claude-3-5-sonnet" in snapshot.cost_by_model

    def test_record_cost_with_user(self) -> None:
        """Test recording cost with user tracking."""
        metrics = MetricsCollector()

        metrics.record_cost("claude-3-5-sonnet", 10000, 5000, user="user-123")

        snapshot = metrics.get_cost_snapshot()
        assert "user-123" in snapshot.cost_by_user
        assert snapshot.cost_by_user["user-123"] > 0

    def test_record_cost_accumulates(self) -> None:
        """Test that costs accumulate across requests."""
        metrics = MetricsCollector()

        cost1 = metrics.record_cost("claude-3-5-sonnet", 10000, 5000)
        cost2 = metrics.record_cost("claude-3-5-sonnet", 10000, 5000)

        snapshot = metrics.get_cost_snapshot()
        assert snapshot.total_cost == pytest.approx(cost1 + cost2)

    def test_record_cost_token_tracking(self) -> None:
        """Test that tokens are tracked."""
        metrics = MetricsCollector()

        metrics.record_cost("gpt-4", 1000, 500)
        metrics.record_cost("gpt-4", 2000, 1000)

        snapshot = metrics.get_cost_snapshot()
        assert snapshot.total_input_tokens == 3000
        assert snapshot.total_output_tokens == 1500


class TestBudgetAlerts:
    """Tests for budget alerts."""

    def setup_method(self) -> None:
        """Reset metrics before each test."""
        reset_metrics()

    def test_budget_warning_at_75_percent(self) -> None:
        """Test budget notice at 75%."""
        metrics = MetricsCollector()
        metrics.set_budget(total=1.0)  # $1 budget

        # Record cost that exceeds 75%
        metrics.record_cost("gpt-4", 30000, 0)  # ~$0.90

        snapshot = metrics.get_cost_snapshot()
        assert any("NOTICE" in alert for alert in snapshot.budget_alerts)

    def test_budget_warning_at_90_percent(self) -> None:
        """Test budget warning at 90%."""
        metrics = MetricsCollector()
        metrics.set_budget(total=0.10)  # $0.10 budget

        # Record cost that exceeds 90%
        metrics.record_cost("gpt-4", 3100, 0)  # ~$0.093

        snapshot = metrics.get_cost_snapshot()
        assert any("WARNING" in alert for alert in snapshot.budget_alerts)

    def test_budget_exceeded(self) -> None:
        """Test budget exceeded alert."""
        metrics = MetricsCollector()
        metrics.set_budget(total=0.01)  # $0.01 budget

        # Record cost that exceeds budget
        metrics.record_cost("gpt-4", 1000, 0)  # ~$0.03

        snapshot = metrics.get_cost_snapshot()
        assert any("EXCEEDED" in alert for alert in snapshot.budget_alerts)

    def test_per_model_budget(self) -> None:
        """Test per-model budget tracking."""
        metrics = MetricsCollector()
        metrics.set_budget(per_model={"gpt-4": 0.01})

        metrics.record_cost("gpt-4", 1000, 0)  # ~$0.03

        snapshot = metrics.get_cost_snapshot()
        assert any("gpt-4" in alert for alert in snapshot.budget_alerts)

    def test_per_user_budget(self) -> None:
        """Test per-user budget tracking."""
        metrics = MetricsCollector()
        metrics.set_budget(per_user={"user-123": 0.01})

        metrics.record_cost("gpt-4", 1000, 0, user="user-123")

        snapshot = metrics.get_cost_snapshot()
        assert any("user-123" in alert for alert in snapshot.budget_alerts)

    def test_alert_callback(self) -> None:
        """Test alert callback is called."""
        metrics = MetricsCollector()
        alerts_received: list[str] = []

        metrics.set_alert_callback(lambda msg: alerts_received.append(msg))
        metrics.set_budget(total=0.01)

        metrics.record_cost("gpt-4", 1000, 0)

        assert len(alerts_received) > 0


class TestCostSnapshot:
    """Tests for cost snapshot."""

    def setup_method(self) -> None:
        """Reset metrics before each test."""
        reset_metrics()

    def test_cost_snapshot_fields(self) -> None:
        """Test CostSnapshot contains all expected fields."""
        metrics = MetricsCollector()
        metrics.record_cost("claude-3-5-sonnet", 1000, 500, user="test-user")

        snapshot = metrics.get_cost_snapshot()

        assert isinstance(snapshot, CostSnapshot)
        assert snapshot.total_cost > 0
        assert "claude-3-5-sonnet" in snapshot.cost_by_model
        assert "test-user" in snapshot.cost_by_user
        assert snapshot.total_input_tokens == 1000
        assert snapshot.total_output_tokens == 500

    def test_metrics_snapshot_includes_cost(self) -> None:
        """Test MetricsSnapshot includes cost data."""
        metrics = MetricsCollector()
        metrics.record_cost("gpt-4", 1000, 500)

        snapshot = metrics.get_snapshot()

        assert snapshot.total_cost > 0
        assert "gpt-4" in snapshot.cost_by_model

    def test_to_dict_includes_cost(self) -> None:
        """Test to_dict includes cost data."""
        metrics = MetricsCollector()
        metrics.record_cost("gpt-4", 1000, 500, user="test")

        data = metrics.to_dict()

        assert "total_cost_usd" in data
        assert "cost_by_model" in data
        assert "cost_by_user" in data


class TestCostReset:
    """Tests for cost reset."""

    def setup_method(self) -> None:
        """Reset metrics before each test."""
        reset_metrics()

    def test_reset_clears_cost(self) -> None:
        """Test reset clears all cost data."""
        metrics = MetricsCollector()
        metrics.record_cost("gpt-4", 1000, 500, user="test")
        metrics.set_budget(total=1.0)

        metrics.reset()

        snapshot = metrics.get_cost_snapshot()
        assert snapshot.total_cost == 0
        assert len(snapshot.cost_by_model) == 0
        assert len(snapshot.cost_by_user) == 0
        assert snapshot.total_input_tokens == 0
        assert snapshot.total_output_tokens == 0
        assert len(snapshot.budget_alerts) == 0
