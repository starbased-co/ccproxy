"""Tests for configuration management."""

import tempfile
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

from ccproxy.config import (
    CCProxyConfig,
    CCProxySettings,
    ConfigProvider,
    LiteLLMConfig,
    clear_config_instance,
    get_config,
)


class TestCCProxySettings:
    """Tests for CCProxySettings model."""

    def test_default_settings(self) -> None:
        """Test default CCProxy settings values."""
        settings = CCProxySettings()
        assert settings.token_count_threshold == 60000
        assert settings.debug is False
        assert settings.metrics_enabled is True

    def test_custom_settings(self) -> None:
        """Test custom CCProxy settings."""
        settings = CCProxySettings(
            token_count_threshold=80000,
            debug=True,
            metrics_enabled=False,
        )
        assert settings.token_count_threshold == 80000
        assert settings.debug is True
        assert settings.metrics_enabled is False

    def test_token_count_threshold_validation(self) -> None:
        """Test context threshold validation."""
        # Valid threshold
        settings = CCProxySettings(token_count_threshold=5000)
        assert settings.token_count_threshold == 5000

        # Invalid threshold (too low)
        with pytest.raises(ValidationError) as exc_info:
            CCProxySettings(token_count_threshold=500)
        assert "greater than or equal to 1000" in str(exc_info.value)


class TestLiteLLMConfig:
    """Tests for LiteLLM configuration model."""

    def test_default_litellm_config(self) -> None:
        """Test default LiteLLM configuration."""
        config = LiteLLMConfig()
        assert config.model_list == []
        assert config.litellm_settings == {}
        assert config.general_settings == {}
        assert isinstance(config.ccproxy_settings, CCProxySettings)
        assert config.ccproxy_settings.token_count_threshold == 60000

    def test_full_litellm_config(self) -> None:
        """Test full LiteLLM configuration."""
        config_data = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                        "api_base": "https://api.anthropic.com",
                    },
                },
                {
                    "model_name": "background",
                    "litellm_params": {
                        "model": "claude-3-5-haiku-20241022",
                        "api_base": "https://api.anthropic.com",
                    },
                },
            ],
            "litellm_settings": {
                "callbacks": "custom_callbacks.ccproxy_handler",
            },
            "general_settings": {
                "monitoring": {
                    "log_transformations": True,
                    "metrics_enabled": True,
                },
            },
            "ccproxy_settings": {
                "token_count_threshold": 70000,
                "debug": True,
            },
        }

        config = LiteLLMConfig(**config_data)
        assert len(config.model_list) == 2
        assert config.model_list[0]["model_name"] == "default"
        assert config.litellm_settings["callbacks"] == "custom_callbacks.ccproxy_handler"
        assert config.ccproxy_settings.token_count_threshold == 70000
        assert config.ccproxy_settings.debug is True


class TestCCProxyConfig:
    """Tests for main CCProxyConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CCProxyConfig()
        assert config.token_count_threshold == 60000
        assert config.debug is False
        assert config.metrics_enabled is True
        assert config.litellm_config_path == Path("./config.yaml")

    def test_config_attributes(self) -> None:
        """Test config attributes can be set directly."""
        config = CCProxyConfig()
        config.token_count_threshold = 50000
        config.debug = True
        config.metrics_enabled = False
        assert config.token_count_threshold == 50000
        assert config.debug is True
        assert config.metrics_enabled is False

    def test_from_litellm_config(self) -> None:
        """Test loading configuration from LiteLLM YAML."""
        yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: claude-3-5-sonnet-20241022
      api_base: https://api.anthropic.com
  - model_name: background
    litellm_params:
      model: claude-3-5-haiku-20241022
      api_base: https://api.anthropic.com
  - model_name: think
    litellm_params:
      model: claude-3-5-sonnet-20241022
      api_base: https://api.anthropic.com
  - model_name: token_count
    litellm_params:
      model: gemini-2.5-pro
      api_base: https://generativelanguage.googleapis.com
  - model_name: web_search
    litellm_params:
      model: perplexity/llama-3.1-sonar-large-128k-online
      api_base: https://api.perplexity.ai

litellm_settings:
  callbacks: custom_callbacks.ccproxy_handler

general_settings:
  monitoring:
    log_transformations: true
    metrics_enabled: true
    slow_transformation_threshold: 0.05

ccproxy_settings:
  token_count_threshold: 80000
  debug: true
  metrics_enabled: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(yaml_path)

            # Check ccproxy settings
            assert config.token_count_threshold == 80000
            assert config.debug is True
            assert config.metrics_enabled is False

            # Check that we can get LiteLLM config
            litellm_config = config.get_litellm_config()
            assert len(litellm_config.model_list) == 5
            assert litellm_config.model_list[0]["model_name"] == "default"

            # Test model lookup
            assert config.get_model_for_label("default") == "claude-3-5-sonnet-20241022"
            assert config.get_model_for_label("background") == "claude-3-5-haiku-20241022"
            assert config.get_model_for_label("think") == "claude-3-5-sonnet-20241022"
            assert config.get_model_for_label("token_count") == "gemini-2.5-pro"
            assert config.get_model_for_label("web_search") == "perplexity/llama-3.1-sonar-large-128k-online"
            assert config.get_model_for_label("unknown") is None

        finally:
            yaml_path.unlink()

    def test_from_litellm_config_no_ccproxy_settings(self) -> None:
        """Test loading LiteLLM config without ccproxy_settings section."""
        yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: claude-3-5-sonnet-20241022

litellm_settings:
  callbacks: custom_callbacks.ccproxy_handler
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(yaml_path)

            # Should use defaults
            assert config.token_count_threshold == 60000
            assert config.debug is False
            assert config.metrics_enabled is True

        finally:
            yaml_path.unlink()

    def test_yaml_config_values(self) -> None:
        """Test that YAML config values are loaded correctly."""
        yaml_content = """
