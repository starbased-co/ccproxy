"""Tests for configuration management."""

import tempfile
from pathlib import Path
from unittest import mock

from ccproxy.config import (
    CCProxyConfig,
    ConfigProvider,
    RuleConfig,
    clear_config_instance,
    get_config,
)


class TestCCProxyConfig:
    """Tests for main CCProxyConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CCProxyConfig()
        assert config.debug is False
        assert config.metrics_enabled is True
        assert config.litellm_config_path == Path("./config.yaml")
        assert config.ccproxy_config_path == Path("./ccproxy.yaml")
        assert config.rules == []

    def test_config_attributes(self) -> None:
        """Test config attributes can be set directly."""
        config = CCProxyConfig()
        config.debug = True
        config.metrics_enabled = False
        assert config.debug is True
        assert config.metrics_enabled is False

    def test_rule_config(self) -> None:
        """Test rule configuration."""
        # Create a rule config
        rule = RuleConfig("test_label", "ccproxy.rules.TokenCountRule", [{"threshold": 5000}])
        assert rule.label == "test_label"
        assert rule.rule_path == "ccproxy.rules.TokenCountRule"
        assert rule.params == [{"threshold": 5000}]

        # Create instance
        instance = rule.create_instance()
        from ccproxy.rules import TokenCountRule

        assert isinstance(instance, TokenCountRule)

    def test_from_yaml_files(self) -> None:
        """Test loading configuration from ccproxy.yaml."""
        ccproxy_yaml_content = """
ccproxy:
  debug: true
  metrics_enabled: false
  rules:
    - label: token_count
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 80000
    - label: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: claude-3-5-haiku
"""
        litellm_yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: claude-3-5-sonnet-20241022
  - model_name: background
    litellm_params:
      model: claude-3-5-haiku-20241022
  - model_name: think
    litellm_params:
      model: claude-3-5-sonnet-20241022
  - model_name: token_count
    litellm_params:
      model: gemini-2.5-pro
  - model_name: web_search
    litellm_params:
      model: perplexity/llama-3.1-sonar-large-128k-online
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            ccproxy_file.write(ccproxy_yaml_content)
            ccproxy_path = Path(ccproxy_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            litellm_file.write(litellm_yaml_content)
            litellm_path = Path(litellm_file.name)

        try:
            config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)

            # Check ccproxy settings
            assert config.debug is True
            assert config.metrics_enabled is False
            assert len(config.rules) == 2
            assert config.rules[0].label == "token_count"
            assert config.rules[1].label == "background"

            # Test model lookup (reads from YAML when proxy_server is None)
            assert config.get_model_for_label("default") == "claude-3-5-sonnet-20241022"
            assert config.get_model_for_label("background") == "claude-3-5-haiku-20241022"
            assert config.get_model_for_label("token_count") == "gemini-2.5-pro"
            assert config.get_model_for_label("web_search") == "perplexity/llama-3.1-sonar-large-128k-online"
            assert config.get_model_for_label("nonexistent") is None

        finally:
            ccproxy_path.unlink()
            litellm_path.unlink()

    def test_from_yaml_no_ccproxy_section(self) -> None:
        """Test loading ccproxy.yaml without ccproxy section."""
        yaml_content = """
