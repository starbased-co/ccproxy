"""Tests for configuration management."""

import logging
import tempfile
from pathlib import Path
from unittest import mock

from ccproxy.config import (
    CCProxyConfig,
    RuleConfig,
    clear_config_instance,
    get_config,
)


class TestCCProxyConfig:
    """Tests for main config class."""

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
        rule = RuleConfig("test_name", "ccproxy.rules.TokenCountRule", [{"threshold": 5000}])
        assert rule.model_name == "test_name"
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
    - name: token_count
      rule: ccproxy.rules.TokenCountRule
      params:
        - threshold: 80000
    - name: background
      rule: ccproxy.rules.MatchModelRule
      params:
        - model_name: claude-haiku-4-5-20251001
"""
        litellm_yaml_content = """
model_list:
  - model_name: default
    litellm_params:
      model: claude-sonnet-4-5-20250929
  - model_name: background
    litellm_params:
      model: claude-haiku-4-5-20251001-20241022
  - model_name: think
    litellm_params:
      model: claude-opus-4-1-20250805
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
            assert config.rules[0].model_name == "token_count"
            assert config.rules[1].model_name == "background"

            # Model lookup functionality has been moved to router.py

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
    - name: custom_rule
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
            assert config.rules[0].model_name == "custom_rule"
            assert config.rules[0].params == [{"threshold": 70000}]

        finally:
            yaml_path.unlink()

    def test_model_loading_from_yaml(self) -> None:
        """Test that model configuration can be loaded from YAML files."""
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

            # Config should have the litellm_config_path set
            assert config.litellm_config_path == litellm_path
            # Model lookup functionality has been moved to router.py

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
    - name: test
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
                assert config.rules[0].model_name == "test"

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

    def test_config_from_runtime(self) -> None:
        """Test loading configuration from proxy_server runtime."""
        # Mock proxy_server
        mock_proxy_server = mock.MagicMock()
        mock_proxy_server.general_settings = {}
        mock_proxy_server.llm_router = mock.MagicMock()
        mock_proxy_server.llm_router.model_list = [
            {
                "model_name": "default",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-5-20250929",
                    "api_base": "https://api.anthropic.com",
                },
            },
            {
                "model_name": "background",
                "litellm_params": {
                    "model": "anthropic/claude-haiku-4-5-20251001-20241022",
                    "api_base": "https://api.anthropic.com",
                },
            },
        ]

        with mock.patch("ccproxy.config.proxy_server", mock_proxy_server):
            config = CCProxyConfig.from_proxy_runtime()

            # Config should be created successfully
            assert config is not None
            # Model lookup functionality has been moved to router.py

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
    - name: runtime_test
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
                # Set environment variable to point to test directory
                with (
                    mock.patch("ccproxy.config.proxy_server", mock_proxy_server),
                    mock.patch.dict(os.environ, {"CCPROXY_CONFIG_DIR": temp_dir}),
                ):
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
    - name: concurrent_test
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


