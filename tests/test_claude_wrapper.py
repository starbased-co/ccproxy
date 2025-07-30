"""Tests for the Claude CLI wrapper."""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock, Mock, patch

from ccproxy.claude_wrapper import (
    find_free_port,
    get_proxy_env,
    is_port_listening,
    is_process_alive,
    load_state,
    save_state,
    shutdown_proxy,
    start_proxy,
    wait_for_proxy_start,
)


class TestPortUtilities:
    """Test port-related utilities."""

    def test_find_free_port(self):
        """Test finding a free port."""
        port = find_free_port()
        assert isinstance(port, int)
        assert 1024 < port < 65536

        # Port should be free
        assert not is_port_listening(port, timeout=0.1)

    def test_is_port_listening(self):
        """Test port listening check."""
        # Test with a port that's definitely not listening
        assert not is_port_listening(65432, timeout=0.1)

        # Test with a listening socket
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            s.listen(1)
            port = s.getsockname()[1]
            assert is_port_listening(port, timeout=0.1)


class TestProcessUtilities:
    """Test process-related utilities."""

    @patch("ccproxy.claude_wrapper.psutil.Process")
    def test_is_process_alive_running(self, mock_process_class):
        """Test checking if a process is alive."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_process.status.return_value = "running"
        mock_process_class.return_value = mock_process

        assert is_process_alive(12345)

    @patch("ccproxy.claude_wrapper.psutil.Process")
    def test_is_process_alive_zombie(self, mock_process_class):
        """Test checking zombie process."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_process.status.return_value = "zombie"
        mock_process_class.return_value = mock_process

        # Import psutil.STATUS_ZOMBIE for the mock
        with patch("ccproxy.claude_wrapper.psutil.STATUS_ZOMBIE", "zombie"):
            assert not is_process_alive(12345)

    @patch("ccproxy.claude_wrapper.psutil.Process")
    def test_is_process_alive_no_such_process(self, mock_process_class):
        """Test checking non-existent process."""
        import psutil

        mock_process_class.side_effect = psutil.NoSuchProcess(12345)

        assert not is_process_alive(12345)


class TestEnvironmentSetup:
    """Test environment variable setup."""

    def test_get_proxy_env(self):
        """Test proxy environment variable generation."""
        env = get_proxy_env(8888)

        assert env["LITELLM_PROXY_PORT"] == "8888"
        assert env["HTTP_PROXY"] == "http://localhost:8888"
        assert env["HTTPS_PROXY"] == "http://localhost:8888"
        assert env["OPENAI_BASE_URL"] == "http://localhost:8888/v1"
        assert env["ANTHROPIC_BASE_URL"] == "http://localhost:8888/v1"

    def test_get_proxy_env_with_api_key(self):
        """Test proxy env includes API key if set."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            env = get_proxy_env(8888)
            assert env["ANTHROPIC_API_KEY"] == "test-key"

    def test_get_proxy_env_no_api_key(self):
        """Test proxy env excludes empty API key."""
        with patch.dict(os.environ, {}, clear=True):
            env = get_proxy_env(8888)
            assert "ANTHROPIC_API_KEY" not in env


class TestStateManagement:
    """Test state file management."""

    def test_save_and_load_state(self, tmp_path, monkeypatch):
        """Test saving and loading state."""
        state_file = tmp_path / "claude_proxy.json"
        monkeypatch.setattr("ccproxy.claude_wrapper.STATE_FILE", state_file)

        state = {
            "pid": 12345,
            "port": 8888,
            "start_time": time.time(),
            "refcount": 2,
        }

        save_state(state)
        loaded = load_state()

        assert loaded == state
        assert state_file.exists()

    def test_load_state_missing_file(self, tmp_path, monkeypatch):
        """Test loading state when file doesn't exist."""
        state_file = tmp_path / "claude_proxy.json"
        monkeypatch.setattr("ccproxy.claude_wrapper.STATE_FILE", state_file)

        assert load_state() is None

    def test_load_state_corrupted(self, tmp_path, monkeypatch):
        """Test loading corrupted state file."""
        state_file = tmp_path / "claude_proxy.json"
        monkeypatch.setattr("ccproxy.claude_wrapper.STATE_FILE", state_file)

        state_file.write_text("invalid json {")
        assert load_state() is None


