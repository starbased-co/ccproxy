"""Multi-user support for ccproxy.

This module provides user-specific routing, token limits,
and usage tracking.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class UserConfig:
    """Configuration for a specific user."""

    user_id: str
    # Token limits
    daily_token_limit: int | None = None
    monthly_token_limit: int | None = None
    # Cost limits
    daily_cost_limit: float | None = None
    monthly_cost_limit: float | None = None
    # Routing overrides
    allowed_models: list[str] = field(default_factory=list)
    blocked_models: list[str] = field(default_factory=list)
    default_model: str | None = None
    # Rate limiting
    requests_per_minute: int | None = None
    # Priority (higher = more priority)
    priority: int = 0


@dataclass
class UserUsage:
    """Usage statistics for a user."""

    user_id: str
    # Token counts
    daily_input_tokens: int = 0
    daily_output_tokens: int = 0
    monthly_input_tokens: int = 0
    monthly_output_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    # Cost
    daily_cost: float = 0.0
    monthly_cost: float = 0.0
    total_cost: float = 0.0
    # Request counts
    daily_requests: int = 0
    monthly_requests: int = 0
    total_requests: int = 0
    # Timestamps
    last_request_at: float = 0.0
    daily_reset_at: float = 0.0
    monthly_reset_at: float = 0.0
    # Rate limiting
    request_timestamps: list[float] = field(default_factory=list)


@dataclass
class UserLimitResult:
    """Result of a limit check."""

    allowed: bool
    reason: str = ""
    limit_type: str = ""  # "token", "cost", "rate", "model"
    current_value: float = 0.0
    limit_value: float = 0.0


class UserManager:
    """Manages user configurations, limits, and usage tracking.

    Features:
    - Per-user token limits (daily/monthly)
    - Per-user cost limits
    - Model access control
    - Rate limiting
    - Usage tracking
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: dict[str, UserConfig] = {}
        self._usage: dict[str, UserUsage] = {}
        self._limit_exceeded_callback: Callable[[str, UserLimitResult], None] | None = None

    def register_user(self, config: UserConfig) -> None:
        """Register a user configuration.

        Args:
            config: User configuration
        """
        with self._lock:
            self._users[config.user_id] = config
            if config.user_id not in self._usage:
                now = time.time()
                self._usage[config.user_id] = UserUsage(
                    user_id=config.user_id,
                    daily_reset_at=now,
                    monthly_reset_at=now,
                )

    def get_user_config(self, user_id: str) -> UserConfig | None:
        """Get user configuration.

        Args:
            user_id: User identifier

        Returns:
            UserConfig or None if not found
        """
        with self._lock:
            return self._users.get(user_id)

    def get_user_usage(self, user_id: str) -> UserUsage | None:
        """Get user usage statistics.

        Args:
            user_id: User identifier

        Returns:
            UserUsage or None if not found
        """
        with self._lock:
            self._reset_usage_if_needed(user_id)
            return self._usage.get(user_id)

    def _reset_usage_if_needed(self, user_id: str) -> None:
        """Reset daily/monthly counters if needed. Must hold lock."""
        usage = self._usage.get(user_id)
        if not usage:
            return

        now = time.time()
        one_day = 86400
        one_month = 86400 * 30

        # Reset daily counters
        if now - usage.daily_reset_at >= one_day:
            usage.daily_input_tokens = 0
            usage.daily_output_tokens = 0
            usage.daily_cost = 0.0
            usage.daily_requests = 0
            usage.daily_reset_at = now

        # Reset monthly counters
        if now - usage.monthly_reset_at >= one_month:
            usage.monthly_input_tokens = 0
            usage.monthly_output_tokens = 0
            usage.monthly_cost = 0.0
            usage.monthly_requests = 0
            usage.monthly_reset_at = now

    def set_limit_callback(self, callback: Callable[[str, UserLimitResult], None]) -> None:
        """Set callback for when limits are exceeded.

        Args:
            callback: Function to call with (user_id, result)
        """
        self._limit_exceeded_callback = callback

    def check_limits(
        self,
        user_id: str,
        model: str | None = None,
        estimated_tokens: int = 0,
    ) -> UserLimitResult:
        """Check if a request is within user limits.

        Args:
            user_id: User identifier
            model: Model being requested
            estimated_tokens: Estimated tokens for the request

        Returns:
            UserLimitResult indicating if request is allowed
        """
        with self._lock:
            config = self._users.get(user_id)
            if not config:
                # Unknown user - allow by default
                return UserLimitResult(allowed=True)

            self._reset_usage_if_needed(user_id)
            usage = self._usage.get(user_id)
            if not usage:
                return UserLimitResult(allowed=True)

            # Check model access
            if model:
                if config.blocked_models and model in config.blocked_models:
                    result = UserLimitResult(
                        allowed=False,
                        reason=f"Model '{model}' is blocked for user",
                        limit_type="model",
                    )
                    self._trigger_limit_callback(user_id, result)
                    return result

                if config.allowed_models and model not in config.allowed_models:
                    result = UserLimitResult(
                        allowed=False,
                        reason=f"Model '{model}' is not in allowed list",
                        limit_type="model",
                    )
                    self._trigger_limit_callback(user_id, result)
                    return result

            # Check daily token limit
            if config.daily_token_limit is not None:
                current = usage.daily_input_tokens + usage.daily_output_tokens
                if current + estimated_tokens > config.daily_token_limit:
                    result = UserLimitResult(
                        allowed=False,
                        reason="Daily token limit exceeded",
                        limit_type="token",
                        current_value=current,
                        limit_value=config.daily_token_limit,
                    )
                    self._trigger_limit_callback(user_id, result)
                    return result

            # Check monthly token limit
            if config.monthly_token_limit is not None:
                current = usage.monthly_input_tokens + usage.monthly_output_tokens
                if current + estimated_tokens > config.monthly_token_limit:
                    result = UserLimitResult(
                        allowed=False,
                        reason="Monthly token limit exceeded",
                        limit_type="token",
                        current_value=current,
                        limit_value=config.monthly_token_limit,
                    )
                    self._trigger_limit_callback(user_id, result)
                    return result

            # Check rate limit
            if config.requests_per_minute is not None:
                now = time.time()
                one_minute_ago = now - 60
                recent = [t for t in usage.request_timestamps if t > one_minute_ago]
                if len(recent) >= config.requests_per_minute:
                    result = UserLimitResult(
                        allowed=False,
                        reason="Rate limit exceeded",
                        limit_type="rate",
                        current_value=len(recent),
                        limit_value=config.requests_per_minute,
                    )
                    self._trigger_limit_callback(user_id, result)
                    return result

            return UserLimitResult(allowed=True)

    def _trigger_limit_callback(self, user_id: str, result: UserLimitResult) -> None:
        """Trigger limit exceeded callback."""
        if self._limit_exceeded_callback:
            try:
                self._limit_exceeded_callback(user_id, result)
            except Exception as e:
                logger.error(f"Limit callback failed: {e}")

    def record_usage(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        """Record usage for a user.

        Args:
            user_id: User identifier
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            cost: Cost of the request
        """
        with self._lock:
            if user_id not in self._usage:
                now = time.time()
                self._usage[user_id] = UserUsage(
                    user_id=user_id,
                    daily_reset_at=now,
                    monthly_reset_at=now,
                )

            self._reset_usage_if_needed(user_id)
            usage = self._usage[user_id]

            # Update token counts
            usage.daily_input_tokens += input_tokens
            usage.daily_output_tokens += output_tokens
            usage.monthly_input_tokens += input_tokens
            usage.monthly_output_tokens += output_tokens
            usage.total_input_tokens += input_tokens
            usage.total_output_tokens += output_tokens

            # Update cost
            usage.daily_cost += cost
            usage.monthly_cost += cost
            usage.total_cost += cost

            # Update request counts
            usage.daily_requests += 1
            usage.monthly_requests += 1
            usage.total_requests += 1

            # Update timestamps for rate limiting
            now = time.time()
            usage.last_request_at = now
            usage.request_timestamps.append(now)

            # Clean old timestamps (keep last minute only)
            one_minute_ago = now - 60
            usage.request_timestamps = [
                t for t in usage.request_timestamps if t > one_minute_ago
            ]

    def get_effective_model(self, user_id: str, requested_model: str) -> str:
        """Get effective model for a user request.

        Args:
            user_id: User identifier
            requested_model: Model requested

        Returns:
            Effective model to use
        """
        with self._lock:
            config = self._users.get(user_id)
            if not config:
                return requested_model

            # Check if requested model is blocked
            if config.blocked_models and requested_model in config.blocked_models:
                if config.default_model:
                    return config.default_model
                return requested_model  # Let limit check handle it

            # Check if requested model is in allowed list
            if config.allowed_models and requested_model not in config.allowed_models:
                if config.default_model and config.default_model in config.allowed_models:
                    return config.default_model
                return requested_model  # Let limit check handle it

            return requested_model

    def get_all_users(self) -> list[str]:
        """Get list of all registered user IDs."""
        with self._lock:
            return list(self._users.keys())

    def remove_user(self, user_id: str) -> bool:
        """Remove a user and their usage data.

        Args:
            user_id: User identifier

        Returns:
            True if user was removed
        """
        with self._lock:
            removed = False
            if user_id in self._users:
                del self._users[user_id]
                removed = True
            if user_id in self._usage:
                del self._usage[user_id]
                removed = True
            return removed


# Global user manager instance
_user_manager_instance: UserManager | None = None
_user_manager_lock = threading.Lock()


def get_user_manager() -> UserManager:
    """Get the global user manager instance.

    Returns:
        The singleton UserManager instance
    """
    global _user_manager_instance

    if _user_manager_instance is None:
        with _user_manager_lock:
            if _user_manager_instance is None:
                _user_manager_instance = UserManager()

    return _user_manager_instance


def reset_user_manager() -> None:
    """Reset the global user manager instance."""
    global _user_manager_instance
    with _user_manager_lock:
        _user_manager_instance = None


def user_limits_hook(
    data: dict[str, Any],
    user_api_key_dict: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Hook to check user limits before request.

    Args:
        data: Request data
        user_api_key_dict: User API key metadata
        **kwargs: Additional arguments

    Returns:
        Modified request data

    Raises:
        ValueError: If user limits are exceeded
    """
    user_manager = get_user_manager()

    # Extract user ID from various sources
    user_id = (
        user_api_key_dict.get("user_id")
        or data.get("user")
        or data.get("metadata", {}).get("user_id")
    )

    if not user_id:
        return data

    model = data.get("model", "")

    # Check limits
    result = user_manager.check_limits(user_id, model)
    if not result.allowed:
        logger.warning(f"User {user_id} limit exceeded: {result.reason}")
        raise ValueError(f"Request blocked: {result.reason}")

    # Get effective model (may be overridden by user config)
    effective_model = user_manager.get_effective_model(user_id, model)
    if effective_model != model:
        data["model"] = effective_model
        logger.info(f"User {user_id} model override: {model} -> {effective_model}")

    # Store user ID in metadata for tracking
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["ccproxy_user_id"] = user_id

    return data
