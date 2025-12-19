"""Metrics tracking for ccproxy.

This module provides lightweight in-memory metrics for tracking
request statistics, routing decisions, and cost tracking.
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default model pricing per 1M tokens (input/output)
# Prices in USD, updated as of Dec 2024
DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    # Anthropic models
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    # OpenAI models
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Google models
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # Default fallback
    "default": {"input": 1.0, "output": 3.0},
}


@dataclass
class CostSnapshot:
    """Cost tracking snapshot."""

    total_cost: float
    cost_by_model: dict[str, float]
    cost_by_user: dict[str, float]
    total_input_tokens: int
    total_output_tokens: int
    budget_alerts: list[str]


@dataclass
class MetricsSnapshot:
    """A point-in-time snapshot of metrics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_by_model: dict[str, int]
    requests_by_rule: dict[str, int]
    passthrough_requests: int
    uptime_seconds: float
    timestamp: float = field(default_factory=time.time)
    # Cost tracking
    total_cost: float = 0.0
    cost_by_model: dict[str, float] = field(default_factory=dict)
    cost_by_user: dict[str, float] = field(default_factory=dict)


class MetricsCollector:
    """Thread-safe metrics collector for ccproxy.

    Tracks:
    - Total request count
    - Successful/failed request counts
    - Requests per routed model
    - Requests per matched rule
    - Passthrough requests (no rule matched)
    - Per-request cost calculation
    - Budget limits and alerts
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Core counters
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._passthrough_requests = 0

        # Per-category counters
        self._requests_by_model: dict[str, int] = defaultdict(int)
        self._requests_by_rule: dict[str, int] = defaultdict(int)

        # Cost tracking
        self._total_cost = 0.0
        self._cost_by_model: dict[str, float] = defaultdict(float)
        self._cost_by_user: dict[str, float] = defaultdict(float)
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Budget configuration
        self._budget_limit: float | None = None
        self._budget_per_model: dict[str, float] = {}
        self._budget_per_user: dict[str, float] = {}
        self._budget_alerts: list[str] = []

        # Custom pricing (overrides default)
        self._model_pricing: dict[str, dict[str, float]] = {}

        # Alert callback
        self._alert_callback: Callable[[str], None] | None = None

    def set_pricing(self, model: str, input_price: float, output_price: float) -> None:
        """Set custom pricing for a model.

        Args:
            model: Model name
            input_price: Price per 1M input tokens
            output_price: Price per 1M output tokens
        """
        with self._lock:
            self._model_pricing[model] = {"input": input_price, "output": output_price}

    def set_budget(
        self,
        total: float | None = None,
        per_model: dict[str, float] | None = None,
        per_user: dict[str, float] | None = None,
    ) -> None:
        """Set budget limits.

        Args:
            total: Total budget limit
            per_model: Budget limits per model
            per_user: Budget limits per user
        """
        with self._lock:
            if total is not None:
                self._budget_limit = total
            if per_model is not None:
                self._budget_per_model = per_model
            if per_user is not None:
                self._budget_per_user = per_user

    def set_alert_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for budget alerts.

        Args:
            callback: Function to call with alert message
        """
        self._alert_callback = callback

    def _get_pricing(self, model: str) -> dict[str, float]:
        """Get pricing for a model."""
        # Check custom pricing first
        if model in self._model_pricing:
            return self._model_pricing[model]

        # Check default pricing (partial match)
        for key, pricing in DEFAULT_MODEL_PRICING.items():
            if key in model.lower():
                return pricing

        return DEFAULT_MODEL_PRICING["default"]

    def _check_budget_alert(self, alert_type: str, name: str, current: float, limit: float) -> None:
        """Check and trigger budget alerts."""
        percentage = (current / limit) * 100 if limit > 0 else 0

        if percentage >= 100:
            message = f"BUDGET EXCEEDED: {alert_type} '{name}' at ${current:.2f} (limit: ${limit:.2f})"
        elif percentage >= 90:
            message = f"BUDGET WARNING: {alert_type} '{name}' at {percentage:.1f}% (${current:.2f}/${limit:.2f})"
        elif percentage >= 75:
            message = f"BUDGET NOTICE: {alert_type} '{name}' at {percentage:.1f}% (${current:.2f}/${limit:.2f})"
        else:
            return

        if message not in self._budget_alerts:
            self._budget_alerts.append(message)
            logger.warning(message)
            if self._alert_callback:
                try:
                    self._alert_callback(message)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost for a request.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = self._get_pricing(model)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def record_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user: str | None = None,
    ) -> float:
        """Record cost for a completed request.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user: Optional user identifier

        Returns:
            Cost in USD
        """
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        with self._lock:
            self._total_cost += cost
            self._cost_by_model[model] += cost
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

            if user:
                self._cost_by_user[user] += cost

            # Check budget alerts
            if self._budget_limit is not None:
                self._check_budget_alert("Total", "budget", self._total_cost, self._budget_limit)

            if model in self._budget_per_model:
                self._check_budget_alert("Model", model, self._cost_by_model[model], self._budget_per_model[model])

            if user and user in self._budget_per_user:
                self._check_budget_alert("User", user, self._cost_by_user[user], self._budget_per_user[user])

        return cost

    def record_request(
        self,
        model_name: str | None = None,
        rule_name: str | None = None,
        is_passthrough: bool = False,
    ) -> None:
        """Record a new request.

        Args:
            model_name: The model the request was routed to
            rule_name: The rule that matched (if any)
            is_passthrough: Whether the request was passed through without routing
        """
        with self._lock:
            self._total_requests += 1

            if model_name:
                self._requests_by_model[model_name] += 1

            if rule_name:
                self._requests_by_rule[rule_name] += 1

            if is_passthrough:
                self._passthrough_requests += 1

    def record_success(self) -> None:
        """Record a successful request completion."""
        with self._lock:
            self._successful_requests += 1

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._failed_requests += 1

    def get_cost_snapshot(self) -> CostSnapshot:
        """Get cost tracking snapshot.

        Returns:
            CostSnapshot with current cost data
        """
        with self._lock:
            return CostSnapshot(
                total_cost=self._total_cost,
                cost_by_model=dict(self._cost_by_model),
                cost_by_user=dict(self._cost_by_user),
                total_input_tokens=self._total_input_tokens,
                total_output_tokens=self._total_output_tokens,
                budget_alerts=list(self._budget_alerts),
            )

    def get_snapshot(self) -> MetricsSnapshot:
        """Get a point-in-time snapshot of all metrics.

        Returns:
            MetricsSnapshot with current values
        """
        with self._lock:
            return MetricsSnapshot(
                total_requests=self._total_requests,
                successful_requests=self._successful_requests,
                failed_requests=self._failed_requests,
                requests_by_model=dict(self._requests_by_model),
                requests_by_rule=dict(self._requests_by_rule),
                passthrough_requests=self._passthrough_requests,
                uptime_seconds=time.time() - self._start_time,
                total_cost=self._total_cost,
                cost_by_model=dict(self._cost_by_model),
                cost_by_user=dict(self._cost_by_user),
            )

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self._total_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._passthrough_requests = 0
            self._requests_by_model.clear()
            self._requests_by_rule.clear()
            self._total_cost = 0.0
            self._cost_by_model.clear()
            self._cost_by_user.clear()
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._budget_alerts.clear()
            self._start_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as a dictionary.

        Useful for JSON serialization or logging.
        """
        snapshot = self.get_snapshot()
        return {
            "total_requests": snapshot.total_requests,
            "successful_requests": snapshot.successful_requests,
            "failed_requests": snapshot.failed_requests,
            "requests_by_model": snapshot.requests_by_model,
            "requests_by_rule": snapshot.requests_by_rule,
            "passthrough_requests": snapshot.passthrough_requests,
            "uptime_seconds": round(snapshot.uptime_seconds, 2),
            "timestamp": snapshot.timestamp,
            # Cost tracking
            "total_cost_usd": round(snapshot.total_cost, 4),
            "cost_by_model": {k: round(v, 4) for k, v in snapshot.cost_by_model.items()},
            "cost_by_user": {k: round(v, 4) for k, v in snapshot.cost_by_user.items()},
        }


# Global metrics instance
_metrics_instance: MetricsCollector | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        The singleton MetricsCollector instance
    """
    global _metrics_instance

    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                _metrics_instance = MetricsCollector()

    return _metrics_instance


def reset_metrics() -> None:
    """Reset the global metrics instance."""
    global _metrics_instance
    with _metrics_lock:
        _metrics_instance = None
