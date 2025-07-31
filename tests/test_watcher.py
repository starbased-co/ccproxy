"""Tests for configuration file watcher."""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest
import yaml

from ccproxy.config import clear_config_instance, get_config
from ccproxy.watcher import (
    ConfigFileHandler,
    ConfigWatcher,
    start_config_watcher,
    stop_config_watcher,
)


class TestConfigFileHandler:
    """Tests for ConfigFileHandler."""

    @pytest.fixture
    def temp_config(self) -> Path:
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"token_count_threshold": 50000}, f)
            return Path(f.name)

    def test_handler_init(self, temp_config: Path) -> None:
        """Test handler initialization."""
        callback = mock.Mock()
        handler = ConfigFileHandler(temp_config, callback, debounce_seconds=0.5)

        assert handler.config_path == temp_config.resolve()
        assert handler.callback is callback
        assert handler.debounce_seconds == 0.5

    def test_on_modified_triggers_reload(self, temp_config: Path) -> None:
        """Test that file modification triggers reload."""
        callback = mock.Mock()
        handler = ConfigFileHandler(temp_config, callback, debounce_seconds=0.1)

        # Mock event
        event = mock.Mock()
        event.is_directory = False
        event.src_path = str(temp_config)

        # Set up event loop
        loop = asyncio.new_event_loop()
        handler.set_event_loop(loop)

        # Trigger modification
        handler.on_modified(event)

        # Wait for debounce and reload
        loop.run_until_complete(asyncio.sleep(0.2))

        # Callback should have been called
        callback.assert_called_once()

        # Cleanup
        loop.close()
        temp_config.unlink()

    def test_on_modified_ignores_directories(self, temp_config: Path) -> None:
        """Test that directory events are ignored."""
        callback = mock.Mock()
        handler = ConfigFileHandler(temp_config, callback)

        # Mock directory event
        event = mock.Mock()
        event.is_directory = True

        handler.on_modified(event)

        # No reload should be scheduled
        assert handler._reload_task is None

        # Cleanup
        temp_config.unlink()

    def test_on_modified_ignores_other_files(self, temp_config: Path) -> None:
        """Test that modifications to other files are ignored."""
        callback = mock.Mock()
        handler = ConfigFileHandler(temp_config, callback)

        # Mock event for different file
        event = mock.Mock()
        event.is_directory = False
        event.src_path = str(temp_config.parent / "other_file.yaml")

        handler.on_modified(event)

        # No reload should be scheduled
        assert handler._reload_task is None

        # Cleanup
        temp_config.unlink()

    def test_debouncing(self, temp_config: Path) -> None:
        """Test that rapid modifications are debounced."""
        callback = mock.Mock()
        handler = ConfigFileHandler(temp_config, callback, debounce_seconds=0.2)

        # Set up event loop
        loop = asyncio.new_event_loop()
        handler.set_event_loop(loop)

        # Mock event
        event = mock.Mock()
        event.is_directory = False
        event.src_path = str(temp_config)

        # Trigger multiple rapid modifications
        handler.on_modified(event)
        handler.on_modified(event)
        handler.on_modified(event)

        # Wait for debounce period
        loop.run_until_complete(asyncio.sleep(0.3))

        # Callback should only be called once
        callback.assert_called_once()

        # Cleanup
        loop.close()
        temp_config.unlink()

    @pytest.mark.asyncio
    async def test_async_callback(self, temp_config: Path) -> None:
        """Test that async callbacks work correctly."""
        callback_called = False

        async def async_callback() -> None:
            nonlocal callback_called
            callback_called = True

        handler = ConfigFileHandler(temp_config, async_callback, debounce_seconds=0.1)
        handler.set_event_loop(asyncio.get_running_loop())

        # Mock event
        event = mock.Mock()
        event.is_directory = False
        event.src_path = str(temp_config)

        # Trigger modification
        handler.on_modified(event)

        # Wait for debounce and callback
        await asyncio.sleep(0.2)

        assert callback_called

        # Cleanup
        temp_config.unlink()


