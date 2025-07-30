"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml
from pydantic import ValidationError

from ccproxy.config import (
    CCProxyConfig,
    ConfigProvider,
    LoggingConfig,
    MetricsConfig,
    ModelConfig,
    RoutingConfig,
    SecurityConfig,
    clear_config_instance,
    get_config,
    reload_config,
)


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_valid_model_config(self) -> None:
        """Test creating a valid model configuration."""
        config = ModelConfig(
            provider="openai",
            model_name="gpt-4",
            api_base="https://api.openai.com/v1",
            temperature=0.7,
        )
        assert config.provider == "openai"
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.7

    def test_invalid_temperature(self) -> None:
        """Test that invalid temperature raises error."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(
                provider="openai",
                model_name="gpt-4",
                temperature=3.0,  # Too high
            )
        assert "less than or equal to 2" in str(exc_info.value)

    def test_optional_fields(self) -> None:
        """Test that optional fields work correctly."""
        config = ModelConfig(provider="anthropic", model_name="claude-3")
        assert config.api_base is None
        assert config.api_version is None
        assert config.max_tokens is None
        assert config.temperature is None


class TestRoutingConfig:
    """Tests for RoutingConfig."""

    @pytest.fixture
    def sample_models(self) -> dict[str, ModelConfig]:
        """Create sample model configs for testing."""
        return {
            "default": ModelConfig(provider="openai", model_name="gpt-4"),
            "background": ModelConfig(provider="anthropic", model_name="claude-3-haiku"),
            "think": ModelConfig(provider="anthropic", model_name="claude-3-opus"),
            "large_context": ModelConfig(provider="openai", model_name="gpt-4-32k"),
            "web_search": ModelConfig(provider="perplexity", model_name="sonar-large"),
        }

    def test_valid_routing_config(self, sample_models: dict[str, ModelConfig]) -> None:
        """Test creating a valid routing configuration."""
        config = RoutingConfig(**sample_models)
        assert config.default.model_name == "gpt-4"
        assert config.background.model_name == "claude-3-haiku"
        assert config.fallback_enabled is True

    def test_with_fallback(self, sample_models: dict[str, ModelConfig]) -> None:
        """Test routing config with fallback model."""
        fallback = ModelConfig(provider="openai", model_name="gpt-3.5-turbo")
        config = RoutingConfig(**sample_models, fallback_model=fallback)
        assert config.fallback_model is not None
        assert config.fallback_model.model_name == "gpt-3.5-turbo"


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_metrics_config(self) -> None:
        """Test default metrics configuration."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.port == 9090
        assert config.path == "/metrics"

    def test_valid_port_range(self) -> None:
        """Test valid port configuration."""
        config = MetricsConfig(port=8080)
        assert config.port == 8080

    def test_invalid_port(self) -> None:
        """Test that invalid port raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MetricsConfig(port=80)  # Too low
        assert "greater than or equal to 1024" in str(exc_info.value)


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_logging_config(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.max_file_size == 10_485_760  # 10MB
        assert config.backup_count == 5

    def test_with_file_path(self) -> None:
        """Test logging config with file path."""
        config = LoggingConfig(file_path=Path("/var/log/ccproxy.log"))
        assert config.file_path == Path("/var/log/ccproxy.log")


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_security_config(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.enable_rate_limiting is True
        assert config.rate_limit_per_minute == 60
        assert config.enable_https_only is True
        assert config.verify_ssl is True
        assert config.allowed_origins == ["*"]

    def test_custom_rate_limit(self) -> None:
        """Test custom rate limit configuration."""
        config = SecurityConfig(rate_limit_per_minute=120)
        assert config.rate_limit_per_minute == 120


class TestCCProxyConfig:
    """Tests for main CCProxyConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CCProxyConfig()
        assert config.context_threshold == 60000
        assert config.config_path == Path("./config.yaml")
        assert config.debug is False
        assert config.reload_config_on_change is False

    def test_env_var_override(self) -> None:
        """Test environment variable overrides."""
        with mock.patch.dict(
            os.environ,
            {
                "CCPROXY_CONTEXT_THRESHOLD": "50000",
                "CCPROXY_DEBUG": "true",
                "CCPROXY_METRICS__PORT": "8080",
            },
        ):
            config = CCProxyConfig()
            assert config.context_threshold == 50000
            assert config.debug is True
            assert config.metrics.port == 8080

    def test_from_yaml(self) -> None:
        """Test loading configuration from YAML."""
        yaml_content = """
context_threshold: 40000
debug: true
metrics:
  enabled: true
  port: 8090
logging:
  level: DEBUG
  format: text
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.context_threshold == 40000
            assert config.debug is True
            assert config.metrics.port == 8090
            assert config.logging.level == "DEBUG"
            assert config.logging.format == "text"
        finally:
            yaml_path.unlink()

    def test_to_yaml(self) -> None:
        """Test saving configuration to YAML."""
        config = CCProxyConfig(
            context_threshold=35000,
            debug=True,
            metrics=MetricsConfig(port=7070),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "test_config.yaml"
            config.to_yaml(yaml_path)

            # Load and verify
            with yaml_path.open() as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["context_threshold"] == 35000
            assert saved_data["debug"] is True
            assert saved_data["metrics"]["port"] == 7070

    def test_invalid_context_threshold(self) -> None:
        """Test that invalid context threshold raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CCProxyConfig(context_threshold=500)  # Too low
        assert "greater than or equal to 1000" in str(exc_info.value)

    def test_yaml_with_routing_config(self) -> None:
        """Test loading YAML with complete routing configuration."""
        yaml_content = """
routing:
  default:
    provider: openai
    model_name: gpt-4
  background:
    provider: anthropic
    model_name: claude-3-haiku
  think:
    provider: anthropic
    model_name: claude-3-opus
  large_context:
    provider: openai
    model_name: gpt-4-32k
  web_search:
    provider: perplexity
    model_name: sonar-large
  fallback_model:
    provider: openai
    model_name: gpt-3.5-turbo
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.routing is not None
            assert config.routing.default.model_name == "gpt-4"
            assert config.routing.background.provider == "anthropic"
            assert config.routing.fallback_model is not None
            assert config.routing.fallback_model.model_name == "gpt-3.5-turbo"
        finally:
            yaml_path.unlink()


class TestConfigSingleton:
    """Tests for configuration singleton functions."""

    def test_get_config_singleton(self) -> None:
        """Test that get_config returns the same instance."""
        # Clear any existing instance
        clear_config_instance()

        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            config1 = get_config()
            config2 = get_config()
            assert config1 is config2

        # Cleanup
        clear_config_instance()

    def test_reload_config(self) -> None:
        """Test that reload_config creates a new instance."""
        # Clear any existing instance
        clear_config_instance()

        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            config1 = get_config()
            config2 = reload_config()
            assert config1 is not config2

            # Subsequent get_config should return the new instance
            config3 = get_config()
            assert config3 is config2

        # Cleanup
        clear_config_instance()


class TestThreadSafety:
    """Tests for thread-safe configuration access."""

    def test_concurrent_get_config(self) -> None:
        """Test that concurrent access to get_config is thread-safe."""
        import concurrent.futures
        import threading

        # Clear any existing instance
        clear_config_instance()

        # Mock the environment to avoid file access
        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            # Track which thread created the config
            config_ids: set[int] = set()
            lock = threading.Lock()

            def get_and_track() -> None:
                config = get_config()
                with lock:
                    config_ids.add(id(config))

            # Run multiple threads
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(get_and_track) for _ in range(50)]
                concurrent.futures.wait(futures)

            # All threads should get the same instance
            assert len(config_ids) == 1

        # Cleanup
        clear_config_instance()

    def test_concurrent_reload_config(self) -> None:
        """Test that concurrent reload is thread-safe."""
        import concurrent.futures

        # Clear any existing instance
        clear_config_instance()

        # Mock the environment to avoid file access
        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            errors = []

            def reload_safely() -> None:
                try:
                    reload_config()
                except Exception as e:
                    errors.append(e)

            # Run multiple reloads concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(reload_safely) for _ in range(20)]
                concurrent.futures.wait(futures)

            # No errors should occur
            assert len(errors) == 0

        # Cleanup
        clear_config_instance()


class TestConfigProvider:
    """Tests for ConfigProvider dependency injection."""

    def test_provider_initialization(self) -> None:
        """Test ConfigProvider initialization."""
        # With config
        config = CCProxyConfig(context_threshold=40000)
        provider = ConfigProvider(config)
        assert provider.get() is config

        # Without config (lazy load)
        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            provider2 = ConfigProvider()
            # Should load from environment
            loaded_config = provider2.get()
            assert loaded_config is not None
            assert isinstance(loaded_config, CCProxyConfig)

    def test_provider_reload(self) -> None:
        """Test ConfigProvider reload functionality."""
        with (
            mock.patch.dict(os.environ, {"LITELLM_CONFIG_PATH": "./test.yaml"}),
            mock.patch("pathlib.Path.exists", return_value=False),
        ):
            provider = ConfigProvider()

            # Get initial config
            config1 = provider.get()

            # Reload
            config2 = provider.reload()

            # Should be a new instance
            assert config2 is not config1

            # But subsequent gets should return the reloaded config
            config3 = provider.get()
            assert config3 is config2

    def test_provider_set(self) -> None:
        """Test ConfigProvider set functionality."""
        provider = ConfigProvider()

        # Set a specific config
        custom_config = CCProxyConfig(context_threshold=35000, debug=True)
        provider.set(custom_config)

        # Should get the custom config
        assert provider.get() is custom_config
        assert provider.get().context_threshold == 35000
        assert provider.get().debug is True

    def test_multiple_providers(self) -> None:
        """Test that multiple providers can coexist."""
        # Each provider has its own config
        provider1 = ConfigProvider(CCProxyConfig(context_threshold=30000))
        provider2 = ConfigProvider(CCProxyConfig(context_threshold=40000))

        assert provider1.get().context_threshold == 30000
        assert provider2.get().context_threshold == 40000

        # They should be independent
        assert provider1.get() is not provider2.get()