# Empty YAML or missing ccproxy section
other_settings:
  key: value
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)

            # Should use defaults
            assert config.debug is False
            assert config.metrics_enabled is True
            assert config.rules == []

        finally:
            yaml_path.unlink()

    def test_yaml_config_values(self) -> None:
        """Test that YAML config values are loaded correctly."""
        yaml_content = """
ccproxy:
  debug: true
  metrics_enabled: false
  rules:
    - label: custom_rule
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 70000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)
            # YAML values should be loaded
            assert config.debug is True
            assert config.metrics_enabled is False
            assert len(config.rules) == 1
            assert config.rules[0].label == "custom_rule"
            assert config.rules[0].params == [{"threshold": 70000}]

        finally:
            yaml_path.unlink()

    def test_get_model_for_label(self) -> None:
        """Test model lookup by routing label."""
        litellm_yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: gpt-4
  - model_name: background
    litellm_params:
      model: gpt-3.5-turbo
"""
        ccproxy_yaml_content = """
ccproxy:
  debug: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as litellm_file:
            litellm_file.write(litellm_yaml_content)
            litellm_path = Path(litellm_file.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as ccproxy_file:
            ccproxy_file.write(ccproxy_yaml_content)
            ccproxy_path = Path(ccproxy_file.name)

        try:
            config = CCProxyConfig.from_yaml(ccproxy_path, litellm_config_path=litellm_path)

            # Should return models from YAML when proxy_server is None
            assert config.get_model_for_label("default") == "gpt-4"
            assert config.get_model_for_label("background") == "gpt-3.5-turbo"
            assert config.get_model_for_label("think") is None  # Not in model_list

        finally:
            litellm_path.unlink()
            ccproxy_path.unlink()


class TestConfigSingleton:
    """Tests for configuration singleton functions."""

    def test_get_config_singleton(self) -> None:
        """Test that get_config returns the same instance."""
        # Clear any existing instance
        clear_config_instance()

        # Create a custom config instance and set it directly
        custom_config = CCProxyConfig(debug=True, metrics_enabled=False)
        from ccproxy.config import set_config_instance

        set_config_instance(custom_config)

        try:
            config1 = get_config()
            config2 = get_config()

            assert config1 is config2
            assert config1.debug is True
            assert config1.metrics_enabled is False

        finally:
            clear_config_instance()


class TestConfigProvider:
    """Tests for ConfigProvider dependency injection."""

    def test_provider_initialization(self) -> None:
        """Test ConfigProvider initialization."""
        # With config
        config = CCProxyConfig(debug=True)
        provider = ConfigProvider(config)
        assert provider.get() is config
        assert provider.get().debug is True

    def test_provider_lazy_load(self) -> None:
        """Test ConfigProvider lazy loading."""
        # Clear any existing instance
        clear_config_instance()

        # Set a custom config in the global singleton
        custom_config = CCProxyConfig(metrics_enabled=False)
        from ccproxy.config import set_config_instance

        set_config_instance(custom_config)

        try:
            provider = ConfigProvider()

            # Should load from singleton on first access
            config = provider.get()
            assert config.metrics_enabled is False

            # Subsequent calls return same instance
            assert provider.get() is config

        finally:
            clear_config_instance()

    def test_provider_set(self) -> None:
        """Test ConfigProvider set functionality."""
        provider = ConfigProvider()

        # Set a specific config
        custom_config = CCProxyConfig(debug=True, metrics_enabled=False)
        provider.set(custom_config)

        # Should get the custom config
        assert provider.get() is custom_config
        assert provider.get().debug is True
        assert provider.get().metrics_enabled is False

    def test_multiple_providers(self) -> None:
        """Test that multiple providers can coexist."""
        # Each provider has its own config
        provider1 = ConfigProvider(CCProxyConfig(debug=True))
        provider2 = ConfigProvider(CCProxyConfig(debug=False))

        assert provider1.get().debug is True
        assert provider2.get().debug is False

        # They should be independent
        assert provider1.get() is not provider2.get()


class TestProxyRuntimeConfig:
    """Tests for loading configuration from proxy_server runtime."""

    def test_from_proxy_runtime_with_ccproxy_yaml(self) -> None:
        """Test loading config from ccproxy.yaml in the same directory as config.yaml."""
        # Create a temp directory with config.yaml and ccproxy.yaml
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config.yaml (LiteLLM config)
            config_yaml = temp_path / "config.yaml"
            config_yaml.write_text("""
model_list:
  - model_name: default
    litellm_params:
      model: gpt-4
""")

            # Create ccproxy.yaml in same directory
            ccproxy_yaml = temp_path / "ccproxy.yaml"
            ccproxy_yaml.write_text("""