class TestConfigWatcher:
    """Tests for ConfigWatcher."""

    @pytest.fixture
    def temp_config(self) -> Path:
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"token_count_threshold": 50000}, f)
            return Path(f.name)

    def test_watcher_init(self, temp_config: Path) -> None:
        """Test watcher initialization."""
        callback = mock.Mock()
        watcher = ConfigWatcher(temp_config, callback, debounce_seconds=0.5)

        assert watcher.config_path == temp_config.resolve()
        assert watcher.callback is callback
        assert watcher.debounce_seconds == 0.5
        assert watcher._observer is None

        # Cleanup
        temp_config.unlink()

    def test_watcher_init_default_path(self) -> None:
        """Test watcher initialization with default path."""
        watcher = ConfigWatcher()
        assert watcher.config_path == Path("./config.yaml").resolve()

    def test_start_stop(self, temp_config: Path) -> None:
        """Test starting and stopping the watcher."""
        watcher = ConfigWatcher(temp_config)

        # Start watching
        watcher.start()
        assert watcher._observer is not None
        assert watcher._observer.is_alive()

        # Start again should be no-op
        watcher.start()
        assert watcher._observer is not None

        # Stop watching
        watcher.stop()
        assert watcher._observer is None

        # Cleanup
        temp_config.unlink()

    def test_context_manager(self, temp_config: Path) -> None:
        """Test watcher as context manager."""
        callback = mock.Mock()

        with ConfigWatcher(temp_config, callback) as watcher:
            assert watcher._observer is not None
            assert watcher._observer.is_alive()

        # Should be stopped after exiting context
        assert watcher._observer is None

        # Cleanup
        temp_config.unlink()

    def test_file_modification_triggers_reload(self, temp_config: Path) -> None:
        """Test that actual file modification triggers config reload."""
        # Clear any existing config
        clear_config_instance()

        # Create callback to track reloads
        reload_count = 0

        def callback() -> None:
            nonlocal reload_count
            reload_count += 1

        # Start watcher
        with ConfigWatcher(temp_config, callback, debounce_seconds=0.1):
            # Modify the file
            with temp_config.open("w") as f:
                yaml.dump({"token_count_threshold": 60000}, f)
                f.flush()  # Ensure write is flushed

            # Wait for reload (a bit longer for file system events)
            time.sleep(0.5)

        # Check that reload happened
        assert reload_count == 1

        # Cleanup
        temp_config.unlink()


class TestGlobalWatcher:
    """Tests for global watcher functions."""

    @pytest.fixture
    def temp_config(self) -> Path:
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"token_count_threshold": 50000}, f)
            return Path(f.name)

    def test_start_stop_global_watcher(self, temp_config: Path) -> None:
        """Test starting and stopping the global watcher."""
        # Start watcher
        watcher = start_config_watcher(temp_config)
        assert watcher is not None
        assert watcher._observer is not None
        assert watcher._observer.is_alive()

        # Stop watcher
        stop_config_watcher()

        # Cleanup
        temp_config.unlink()

    def test_restart_global_watcher(self, temp_config: Path) -> None:
        """Test restarting the global watcher."""
        # Start first watcher
        watcher1 = start_config_watcher(temp_config)
        observer1 = watcher1._observer

        # Start second watcher (should stop first)
        watcher2 = start_config_watcher(temp_config)

        # First observer should be stopped
        assert observer1 is not None
        assert not observer1.is_alive()

        # Second observer should be running
        assert watcher2._observer is not None
        assert watcher2._observer.is_alive()

        # Cleanup
        stop_config_watcher()
        temp_config.unlink()


class TestIntegration:
    """Integration tests for config hot-reload."""

    def test_config_hot_reload_integration(self) -> None:
        """Test full integration of config hot-reload."""
        # Clear any existing config
        clear_config_instance()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "token_count_threshold": 50000,
                    "debug": False,
                    "metrics": {"enabled": True, "port": 9090},
                },
                f,
            )
            config_path = Path(f.name)

        try:
            # Initial config load
            with mock.patch("ccproxy.config.Path", return_value=config_path):
                config = get_config()
                assert config.token_count_threshold == 50000
                assert config.debug is False

                # Track reloads
                reload_count = 0

                def on_reload() -> None:
                    nonlocal reload_count
                    reload_count += 1

                # Start watching
                with ConfigWatcher(config_path, on_reload, debounce_seconds=0.1):
                    # Modify config
                    with config_path.open("w") as f:
                        yaml.dump(
                            {
                                "token_count_threshold": 60000,
                                "debug": True,
                                "metrics": {"enabled": False, "port": 8080},
                            },
                            f,
                        )
                        f.flush()  # Ensure write is flushed

                    # Wait for reload (a bit longer for file system events)
                    time.sleep(0.5)

                    # Check updated config
                    updated_config = get_config()
                    assert updated_config.token_count_threshold == 60000
                    assert updated_config.debug is True
                    assert updated_config.metrics.enabled is False
                    assert updated_config.metrics.port == 8080

                    # Verify reload callback was called
                    assert reload_count == 1

        finally:
            # Cleanup
            config_path.unlink()
            clear_config_instance()

    def test_invalid_config_reload_handling(self) -> None:
        """Test that invalid config doesn't crash the watcher."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"token_count_threshold": 50000}, f)
            config_path = Path(f.name)

        try:
            # Track errors
            error_count = 0

            def on_error() -> None:
                nonlocal error_count
                error_count += 1

            # Start watching
            with ConfigWatcher(config_path, on_error, debounce_seconds=0.1):
                # Write invalid YAML
                with config_path.open("w") as f:
                    f.write("invalid: yaml: content: ][")

                # Wait for reload attempt
                time.sleep(0.3)

                # Error should have been handled gracefully
                # (reload_config will fail but watcher should continue)

                # Write valid config again
                with config_path.open("w") as f:
                    yaml.dump({"token_count_threshold": 70000}, f)

                # Wait for reload
                time.sleep(0.3)

        finally:
            # Cleanup
            config_path.unlink()
