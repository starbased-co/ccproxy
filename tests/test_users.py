"""Tests for multi-user support functionality."""

import time

import pytest

from ccproxy.users import (
    UserConfig,
    UserLimitResult,
    UserManager,
    UserUsage,
    get_user_manager,
    reset_user_manager,
    user_limits_hook,
)


class TestUserConfig:
    """Tests for user configuration."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_register_user(self) -> None:
        """Test registering a user."""
        manager = UserManager()
        config = UserConfig(user_id="user-123")

        manager.register_user(config)

        assert manager.get_user_config("user-123") == config

    def test_register_user_with_limits(self) -> None:
        """Test registering a user with limits."""
        manager = UserManager()
        config = UserConfig(
            user_id="user-123",
            daily_token_limit=10000,
            monthly_token_limit=100000,
            daily_cost_limit=10.0,
        )

        manager.register_user(config)

        retrieved = manager.get_user_config("user-123")
        assert retrieved is not None
        assert retrieved.daily_token_limit == 10000
        assert retrieved.monthly_token_limit == 100000

    def test_get_unknown_user(self) -> None:
        """Test getting unknown user returns None."""
        manager = UserManager()
        assert manager.get_user_config("unknown") is None


class TestUserLimits:
    """Tests for user limit checking."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_unknown_user_allowed(self) -> None:
        """Test that unknown users are allowed by default."""
        manager = UserManager()
        result = manager.check_limits("unknown-user")
        assert result.allowed is True

    def test_daily_token_limit(self) -> None:
        """Test daily token limit enforcement."""
        manager = UserManager()
        config = UserConfig(user_id="user-123", daily_token_limit=1000)
        manager.register_user(config)

        # First check should pass
        result = manager.check_limits("user-123", estimated_tokens=500)
        assert result.allowed is True

        # Record usage
        manager.record_usage("user-123", 500, 500, 0.01)

        # Second check should fail
        result = manager.check_limits("user-123", estimated_tokens=100)
        assert result.allowed is False
        assert result.limit_type == "token"
        assert "Daily" in result.reason

    def test_monthly_token_limit(self) -> None:
        """Test monthly token limit enforcement."""
        manager = UserManager()
        config = UserConfig(user_id="user-123", monthly_token_limit=2000)
        manager.register_user(config)

        # Record usage near limit
        manager.record_usage("user-123", 1000, 900, 0.01)

        # Check should fail
        result = manager.check_limits("user-123", estimated_tokens=200)
        assert result.allowed is False
        assert "Monthly" in result.reason

    def test_blocked_model(self) -> None:
        """Test blocked model enforcement."""
        manager = UserManager()
        config = UserConfig(
            user_id="user-123",
            blocked_models=["gpt-4", "claude-3-opus"],
        )
        manager.register_user(config)

        result = manager.check_limits("user-123", model="gpt-4")
        assert result.allowed is False
        assert result.limit_type == "model"
        assert "blocked" in result.reason

    def test_allowed_models(self) -> None:
        """Test allowed model list enforcement."""
        manager = UserManager()
        config = UserConfig(
            user_id="user-123",
            allowed_models=["gpt-3.5-turbo", "claude-3-haiku"],
        )
        manager.register_user(config)

        # Allowed model
        result = manager.check_limits("user-123", model="gpt-3.5-turbo")
        assert result.allowed is True

        # Not in allowed list
        result = manager.check_limits("user-123", model="gpt-4")
        assert result.allowed is False

    def test_rate_limit(self) -> None:
        """Test rate limiting."""
        manager = UserManager()
        config = UserConfig(user_id="user-123", requests_per_minute=3)
        manager.register_user(config)

        # Make 3 requests
        for _ in range(3):
            manager.record_usage("user-123", 100, 50, 0.01)

        # 4th request should be blocked
        result = manager.check_limits("user-123")
        assert result.allowed is False
        assert result.limit_type == "rate"