ccproxy:
  debug: true
  metrics_enabled: false
  rules:
    - label: test
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 75000
""")

            # Mock Path("config.yaml") to return our temp config.yaml
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = config_yaml

                config = CCProxyConfig.from_proxy_runtime()

                assert config.debug is True
                assert config.metrics_enabled is False
                assert len(config.rules) == 1
                assert config.rules[0].label == "test"

    def test_from_proxy_runtime_without_ccproxy_yaml(self) -> None:
        """Test loading config when ccproxy.yaml doesn't exist."""
        # Create a temporary directory without ccproxy.yaml
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_yaml = temp_path / "config.yaml"
            config_yaml.write_text("model_list: []")

            # Mock Path("config.yaml") to return our temp config.yaml
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = config_yaml

                config = CCProxyConfig.from_proxy_runtime()

                # Should use defaults
                assert config.debug is False
                assert config.metrics_enabled is True
                assert config.rules == []

    def test_from_proxy_runtime_default_paths(self) -> None:
        """Test loading config with default paths."""
        # Create paths that don't exist
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_yaml = temp_path / "config.yaml"  # Don't create it

            # Mock Path to return our non-existent config.yaml
            with mock.patch("ccproxy.config.Path") as mock_path:
                mock_path.return_value = config_yaml

                config = CCProxyConfig.from_proxy_runtime()

                # Should use defaults
                assert config.debug is False
                assert config.metrics_enabled is True
                assert config.rules == []

    def test_get_model_for_label_from_runtime(self) -> None:
        """Test model lookup from proxy_server runtime."""
        # Mock proxy_server
        mock_proxy_server = mock.MagicMock()
        mock_proxy_server.general_settings = {}
        mock_proxy_server.llm_router = mock.MagicMock()
        mock_proxy_server.llm_router.model_list = [
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
        ]

        with mock.patch("ccproxy.config.proxy_server", mock_proxy_server):
            config = CCProxyConfig.from_proxy_runtime()

            assert config.get_model_for_label("default") == "claude-3-5-sonnet-20241022"
            assert config.get_model_for_label("background") == "claude-3-5-haiku-20241022"
            assert config.get_model_for_label("unknown") is None

    def test_get_config_uses_runtime_when_available(self) -> None:
        """Test that get_config prefers runtime config when available."""
        # Clear any existing instance
        clear_config_instance()

        # Mock proxy_server
        mock_proxy_server = mock.MagicMock()
        mock_proxy_server.general_settings = {}

        # Create temporary ccproxy.yaml
        ccproxy_yaml_content = """
ccproxy:
  debug: true
  rules:
    - label: runtime_test
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 90000
"""

        # Create a temp directory for the config files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config.yaml
            config_yaml = temp_path / "config.yaml"
            config_yaml.write_text("model_list: []")

            # Create ccproxy.yaml
            ccproxy_yaml = temp_path / "ccproxy.yaml"
            ccproxy_yaml.write_text(ccproxy_yaml_content)

            # Change to the temp directory so ./ccproxy.yaml exists
            import os

            original_cwd = Path.cwd()
            os.chdir(temp_dir)

            try:
                with mock.patch("ccproxy.config.proxy_server", mock_proxy_server):
                    config = get_config()
                    assert config.debug is True
                    assert len(config.rules) == 1
                    assert config.rules[0].params == [{"threshold": 90000}]
            finally:
                os.chdir(original_cwd)

        clear_config_instance()


class TestThreadSafety:
    """Tests for thread-safe configuration access."""

    def test_concurrent_get_config(self) -> None:
        """Test that concurrent access to get_config is thread-safe."""
        import concurrent.futures
        import os
        import threading

        # Clear any existing instance
        clear_config_instance()

        yaml_content = """
ccproxy:
  debug: true
  rules:
    - label: concurrent_test
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 50000
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ccproxy_path = Path(temp_dir) / "ccproxy.yaml"
            ccproxy_path.write_text(yaml_content)

            # Change to temp directory so ./ccproxy.yaml exists
            original_cwd = Path.cwd()
            os.chdir(temp_dir)

            try:
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
                os.chdir(original_cwd)
                clear_config_instance()
