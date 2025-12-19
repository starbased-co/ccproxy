"""Tests for A/B testing framework."""

import time

import pytest

from ccproxy.ab_testing import (
    ABExperiment,
    ABTestingManager,
    ExperimentResult,
    ExperimentVariant,
    ab_testing_hook,
    get_ab_manager,
    reset_ab_manager,
)


class TestExperimentVariant:
    """Tests for experiment variants."""

    def test_variant_creation(self) -> None:
        """Test creating a variant."""
        variant = ExperimentVariant(
            name="control",
            model="gpt-4",
            weight=1.0,
        )
        assert variant.name == "control"
        assert variant.model == "gpt-4"
        assert variant.weight == 1.0
        assert variant.enabled is True


class TestABExperiment:
    """Tests for A/B experiment."""

    def test_create_experiment(self) -> None:
        """Test creating an experiment."""
        variants = [
            ExperimentVariant(name="control", model="gpt-4"),
            ExperimentVariant(name="treatment", model="gpt-3.5-turbo"),
        ]
        experiment = ABExperiment("exp-1", "Test Experiment", variants)

        assert experiment.experiment_id == "exp-1"
        assert experiment.name == "Test Experiment"
        assert len(experiment.variants) == 2

    def test_assign_variant_random(self) -> None:
        """Test random variant assignment."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4"),
            ExperimentVariant(name="B", model="gpt-3.5"),
        ]
        experiment = ABExperiment("exp-1", "Test", variants, sticky_sessions=False)

        # Should assign a valid variant
        variant = experiment.assign_variant()
        assert variant.name in ["A", "B"]

    def test_assign_variant_sticky_session(self) -> None:
        """Test sticky session variant assignment."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4"),
            ExperimentVariant(name="B", model="gpt-3.5"),
        ]
        experiment = ABExperiment("exp-1", "Test", variants, sticky_sessions=True)

        # Same user should always get same variant
        user_id = "user-123"
        variant1 = experiment.assign_variant(user_id)
        variant2 = experiment.assign_variant(user_id)
        variant3 = experiment.assign_variant(user_id)

        assert variant1.name == variant2.name == variant3.name

    def test_assign_variant_different_users(self) -> None:
        """Test different users can get different variants."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4", weight=1.0),
            ExperimentVariant(name="B", model="gpt-3.5", weight=1.0),
        ]
        experiment = ABExperiment("exp-1", "Test", variants, sticky_sessions=True)

        # Check multiple users (at least some should differ)
        assignments = set()
        for i in range(100):
            variant = experiment.assign_variant(f"user-{i}")
            assignments.add(variant.name)

        # With 50/50 weight, both variants should be assigned
        assert len(assignments) == 2

    def test_assign_variant_respects_weights(self) -> None:
        """Test variant assignment respects weights."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4", weight=9.0),  # 90%
            ExperimentVariant(name="B", model="gpt-3.5", weight=1.0),  # 10%
        ]
        experiment = ABExperiment("exp-1", "Test", variants, sticky_sessions=False)

        # Count assignments
        counts = {"A": 0, "B": 0}
        for _ in range(1000):
            variant = experiment.assign_variant()
            counts[variant.name] += 1

        # A should have significantly more assignments
        assert counts["A"] > counts["B"] * 5

    def test_assign_variant_no_enabled(self) -> None:
        """Test error when no variants enabled."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4", enabled=False),
        ]
        experiment = ABExperiment("exp-1", "Test", variants)

        with pytest.raises(ValueError, match="No enabled variants"):
            experiment.assign_variant()


class TestExperimentResults:
    """Tests for recording and analyzing results."""

    def test_record_result(self) -> None:
        """Test recording a result."""
        variants = [ExperimentVariant(name="A", model="gpt-4")]
        experiment = ABExperiment("exp-1", "Test", variants)

        result = ExperimentResult(
            variant_name="A",
            model="gpt-4",
            latency_ms=150.0,
            input_tokens=100,
            output_tokens=50,
            cost=0.01,
            success=True,
        )
        experiment.record_result(result)

        stats = experiment.get_variant_stats("A")
        assert stats is not None
        assert stats.request_count == 1
        assert stats.success_count == 1

    def test_variant_stats_calculation(self) -> None:
        """Test statistics calculation."""
        variants = [ExperimentVariant(name="A", model="gpt-4")]
        experiment = ABExperiment("exp-1", "Test", variants)

        # Record multiple results
        for i in range(100):
            result = ExperimentResult(
                variant_name="A",
                model="gpt-4",
                latency_ms=100 + i,  # 100-199ms
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
                success=i < 90,  # 90% success rate
            )
            experiment.record_result(result)

        stats = experiment.get_variant_stats("A")
        assert stats is not None
        assert stats.request_count == 100
        assert stats.success_count == 90
        assert stats.failure_count == 10
        assert stats.success_rate == 0.9
        assert 140 <= stats.avg_latency_ms <= 160  # ~149.5
        assert stats.total_cost == pytest.approx(1.0)

    def test_variant_stats_empty(self) -> None:
        """Test stats for variant with no results."""
        variants = [ExperimentVariant(name="A", model="gpt-4")]
        experiment = ABExperiment("exp-1", "Test", variants)

        stats = experiment.get_variant_stats("A")
        assert stats is not None
        assert stats.request_count == 0


class TestExperimentSummary:
    """Tests for experiment summary."""

    def test_summary_basic(self) -> None:
        """Test basic summary."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4"),
            ExperimentVariant(name="B", model="gpt-3.5"),
        ]
        experiment = ABExperiment("exp-1", "Test", variants)

        summary = experiment.get_summary()

        assert summary.experiment_id == "exp-1"
        assert summary.name == "Test"
        assert len(summary.variants) == 2
        assert summary.total_requests == 0

    def test_summary_with_winner(self) -> None:
        """Test summary determines winner."""
        variants = [
            ExperimentVariant(name="A", model="gpt-4"),
            ExperimentVariant(name="B", model="gpt-3.5"),
        ]
        experiment = ABExperiment("exp-1", "Test", variants)

        # A: 95% success
        for _ in range(100):
            experiment.record_result(ExperimentResult(
                variant_name="A", model="gpt-4",
                latency_ms=100, input_tokens=100, output_tokens=50,
                cost=0.01, success=True,
            ))
        for _ in range(5):
            experiment.record_result(ExperimentResult(
                variant_name="A", model="gpt-4",
                latency_ms=100, input_tokens=100, output_tokens=50,
                cost=0.01, success=False,
            ))

        # B: 80% success
        for _ in range(80):
            experiment.record_result(ExperimentResult(
                variant_name="B", model="gpt-3.5",
                latency_ms=100, input_tokens=100, output_tokens=50,
                cost=0.01, success=True,
            ))
        for _ in range(20):
            experiment.record_result(ExperimentResult(
                variant_name="B", model="gpt-3.5",
                latency_ms=100, input_tokens=100, output_tokens=50,
                cost=0.01, success=False,
            ))

        summary = experiment.get_summary()

        assert summary.winner == "A"
        assert summary.confidence > 0