ccproxy_settings:
  token_count_threshold: 70000
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(yaml_path)
            # YAML values should be loaded
            assert config.token_count_threshold == 70000
            assert config.debug is True

        finally:
            yaml_path.unlink()

    def test_get_model_for_label(self) -> None:
        """Test model lookup by routing label."""
        yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: gpt-4
  - model_name: background
    litellm_params:
      model: gpt-3.5-turbo
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_litellm_config(yaml_path)

            assert config.get_model_for_label("default") == "gpt-4"
            assert config.get_model_for_label("background") == "gpt-3.5-turbo"
            assert config.get_model_for_label("think") is None

        finally:
            yaml_path.unlink()


class TestConfigSingleton:
    """Tests for configuration singleton functions."""

    def test_get_config_singleton(self) -> None:
        """Test that get_config returns the same instance."""
        # Clear any existing instance
        clear_config_instance()

        yaml_content = """
ccproxy_settings:
  token_count_threshold: 55000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = yaml_path
                config1 = get_config()
                config2 = get_config()

                assert config1 is config2
                assert config1.token_count_threshold == 55000

        finally:
            yaml_path.unlink()
            clear_config_instance()


class TestConfigProvider:
    """Tests for ConfigProvider dependency injection."""

    def test_provider_initialization(self) -> None:
        """Test ConfigProvider initialization."""
        # With config
        config = CCProxyConfig(token_count_threshold=40000)
        provider = ConfigProvider(config)
        assert provider.get() is config
        assert provider.get().token_count_threshold == 40000

    def test_provider_lazy_load(self) -> None:
        """Test ConfigProvider lazy loading."""
        yaml_content = """
ccproxy_settings:
  token_count_threshold: 85000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = yaml_path
                provider = ConfigProvider()

                # Should load from file on first access
                config = provider.get()
                assert config.token_count_threshold == 85000

                # Subsequent calls return same instance
                assert provider.get() is config

        finally:
            yaml_path.unlink()

    def test_provider_set(self) -> None:
        """Test ConfigProvider set functionality."""
        provider = ConfigProvider()

        # Set a specific config
        custom_config = CCProxyConfig(token_count_threshold=35000, debug=True)
        provider.set(custom_config)

        # Should get the custom config
        assert provider.get() is custom_config
        assert provider.get().token_count_threshold == 35000
        assert provider.get().debug is True

    def test_multiple_providers(self) -> None:
        """Test that multiple providers can coexist."""
        # Each provider has its own config
        provider1 = ConfigProvider(CCProxyConfig(token_count_threshold=30000))
        provider2 = ConfigProvider(CCProxyConfig(token_count_threshold=40000))

        assert provider1.get().token_count_threshold == 30000
        assert provider2.get().token_count_threshold == 40000

        # They should be independent
        assert provider1.get() is not provider2.get()


class TestThreadSafety:
    """Tests for thread-safe configuration access."""

    def test_concurrent_get_config(self) -> None:
        """Test that concurrent access to get_config is thread-safe."""
        import concurrent.futures
        import threading

        # Clear any existing instance
        clear_config_instance()

        yaml_content = """
ccproxy_settings:
  token_count_threshold: 50000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = yaml_path
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

        finally:
            yaml_path.unlink()
            clear_config_instance()
