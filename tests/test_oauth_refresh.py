"""Tests for OAuth token refresh functionality."""

import tempfile
import time
from pathlib import Path
from unittest import mock

from ccproxy.config import CCProxyConfig


class TestOAuthRefresh:
    """Tests for OAuth token refresh."""

    def test_refresh_credentials_empty_sources(self) -> None:
        """Test refresh with no OAuth sources."""
        config = CCProxyConfig()
        result = config.refresh_credentials()
        assert result is False

    def test_refresh_credentials_success(self) -> None:
        """Test successful credential refresh."""
        config = CCProxyConfig(
            oat_sources={"test": "echo 'new_token'"},
        )
        # Pre-populate with old token
        config._oat_values["test"] = "old_token"

        result = config.refresh_credentials()

        assert result is True
        assert config._oat_values["test"] == "new_token"

    def test_refresh_credentials_preserves_working_tokens(self) -> None:
        """Test that failed refresh doesn't remove existing tokens."""
        config = CCProxyConfig(
            oat_sources={"test": "exit 1"},  # Command that fails
        )
        # Pre-populate with existing token
        config._oat_values["test"] = "existing_token"

        result = config.refresh_credentials()

        # Should not have refreshed
        assert result is False
        # But existing token should still be there
        assert config._oat_values["test"] == "existing_token"

    def test_start_background_refresh_disabled_when_interval_zero(self) -> None:
        """Test that background refresh doesn't start when interval is 0."""
        config = CCProxyConfig(
            oat_sources={"test": "echo 'token'"},
            oauth_refresh_interval=0,
        )

        config.start_background_refresh()

        assert config._refresh_thread is None

    def test_start_background_refresh_disabled_when_no_sources(self) -> None:
        """Test that background refresh doesn't start without OAuth sources."""
        config = CCProxyConfig(
            oauth_refresh_interval=3600,
        )

        config.start_background_refresh()

        assert config._refresh_thread is None

    def test_start_background_refresh_starts_thread(self) -> None:
        """Test that background refresh starts a daemon thread."""
        config = CCProxyConfig(
            oat_sources={"test": "echo 'token'"},
            oauth_refresh_interval=1,  # 1 second for testing
        )

        try:
            config.start_background_refresh()

            assert config._refresh_thread is not None
            assert config._refresh_thread.is_alive()
            assert config._refresh_thread.daemon is True
            assert config._refresh_thread.name == "oauth-token-refresh"
        finally:
            config.stop_background_refresh()

    def test_stop_background_refresh(self) -> None:
        """Test stopping the background refresh thread."""
        config = CCProxyConfig(
            oat_sources={"test": "echo 'token'"},
            oauth_refresh_interval=1,
        )

        config.start_background_refresh()
        assert config._refresh_thread is not None

        config.stop_background_refresh()
        assert config._refresh_thread is None

    def test_double_start_is_safe(self) -> None:
        """Test that calling start_background_refresh twice is safe."""
        config = CCProxyConfig(
            oat_sources={"test": "echo 'token'"},
            oauth_refresh_interval=1,
        )

        try:
            config.start_background_refresh()
            thread1 = config._refresh_thread

            config.start_background_refresh()
            thread2 = config._refresh_thread

            # Should be the same thread
            assert thread1 is thread2
        finally:
            config.stop_background_refresh()

    def test_oauth_refresh_interval_from_yaml(self) -> None:
        """Test loading oauth_refresh_interval from YAML."""
        yaml_content = """
ccproxy:
  oauth_refresh_interval: 7200
  oat_sources:
    test: echo 'token'
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(
                    returncode=0,
                    stdout="test_token\n",
                )
                config = CCProxyConfig.from_yaml(yaml_path)

            assert config.oauth_refresh_interval == 7200

            # Stop any background thread that may have started
            config.stop_background_refresh()
        finally:
            yaml_path.unlink()
