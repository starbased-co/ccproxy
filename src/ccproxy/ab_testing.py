"""A/B Testing Framework for ccproxy.

This module provides model comparison, response quality metrics,
and cost/performance trade-off analysis.
"""

import hashlib
import logging
import random
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExperimentVariant:
    """A variant in an A/B test experiment."""

    name: str
    model: str
    weight: float = 1.0  # Relative weight for traffic distribution
    enabled: bool = True


@dataclass
class ExperimentResult:
    """Result of a single request in an experiment."""

    variant_name: str
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float
    success: bool
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VariantStats:
    """Statistics for a variant."""

    variant_name: str
    model: str
    request_count: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    avg_cost_per_request: float


@dataclass
class ExperimentSummary:
    """Summary of an A/B test experiment."""

    experiment_id: str
    name: str
    variants: list[VariantStats]
    winner: str | None
    confidence: float
    total_requests: int
    started_at: float
    duration_seconds: float


class ABExperiment:
    """An A/B test experiment comparing model variants.

    Features:
    - Multiple variants with weighted traffic distribution
    - Latency and success rate tracking
    - Cost comparison
    - Statistical significance calculation
    """

    def __init__(
        self,
        experiment_id: str,
        name: str,
        variants: list[ExperimentVariant],
        sticky_sessions: bool = True,
    ) -> None:
        """Initialize an experiment.

        Args:
            experiment_id: Unique experiment identifier
            name: Human-readable name
            variants: List of variants to test
            sticky_sessions: If True, same user always gets same variant
        """
        self.experiment_id = experiment_id
        self.name = name
        self.variants = {v.name: v for v in variants}
        self.sticky_sessions = sticky_sessions
        self._started_at = time.time()

        self._lock = threading.Lock()
        self._results: dict[str, list[ExperimentResult]] = {v.name: [] for v in variants}
        self._user_assignments: dict[str, str] = {}

    def _hash_user(self, user_id: str) -> int:
        """Get consistent hash for user ID."""
        return int(hashlib.md5(f"{self.experiment_id}:{user_id}".encode()).hexdigest(), 16)

    def assign_variant(self, user_id: str | None = None) -> ExperimentVariant:
        """Assign a variant to a request.

        Args:
            user_id: Optional user ID for sticky sessions

        Returns:
            Assigned variant
        """
        enabled_variants = [v for v in self.variants.values() if v.enabled]
        if not enabled_variants:
            raise ValueError("No enabled variants in experiment")

        with self._lock:
            # Check sticky session
            if self.sticky_sessions and user_id:
                if user_id in self._user_assignments:
                    variant_name = self._user_assignments[user_id]
                    if variant_name in self.variants:
                        return self.variants[variant_name]

                # Assign based on hash
                user_hash = self._hash_user(user_id)
                total_weight = sum(v.weight for v in enabled_variants)
                threshold = (user_hash % 1000) / 1000 * total_weight

                cumulative = 0.0
                for variant in enabled_variants:
                    cumulative += variant.weight
                    if threshold < cumulative:
                        self._user_assignments[user_id] = variant.name
                        return variant

            # Random assignment based on weights
            total_weight = sum(v.weight for v in enabled_variants)
            r = random.random() * total_weight
            cumulative = 0.0
            for variant in enabled_variants:
                cumulative += variant.weight
                if r < cumulative:
                    return variant

        return enabled_variants[0]

    def record_result(self, result: ExperimentResult) -> None:
        """Record a result for the experiment.

        Args:
            result: Experiment result
        """
        with self._lock:
            if result.variant_name in self._results:
                self._results[result.variant_name].append(result)

    def get_variant_stats(self, variant_name: str) -> VariantStats | None:
        """Get statistics for a variant.

        Args:
            variant_name: Name of the variant

        Returns:
            VariantStats or None if not found
        """
        with self._lock:
            if variant_name not in self._results:
                return None

            results = self._results[variant_name]
            if not results:
                variant = self.variants.get(variant_name)
                return VariantStats(
                    variant_name=variant_name,
                    model=variant.model if variant else "",
                    request_count=0,
                    success_count=0,
                    failure_count=0,
                    success_rate=0.0,
                    avg_latency_ms=0.0,
                    p50_latency_ms=0.0,
                    p95_latency_ms=0.0,
                    p99_latency_ms=0.0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_cost=0.0,
                    avg_cost_per_request=0.0,
                )

            variant = self.variants[variant_name]
            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]
            latencies = sorted([r.latency_ms for r in results])

            return VariantStats(
                variant_name=variant_name,
                model=variant.model,
                request_count=len(results),
                success_count=len(successes),
                failure_count=len(failures),
                success_rate=len(successes) / len(results) if results else 0.0,
                avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
                p50_latency_ms=self._percentile(latencies, 50),
                p95_latency_ms=self._percentile(latencies, 95),
                p99_latency_ms=self._percentile(latencies, 99),
                total_input_tokens=sum(r.input_tokens for r in results),
                total_output_tokens=sum(r.output_tokens for r in results),
                total_cost=sum(r.cost for r in results),
                avg_cost_per_request=sum(r.cost for r in results) / len(results) if results else 0.0,
            )

    def _percentile(self, sorted_data: list[float], p: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f < len(sorted_data) - 1 else f
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    def get_summary(self) -> ExperimentSummary:
        """Get experiment summary with winner determination.

        Returns:
            ExperimentSummary
        """
        with self._lock:
            variant_stats = []
            for name in self.variants:
                stats = self.get_variant_stats(name)
                if stats:
                    variant_stats.append(stats)

            total_requests = sum(s.request_count for s in variant_stats)

            # Determine winner (best success rate with minimum samples)
            winner = None
            confidence = 0.0
            min_samples = 30  # Minimum for statistical significance

            qualified = [s for s in variant_stats if s.request_count >= min_samples]
            if len(qualified) >= 2:
                # Sort by success rate, then by avg latency
                qualified.sort(key=lambda s: (-s.success_rate, s.avg_latency_ms))
                best = qualified[0]
                second = qualified[1]

                if best.success_rate > second.success_rate:
                    winner = best.variant_name
                    # Simple confidence estimate based on sample size and difference
                    diff = best.success_rate - second.success_rate
                    min_count = min(best.request_count, second.request_count)
                    confidence = min(0.99, diff * (min_count / 100))

            return ExperimentSummary(
                experiment_id=self.experiment_id,
                name=self.name,
                variants=variant_stats,
                winner=winner,
                confidence=confidence,
                total_requests=total_requests,
                started_at=self._started_at,
                duration_seconds=time.time() - self._started_at,
            )


class ABTestingManager:
    """Manages multiple A/B testing experiments."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._experiments: dict[str, ABExperiment] = {}
        self._active_experiment: str | None = None

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        variants: list[ExperimentVariant],
        activate: bool = True,
    ) -> ABExperiment:
        """Create a new experiment.

        Args:
            experiment_id: Unique identifier
            name: Human-readable name
            variants: Variants to test
            activate: Whether to activate immediately

        Returns:
            Created experiment
        """
        experiment = ABExperiment(experiment_id, name, variants)

        with self._lock:
            self._experiments[experiment_id] = experiment
            if activate:
                self._active_experiment = experiment_id

        logger.info(f"Created A/B experiment: {name} ({experiment_id})")
        return experiment

    def get_experiment(self, experiment_id: str) -> ABExperiment | None:
        """Get an experiment by ID."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def get_active_experiment(self) -> ABExperiment | None:
        """Get the currently active experiment."""
        with self._lock:
            if self._active_experiment:
                return self._experiments.get(self._active_experiment)
            return None

    def set_active_experiment(self, experiment_id: str | None) -> None:
        """Set the active experiment."""
        with self._lock:
            self._active_experiment = experiment_id

    def list_experiments(self) -> list[str]:
        """List all experiment IDs."""
        with self._lock:
            return list(self._experiments.keys())

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment."""
        with self._lock:
            if experiment_id in self._experiments:
                del self._experiments[experiment_id]
                if self._active_experiment == experiment_id:
                    self._active_experiment = None
                return True
            return False


# Global A/B testing manager
_ab_manager_instance: ABTestingManager | None = None
_ab_manager_lock = threading.Lock()


def get_ab_manager() -> ABTestingManager:
    """Get the global A/B testing manager.

    Returns:
        The singleton ABTestingManager instance
    """
    global _ab_manager_instance

    if _ab_manager_instance is None:
        with _ab_manager_lock:
            if _ab_manager_instance is None:
                _ab_manager_instance = ABTestingManager()

    return _ab_manager_instance


def reset_ab_manager() -> None:
    """Reset the global A/B testing manager."""
    global _ab_manager_instance
    with _ab_manager_lock:
        _ab_manager_instance = None


def ab_testing_hook(
    data: dict[str, Any],
    user_api_key_dict: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Hook to apply A/B testing to requests.

    Args:
        data: Request data
        user_api_key_dict: User API key metadata
        **kwargs: Additional arguments

    Returns:
        Modified request data with assigned variant
    """
    manager = get_ab_manager()
    experiment = manager.get_active_experiment()

    if not experiment:
        return data

    # Get user ID for sticky sessions
    user_id = (
        user_api_key_dict.get("user_id")
        or data.get("user")
        or data.get("metadata", {}).get("user_id")
    )

    try:
        variant = experiment.assign_variant(user_id)
    except ValueError:
        return data

    # Override model
    original_model = data.get("model", "")
    data["model"] = variant.model

    # Store experiment metadata
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["ccproxy_ab_experiment"] = experiment.experiment_id
    data["metadata"]["ccproxy_ab_variant"] = variant.name
    data["metadata"]["ccproxy_ab_original_model"] = original_model
    data["metadata"]["ccproxy_ab_start_time"] = time.time()

    logger.debug(f"A/B test assigned: {variant.name} ({variant.model})")

    return data