class TestProxyManagement:
    """Test proxy lifecycle management."""

    @patch("ccproxy.claude_wrapper.subprocess.Popen")
    @patch("ccproxy.claude_wrapper.open")
    def test_start_proxy_basic(self, mock_open, mock_popen):
        """Test starting proxy process."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        process = start_proxy(8888)

        assert process == mock_process
        mock_popen.assert_called_once()

        # Check command
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert sys.executable in cmd
        assert "-m" in cmd
        assert "litellm" in cmd
        assert "--port" in cmd
        assert "8888" in cmd

    @patch("ccproxy.claude_wrapper.subprocess.Popen")
    @patch("ccproxy.claude_wrapper.open")
    def test_start_proxy_with_config(self, mock_open, mock_popen, tmp_path, monkeypatch):
        """Test starting proxy with config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("models:\n  - model_name: test")

        monkeypatch.setattr("ccproxy.claude_wrapper.CONFIG_FILE", config_file)

        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        process = start_proxy(8888)

        # Check config was included
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--config" in cmd
        assert str(config_file) in cmd

    @patch("ccproxy.claude_wrapper.is_port_listening")
    def test_wait_for_proxy_start_success(self, mock_is_listening):
        """Test waiting for proxy to start successfully."""
        mock_is_listening.side_effect = [False, False, True]

        with patch("ccproxy.claude_wrapper.time.sleep"):
            assert wait_for_proxy_start(8888, timeout=5.0)

        assert mock_is_listening.call_count == 3

    @patch("ccproxy.claude_wrapper.is_port_listening")
    def test_wait_for_proxy_start_timeout(self, mock_is_listening):
        """Test waiting for proxy timeout."""
        mock_is_listening.return_value = False

        with patch("ccproxy.claude_wrapper.time.sleep"):
            assert not wait_for_proxy_start(8888, timeout=0.1)

    @patch("ccproxy.claude_wrapper.psutil.Process")
    def test_shutdown_proxy(self, mock_process_class):
        """Test proxy shutdown."""
        mock_process = Mock()
        mock_process_class.return_value = mock_process

        shutdown_proxy(12345)

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)

    @patch("ccproxy.claude_wrapper.psutil.Process")
    def test_shutdown_proxy_force_kill(self, mock_process_class):
        """Test force killing proxy on timeout."""
        import psutil

        mock_process = Mock()
        mock_process.terminate.return_value = None
        # First wait() call raises TimeoutExpired, second wait() succeeds
        mock_process.wait.side_effect = [psutil.TimeoutExpired(12345, 5), None]
        mock_process_class.return_value = mock_process

        shutdown_proxy(12345)

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.wait.call_count == 2


class TestMainFunction:
    """Test main entry point."""

    @patch("ccproxy.claude_wrapper.subprocess.call")
    @patch("ccproxy.claude_wrapper.subprocess.run")
    @patch("ccproxy.claude_wrapper.start_proxy")
    @patch("ccproxy.claude_wrapper.wait_for_proxy_start")
    @patch("ccproxy.claude_wrapper.is_port_listening")
    @patch("ccproxy.claude_wrapper.is_process_alive")
    @patch("ccproxy.claude_wrapper.load_state")
    @patch("ccproxy.claude_wrapper.save_state")
    @patch("ccproxy.claude_wrapper.fasteners.InterProcessLock")
    def test_main_new_proxy(
        self,
        mock_lock_class,
        mock_save_state,
        mock_load_state,
        mock_is_alive,
        mock_is_listening,
        mock_wait_start,
        mock_start_proxy,
        mock_run,
        mock_call,
    ):
        """Test main with new proxy startup."""
        # Setup mocks
        mock_lock = MagicMock()
        mock_lock_class.return_value = mock_lock
        mock_load_state.return_value = None  # No existing proxy
        mock_wait_start.return_value = True

        mock_process = Mock(pid=12345)
        mock_start_proxy.return_value = mock_process

        # Mock which command finding claude
        mock_which_result = Mock(returncode=0)
        mock_run.return_value = mock_which_result

        # Mock claude execution
        mock_call.return_value = 0

        from ccproxy.claude_wrapper import main

        with patch("sys.argv", ["claude", "--help"]):
            result = main()

        assert result == 0
        mock_start_proxy.assert_called_once()
        mock_save_state.assert_called()
        mock_call.assert_called_once()

    @patch("ccproxy.claude_wrapper.subprocess.call")
    @patch("ccproxy.claude_wrapper.subprocess.run")
    @patch("ccproxy.claude_wrapper.is_port_listening")
    @patch("ccproxy.claude_wrapper.is_process_alive")
    @patch("ccproxy.claude_wrapper.load_state")
    @patch("ccproxy.claude_wrapper.save_state")
    @patch("ccproxy.claude_wrapper.fasteners.InterProcessLock")
    def test_main_reuse_proxy(
        self,
        mock_lock_class,
        mock_save_state,
        mock_load_state,
        mock_is_alive,
        mock_is_listening,
        mock_run,
        mock_call,
    ):
        """Test main with existing proxy reuse."""
        # Setup mocks
        mock_lock = MagicMock()
        mock_lock_class.return_value = mock_lock

        # Existing proxy state
        existing_state = {
            "pid": 12345,
            "port": 8888,
            "start_time": time.time(),
            "refcount": 1,
        }
        # First load_state returns existing state, second returns updated state
        mock_load_state.side_effect = [
            existing_state,
            {"pid": 12345, "port": 8888, "start_time": existing_state["start_time"], "refcount": 2},
        ]
        mock_is_alive.return_value = True
        mock_is_listening.return_value = True

        # Mock which command finding claude
        mock_which_result = Mock(returncode=0)
        mock_run.return_value = mock_which_result

        # Mock claude execution
        mock_call.return_value = 0

        from ccproxy.claude_wrapper import main

        with patch("sys.argv", ["claude", "--help"]):
            result = main()

        assert result == 0

        # Should increment refcount - check all save_state calls
        # First call is during startup, second is during cleanup
        assert mock_save_state.call_count >= 2

        # Check first save_state call (during startup)
        first_call_state = mock_save_state.call_args_list[0][0][0]
        assert first_call_state["refcount"] == 2
        assert first_call_state["port"] == 8888

    @patch("ccproxy.claude_wrapper.subprocess.run")
    @patch("ccproxy.claude_wrapper.fasteners.InterProcessLock")
    def test_main_claude_not_found(self, mock_lock_class, mock_run):
        """Test main when Claude CLI is not found."""
        mock_lock = MagicMock()
        mock_lock_class.return_value = mock_lock

        # Mock which command not finding claude
        mock_which_result = Mock(returncode=1)
        mock_run.return_value = mock_which_result

        from ccproxy.claude_wrapper import main

        with patch("sys.argv", ["claude", "--help"]):
            result = main()

        assert result == 1