class TestABTestingManager:
    """Tests for A/B testing manager."""

    def setup_method(self) -> None:
        """Reset manager before each test."""
        reset_ab_manager()

    def test_create_experiment(self) -> None:
        """Test creating experiment via manager."""
        manager = ABTestingManager()
        variants = [ExperimentVariant(name="A", model="gpt-4")]

        experiment = manager.create_experiment("exp-1", "Test", variants)

        assert manager.get_experiment("exp-1") == experiment

    def test_active_experiment(self) -> None:
        """Test active experiment management."""
        manager = ABTestingManager()
        variants = [ExperimentVariant(name="A", model="gpt-4")]

        manager.create_experiment("exp-1", "Test", variants, activate=True)

        assert manager.get_active_experiment() is not None
        assert manager.get_active_experiment().experiment_id == "exp-1"

    def test_list_experiments(self) -> None:
        """Test listing experiments."""
        manager = ABTestingManager()

        manager.create_experiment("exp-1", "Test 1", [ExperimentVariant("A", "gpt-4")])
        manager.create_experiment("exp-2", "Test 2", [ExperimentVariant("B", "gpt-3.5")])

        experiments = manager.list_experiments()
        assert set(experiments) == {"exp-1", "exp-2"}

    def test_delete_experiment(self) -> None:
        """Test deleting experiment."""
        manager = ABTestingManager()
        manager.create_experiment("exp-1", "Test", [ExperimentVariant("A", "gpt-4")])

        deleted = manager.delete_experiment("exp-1")

        assert deleted is True
        assert manager.get_experiment("exp-1") is None


class TestABTestingHook:
    """Tests for A/B testing hook."""

    def setup_method(self) -> None:
        """Reset manager before each test."""
        reset_ab_manager()

    def test_hook_no_active_experiment(self) -> None:
        """Test hook with no active experiment."""
        data = {"model": "gpt-4", "messages": []}
        result = ab_testing_hook(data, {})
        assert result["model"] == "gpt-4"

    def test_hook_assigns_variant(self) -> None:
        """Test hook assigns variant and modifies model."""
        manager = get_ab_manager()
        manager.create_experiment(
            "exp-1", "Test",
            [ExperimentVariant(name="treatment", model="gpt-3.5-turbo")],
            activate=True,
        )

        data = {"model": "gpt-4", "messages": []}
        result = ab_testing_hook(data, {})

        assert result["model"] == "gpt-3.5-turbo"
        assert result["metadata"]["ccproxy_ab_experiment"] == "exp-1"
        assert result["metadata"]["ccproxy_ab_variant"] == "treatment"
        assert result["metadata"]["ccproxy_ab_original_model"] == "gpt-4"


class TestGlobalABManager:
    """Tests for global A/B manager."""

    def setup_method(self) -> None:
        """Reset manager before each test."""
        reset_ab_manager()

    def test_get_ab_manager_singleton(self) -> None:
        """Test get_ab_manager returns singleton."""
        manager1 = get_ab_manager()
        manager2 = get_ab_manager()
        assert manager1 is manager2

    def test_reset_ab_manager(self) -> None:
        """Test reset_ab_manager creates new instance."""
        manager1 = get_ab_manager()
        reset_ab_manager()
        manager2 = get_ab_manager()
        assert manager1 is not manager2
