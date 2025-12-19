"""Tests for metrics collection."""

import threading
import time

from ccproxy.metrics import MetricsCollector, get_metrics, reset_metrics


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_initial_state(self) -> None:
        """Test that a new collector has zero counts."""
        collector = MetricsCollector()
        snapshot = collector.get_snapshot()

        assert snapshot.total_requests == 0
        assert snapshot.successful_requests == 0
        assert snapshot.failed_requests == 0
        assert snapshot.passthrough_requests == 0
        assert snapshot.requests_by_model == {}
        assert snapshot.requests_by_rule == {}

    def test_record_request(self) -> None:
        """Test recording a request with model and rule."""
        collector = MetricsCollector()

        collector.record_request(model_name="gpt-4", rule_name="token_count")

        snapshot = collector.get_snapshot()
        assert snapshot.total_requests == 1
        assert snapshot.requests_by_model == {"gpt-4": 1}
        assert snapshot.requests_by_rule == {"token_count": 1}
        assert snapshot.passthrough_requests == 0

    def test_record_passthrough_request(self) -> None:
        """Test recording a passthrough request."""
        collector = MetricsCollector()

        collector.record_request(model_name="default", is_passthrough=True)

        snapshot = collector.get_snapshot()
        assert snapshot.total_requests == 1
        assert snapshot.passthrough_requests == 1

    def test_record_success_and_failure(self) -> None:
        """Test recording success and failure events."""
        collector = MetricsCollector()

        collector.record_success()
        collector.record_success()
        collector.record_failure()

        snapshot = collector.get_snapshot()
        assert snapshot.successful_requests == 2
        assert snapshot.failed_requests == 1

    def test_multiple_requests_same_model(self) -> None:
        """Test that multiple requests to same model are aggregated."""
        collector = MetricsCollector()

        collector.record_request(model_name="gpt-4")
        collector.record_request(model_name="gpt-4")
        collector.record_request(model_name="claude")

        snapshot = collector.get_snapshot()
        assert snapshot.total_requests == 3
        assert snapshot.requests_by_model == {"gpt-4": 2, "claude": 1}

    def test_reset(self) -> None:
        """Test that reset clears all counters."""
        collector = MetricsCollector()

        collector.record_request(model_name="gpt-4", rule_name="test")
        collector.record_success()
        collector.reset()

        snapshot = collector.get_snapshot()
        assert snapshot.total_requests == 0
        assert snapshot.successful_requests == 0
        assert snapshot.requests_by_model == {}
        assert snapshot.requests_by_rule == {}

    def test_to_dict(self) -> None:
        """Test dictionary export."""
        collector = MetricsCollector()

        collector.record_request(model_name="gpt-4")
        collector.record_success()

        data = collector.to_dict()
        assert data["total_requests"] == 1
        assert data["successful_requests"] == 1
        assert data["requests_by_model"] == {"gpt-4": 1}
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_uptime_tracking(self) -> None:
        """Test that uptime is tracked."""
        collector = MetricsCollector()
        time.sleep(0.1)  # Wait a bit

        snapshot = collector.get_snapshot()
        assert snapshot.uptime_seconds >= 0.1

    def test_thread_safety(self) -> None:
        """Test that concurrent access is thread-safe."""
        collector = MetricsCollector()
        num_threads = 10
        requests_per_thread = 100

        def record_many():
            for _ in range(requests_per_thread):
                collector.record_request(model_name="test")
                collector.record_success()

        threads = [threading.Thread(target=record_many) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshot = collector.get_snapshot()
        expected = num_threads * requests_per_thread
        assert snapshot.total_requests == expected
        assert snapshot.successful_requests == expected


class TestMetricsSingleton:
    """Tests for global metrics instance."""

    def test_get_metrics_returns_same_instance(self) -> None:
        """Test that get_metrics returns singleton."""
        reset_metrics()

        m1 = get_metrics()
        m2 = get_metrics()

        assert m1 is m2

    def test_reset_metrics_clears_instance(self) -> None:
        """Test that reset_metrics creates new instance."""
        reset_metrics()

        m1 = get_metrics()
        m1.record_request(model_name="test")

        reset_metrics()
        m2 = get_metrics()

        # New instance should have fresh counts
        assert m2.get_snapshot().total_requests == 0