class TestOAuthLoading:
    """Tests for OAuth token loading at config startup."""

    def test_oat_sources_loaded_at_startup_success(self) -> None:
        """Test that OAuth tokens are loaded successfully during config initialization."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo 'anthropic-token-123'
    gemini: echo 'gemini-token-456'
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)

            # OAuth tokens should be loaded and cached
            assert config.get_oauth_token("anthropic") == "anthropic-token-123"
            assert config.get_oauth_token("gemini") == "gemini-token-456"
            assert config.oat_sources == {"anthropic": "echo 'anthropic-token-123'", "gemini": "echo 'gemini-token-456'"}

        finally:
            yaml_path.unlink()

    def test_oat_sources_loaded_with_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from OAuth token output."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo '  token-with-spaces  '
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.get_oauth_token("anthropic") == "token-with-spaces"

        finally:
            yaml_path.unlink()

    def test_oat_sources_shell_command_failure_partial(self) -> None:
        """Test that config loads successfully even when some OAuth commands fail."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo 'valid-token'
    gemini: exit 1
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            # Should load successfully with partial success
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.get_oauth_token("anthropic") == "valid-token"
            assert config.get_oauth_token("gemini") is None

        finally:
            yaml_path.unlink()

    def test_oat_sources_shell_command_all_fail(self) -> None:
        """Test that config loading fails when all OAuth commands fail."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: exit 1
    gemini: exit 1
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            # Should raise RuntimeError when all commands fail
            import pytest

            with pytest.raises(RuntimeError, match="Failed to load OAuth tokens for all 2 provider"):
                CCProxyConfig.from_yaml(yaml_path)

        finally:
            yaml_path.unlink()

    def test_oat_sources_shell_command_empty_output(self) -> None:
        """Test that provider is skipped when OAuth command returns empty output."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo 'valid-token'
    gemini: echo -n ''
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            # Should load with only valid provider
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.get_oauth_token("anthropic") == "valid-token"
            assert config.get_oauth_token("gemini") is None

        finally:
            yaml_path.unlink()

    def test_oat_sources_shell_command_timeout(self) -> None:
        """Test that provider is skipped when OAuth command times out."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo 'valid-token'
    gemini: sleep 10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            # Should load with only non-timeout provider
            config = CCProxyConfig.from_yaml(yaml_path)
            assert config.get_oauth_token("anthropic") == "valid-token"
            assert config.get_oauth_token("gemini") is None

        finally:
            yaml_path.unlink()

    def test_oat_sources_not_configured(self) -> None:
        """Test that config loads successfully when no OAuth sources configured."""
        yaml_content = """
ccproxy:
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)

            # Should load successfully with no OAuth tokens
            assert config.oat_sources == {}
            assert config.oat_values == {}
            assert config.get_oauth_token("anthropic") is None

        finally:
            yaml_path.unlink()

    def test_oat_values_property_readonly(self) -> None:
        """Test that oat_values is accessible via property."""
        config = CCProxyConfig()
        config._oat_values = {"anthropic": "cached-token"}

        # Should be accessible via property
        assert config.oat_values == {"anthropic": "cached-token"}
        assert config.get_oauth_token("anthropic") == "cached-token"

    def test_oauth_tokens_cached_once(self) -> None:
        """Test that OAuth tokens are cached and not re-executed."""
        yaml_content = """
ccproxy:
  oat_sources:
    anthropic: echo 'initial-token'
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            config = CCProxyConfig.from_yaml(yaml_path)

            # Get the cached value
            first_value = config.get_oauth_token("anthropic")
            assert first_value == "initial-token"

            # Accessing again should return same cached value
            second_value = config.get_oauth_token("anthropic")
            assert second_value == first_value

        finally:
            yaml_path.unlink()

    def test_deprecated_credentials_field_migration(self, caplog) -> None:
        """Test that deprecated 'credentials' field is migrated to oat_sources['anthropic']."""
        yaml_content = """
ccproxy:
  credentials: echo 'legacy-token-123'
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with caplog.at_level(logging.ERROR):
                config = CCProxyConfig.from_yaml(yaml_path)

            # Should have migrated credentials to oat_sources
            assert config.get_oauth_token("anthropic") == "legacy-token-123"
            assert config.oat_sources == {"anthropic": "echo 'legacy-token-123'"}

            # Should have logged deprecation error
            assert "DEPRECATED: The 'credentials' field is deprecated" in caplog.text
            assert "oat_sources['anthropic']" in caplog.text

        finally:
            yaml_path.unlink()

    def test_deprecated_credentials_with_existing_oat_sources(self, caplog) -> None:
        """Test that oat_sources['anthropic'] takes precedence over deprecated credentials."""
        yaml_content = """
ccproxy:
  credentials: echo 'legacy-token'
  oat_sources:
    anthropic: echo 'new-token-456'
  debug: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with caplog.at_level(logging.WARNING):  # Capture WARNING level for the preference message
                config = CCProxyConfig.from_yaml(yaml_path)

            # Should use oat_sources value, not credentials
            assert config.get_oauth_token("anthropic") == "new-token-456"
            assert config.oat_sources == {"anthropic": "echo 'new-token-456'"}

            # Should have logged both deprecation and preference warning
            assert "DEPRECATED: The 'credentials' field is deprecated" in caplog.text
            assert 'Using \'oat_sources["anthropic"]\' and ignoring deprecated \'credentials\' field' in caplog.text

        finally:
            yaml_path.unlink()