class TestUsageTracking:
    """Tests for usage tracking."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_record_usage(self) -> None:
        """Test recording usage."""
        manager = UserManager()
        manager.record_usage("user-123", 100, 50, 0.05)

        usage = manager.get_user_usage("user-123")
        assert usage is not None
        assert usage.total_input_tokens == 100
        assert usage.total_output_tokens == 50
        assert usage.total_cost == 0.05
        assert usage.total_requests == 1

    def test_usage_accumulates(self) -> None:
        """Test that usage accumulates across requests."""
        manager = UserManager()

        manager.record_usage("user-123", 100, 50, 0.05)
        manager.record_usage("user-123", 200, 100, 0.10)

        usage = manager.get_user_usage("user-123")
        assert usage is not None
        assert usage.total_input_tokens == 300
        assert usage.total_output_tokens == 150
        assert usage.total_cost == pytest.approx(0.15)
        assert usage.total_requests == 2


class TestModelOverride:
    """Tests for model override functionality."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_no_override_for_allowed_model(self) -> None:
        """Test no override when model is allowed."""
        manager = UserManager()
        config = UserConfig(user_id="user-123")
        manager.register_user(config)

        effective = manager.get_effective_model("user-123", "gpt-4")
        assert effective == "gpt-4"

    def test_override_blocked_model(self) -> None:
        """Test override when model is blocked."""
        manager = UserManager()
        config = UserConfig(
            user_id="user-123",
            blocked_models=["gpt-4"],
            default_model="gpt-3.5-turbo",
        )
        manager.register_user(config)

        effective = manager.get_effective_model("user-123", "gpt-4")
        assert effective == "gpt-3.5-turbo"

    def test_unknown_user_no_override(self) -> None:
        """Test unknown user gets no override."""
        manager = UserManager()
        effective = manager.get_effective_model("unknown", "gpt-4")
        assert effective == "gpt-4"


class TestLimitCallback:
    """Tests for limit exceeded callback."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_callback_on_limit_exceeded(self) -> None:
        """Test callback is called when limit is exceeded."""
        manager = UserManager()
        callbacks_received: list[tuple[str, UserLimitResult]] = []

        def callback(user_id: str, result: UserLimitResult) -> None:
            callbacks_received.append((user_id, result))

        manager.set_limit_callback(callback)
        config = UserConfig(user_id="user-123", daily_token_limit=100)
        manager.register_user(config)
        manager.record_usage("user-123", 100, 0, 0.01)

        manager.check_limits("user-123", estimated_tokens=10)

        assert len(callbacks_received) == 1
        assert callbacks_received[0][0] == "user-123"


class TestUserManagement:
    """Tests for user management operations."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_get_all_users(self) -> None:
        """Test getting all registered users."""
        manager = UserManager()
        manager.register_user(UserConfig(user_id="user-1"))
        manager.register_user(UserConfig(user_id="user-2"))

        users = manager.get_all_users()
        assert set(users) == {"user-1", "user-2"}

    def test_remove_user(self) -> None:
        """Test removing a user."""
        manager = UserManager()
        manager.register_user(UserConfig(user_id="user-123"))
        manager.record_usage("user-123", 100, 50, 0.05)

        removed = manager.remove_user("user-123")

        assert removed is True
        assert manager.get_user_config("user-123") is None
        assert manager.get_user_usage("user-123") is None

    def test_remove_unknown_user(self) -> None:
        """Test removing unknown user returns False."""
        manager = UserManager()
        removed = manager.remove_user("unknown")
        assert removed is False


class TestUserLimitsHook:
    """Tests for user limits hook."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_hook_with_no_user(self) -> None:
        """Test hook with no user ID."""
        data = {"model": "gpt-4", "messages": []}
        result = user_limits_hook(data, {})
        assert result == data  # No modification

    def test_hook_with_user_id(self) -> None:
        """Test hook adds user ID to metadata."""
        data = {"model": "gpt-4", "messages": [], "user": "user-123"}
        result = user_limits_hook(data, {})
        assert result["metadata"]["ccproxy_user_id"] == "user-123"

    def test_hook_blocks_when_limit_exceeded(self) -> None:
        """Test hook raises error when limit exceeded."""
        manager = get_user_manager()
        config = UserConfig(
            user_id="user-123",
            blocked_models=["gpt-4"],  # Block gpt-4
        )
        manager.register_user(config)

        data = {"model": "gpt-4", "user": "user-123"}

        with pytest.raises(ValueError, match="Request blocked"):
            user_limits_hook(data, {})


class TestGlobalUserManager:
    """Tests for global user manager instance."""

    def setup_method(self) -> None:
        """Reset user manager before each test."""
        reset_user_manager()

    def test_get_user_manager_singleton(self) -> None:
        """Test get_user_manager returns singleton."""
        manager1 = get_user_manager()
        manager2 = get_user_manager()
        assert manager1 is manager2

    def test_reset_user_manager(self) -> None:
        """Test reset_user_manager creates new instance."""
        manager1 = get_user_manager()
        reset_user_manager()
        manager2 = get_user_manager()
        assert manager1 is not manager2
