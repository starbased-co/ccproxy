"""Tests for the CCProxy CLI."""

import os
import signal
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest

from ccproxy.cli import CCProxyDaemon, install, main, run_with_proxy


class TestCCProxyDaemon:
    """Test suite for CCProxyDaemon class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test daemon initialization."""
        daemon = CCProxyDaemon(tmp_path)
        assert daemon.config_dir == tmp_path
        assert daemon.pid_file == tmp_path / "ccproxy.pid"
        assert daemon.log_file == tmp_path / "ccproxy.log"

    def test_load_litellm_config_exists(self, tmp_path: Path) -> None:
        """Test loading existing litellm config."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 0.0.0.0
  port: 8080
  num_workers: 4
  debug: true
""")
        daemon = CCProxyDaemon(tmp_path)
        config = daemon._load_litellm_config()

        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8080
        assert config["num_workers"] == 4
        assert config["debug"] is True

    def test_load_litellm_config_not_exists(self, tmp_path: Path) -> None:
        """Test loading litellm config when file doesn't exist."""
        daemon = CCProxyDaemon(tmp_path)
        config = daemon._load_litellm_config()
        assert config == {}

    def test_build_litellm_command_defaults(self, tmp_path: Path) -> None:
        """Test building litellm command with defaults."""
        daemon = CCProxyDaemon(tmp_path)
        args = Mock()
        args.host = None
        args.port = None
        args.workers = None
        args.debug = False
        args.detailed_debug = False

        cmd = daemon._build_litellm_command(args)

        assert cmd[0] == "litellm"
        assert "--config" in cmd
        assert str(tmp_path / "config.yaml") in cmd
        assert "--host" in cmd
        assert "127.0.0.1" in cmd
        assert "--port" in cmd
        assert "4000" in cmd
        assert "--num_workers" in cmd
        assert "1" in cmd
        assert "--debug" not in cmd

    def test_build_litellm_command_with_env_vars(self, tmp_path: Path) -> None:
        """Test building litellm command with environment variables."""
        daemon = CCProxyDaemon(tmp_path)
        args = Mock()
        args.host = None
        args.port = None
        args.workers = None
        args.debug = False
        args.detailed_debug = False

        with patch.dict(os.environ, {"HOST": "192.168.1.1", "PORT": "9000", "DEBUG": "true"}):
            cmd = daemon._build_litellm_command(args)

        assert "192.168.1.1" in cmd
        assert "9000" in cmd
        assert "--debug" in cmd

    def test_build_litellm_command_with_cli_args(self, tmp_path: Path) -> None:
        """Test building litellm command with CLI arguments."""
        daemon = CCProxyDaemon(tmp_path)
        args = Mock()
        args.host = "10.0.0.1"
        args.port = 5000
        args.workers = 8
        args.debug = True
        args.detailed_debug = True

        cmd = daemon._build_litellm_command(args)

        assert "10.0.0.1" in cmd
        assert "5000" in cmd
        assert "8" in cmd
        assert "--debug" in cmd
        assert "--detailed_debug" in cmd

    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("os.chdir")
    @patch("os.open")
    @patch("os.dup2")
    @patch("os.close")
    def test_daemonize(
        self,
        mock_close: Mock,
        mock_dup2: Mock,
        mock_open: Mock,
        mock_chdir: Mock,
        mock_umask: Mock,
        mock_setsid: Mock,
        mock_fork: Mock,
        tmp_path: Path,
    ) -> None:
        """Test daemonization process."""
        daemon = CCProxyDaemon(tmp_path)

        # Mock fork to return 0 (child process)
        mock_fork.return_value = 0
        mock_open.return_value = 3

        daemon._daemonize()

        assert mock_fork.call_count == 2
        mock_chdir.assert_called_once_with(str(tmp_path))
        mock_setsid.assert_called_once()
        mock_umask.assert_called_once_with(0)

    @patch("os.fork")
    def test_daemonize_fork1_failure(self, mock_fork: Mock, tmp_path: Path) -> None:
        """Test daemonization when first fork fails."""
        daemon = CCProxyDaemon(tmp_path)

        # Mock fork to raise OSError
        mock_fork.side_effect = OSError("Fork failed")

        with pytest.raises(SystemExit) as exc_info:
            daemon._daemonize()

        assert exc_info.value.code == 1
        mock_fork.assert_called_once()

    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("os.chdir")
    def test_daemonize_fork2_failure(
        self, mock_chdir: Mock, mock_umask: Mock, mock_setsid: Mock, mock_fork: Mock, tmp_path: Path
    ) -> None:
        """Test daemonization when second fork fails."""
        daemon = CCProxyDaemon(tmp_path)

        # First fork succeeds, second fails
        mock_fork.side_effect = [0, OSError("Fork failed")]

        with pytest.raises(SystemExit) as exc_info:
            daemon._daemonize()

        assert exc_info.value.code == 1
        assert mock_fork.call_count == 2

    @patch("subprocess.Popen")
    @patch.object(CCProxyDaemon, "_daemonize")
    @patch("psutil.pid_exists")
    def test_start_already_running(
        self, mock_pid_exists: Mock, mock_daemonize: Mock, mock_popen: Mock, tmp_path: Path
    ) -> None:
        """Test starting when daemon is already running."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            daemon.start(Mock())

        assert exc_info.value.code == 1
        mock_daemonize.assert_not_called()
        mock_popen.assert_not_called()

    @patch("subprocess.Popen")
    @patch.object(CCProxyDaemon, "_daemonize")
    @patch("psutil.pid_exists")
    def test_start_stale_pid(
        self, mock_pid_exists: Mock, mock_daemonize: Mock, mock_popen: Mock, tmp_path: Path
    ) -> None:
        """Test starting with stale PID file."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = False
        mock_process = Mock()
        mock_process.pid = 99999
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        daemon.start(Mock())

        mock_daemonize.assert_called_once()
        mock_popen.assert_called_once()
        # PID file should be removed in finally block, but process continues

    @patch("subprocess.Popen")
    @patch.object(CCProxyDaemon, "_daemonize")
    def test_start_exception(self, mock_daemonize: Mock, mock_popen: Mock, tmp_path: Path) -> None:
        """Test start when subprocess raises exception."""
        daemon = CCProxyDaemon(tmp_path)

        mock_popen.side_effect = Exception("Failed to start")

        with pytest.raises(SystemExit) as exc_info:
            daemon.start(Mock())

        assert exc_info.value.code == 1
        mock_daemonize.assert_called_once()

    @patch("os.kill")
    @patch("psutil.pid_exists")
    def test_stop_success(self, mock_pid_exists: Mock, mock_kill: Mock, tmp_path: Path) -> None:
        """Test successful stop."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.side_effect = [True, False]  # Exists, then doesn't

        daemon.stop()

        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        assert not pid_file.exists()

    @patch("os.kill")
    @patch("psutil.pid_exists")
    @patch("time.sleep")
    def test_stop_force_kill(self, mock_sleep: Mock, mock_pid_exists: Mock, mock_kill: Mock, tmp_path: Path) -> None:
        """Test force kill when process doesn't terminate gracefully."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        # Process continues to exist after SIGTERM
        mock_pid_exists.return_value = True

        daemon.stop()

        # Should send SIGTERM first, then SIGKILL
        assert mock_kill.call_count == 2
        mock_kill.assert_any_call(12345, signal.SIGTERM)
        mock_kill.assert_any_call(12345, signal.SIGKILL)
        assert mock_sleep.call_count == 100  # Waited full timeout

    def test_stop_not_running(self, tmp_path: Path) -> None:
        """Test stop when daemon is not running."""
        daemon = CCProxyDaemon(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            daemon.stop()

        assert exc_info.value.code == 1

    @patch("os.kill")
    @patch("psutil.pid_exists")
    def test_stop_invalid_pid(self, mock_pid_exists: Mock, mock_kill: Mock, tmp_path: Path) -> None:
        """Test stop with invalid PID in file."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("invalid")

        with pytest.raises(SystemExit) as exc_info:
            daemon.stop()

        assert exc_info.value.code == 1
        mock_kill.assert_not_called()

    @patch("os.kill")
    @patch("psutil.pid_exists")
    def test_stop_permission_error(self, mock_pid_exists: Mock, mock_kill: Mock, tmp_path: Path) -> None:
        """Test stop when permission denied to kill process."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = True
        mock_kill.side_effect = PermissionError("Permission denied")

        # PermissionError is not caught by the stop method, so it will raise
        with pytest.raises(PermissionError):
            daemon.stop()

    @patch("psutil.Process")
    @patch("psutil.pid_exists")
    def test_status_running(self, mock_pid_exists: Mock, mock_process: Mock, tmp_path: Path, capsys) -> None:
        """Test status when daemon is running."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = True
        mock_proc_instance = Mock()
        mock_proc_instance.cpu_percent.return_value = 15.5
        mock_proc_instance.memory_info.return_value = Mock(rss=104857600)  # 100MB
        mock_proc_instance.create_time.return_value = 1234567890
        mock_process.return_value = mock_proc_instance

        daemon.status()

        captured = capsys.readouterr()
        assert "CCProxy is running (PID: 12345)" in captured.out
        assert "CPU: 15.5%" in captured.out
        assert "Memory: 100.0 MB" in captured.out

    @patch("psutil.Process")
    @patch("psutil.pid_exists")
    def test_status_process_error(self, mock_pid_exists: Mock, mock_process: Mock, tmp_path: Path, capsys) -> None:
        """Test status when process info lookup fails."""
        daemon = CCProxyDaemon(tmp_path)
        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = True
        mock_process.side_effect = psutil.NoSuchProcess(12345)

        with pytest.raises(SystemExit) as exc_info:
            daemon.status()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "CCProxy is not running (process not found)" in captured.out
        # PID file should be removed
        assert not pid_file.exists()

    def test_status_not_running(self, tmp_path: Path, capsys) -> None:
        """Test status when daemon is not running."""
        daemon = CCProxyDaemon(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            daemon.status()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "CCProxy is not running" in captured.out


class TestInstallCommand:
    """Test suite for install command."""

    @patch("ccproxy.cli.get_templates_dir")
    def test_install_fresh(self, mock_get_templates: Mock, tmp_path: Path) -> None:
        """Test fresh installation."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template files
        (templates_dir / "ccproxy.yaml").write_text("test: config")
        (templates_dir / "config.yaml").write_text("litellm: config")
        (templates_dir / "ccproxy.py").write_text("# hook code")

        mock_get_templates.return_value = templates_dir

        config_dir = tmp_path / "config"
        install(config_dir)

        assert (config_dir / "ccproxy.yaml").exists()
        assert (config_dir / "config.yaml").exists()
        assert (config_dir / "ccproxy.py").exists()

    def test_install_exists_no_force(self, tmp_path: Path) -> None:
        """Test install when config already exists without force."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            install(config_dir, force=False)

        assert exc_info.value.code == 1

    @patch("ccproxy.cli.get_templates_dir")
    def test_install_with_force(self, mock_get_templates: Mock, tmp_path: Path) -> None:
        """Test install with force overwrites existing files."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "ccproxy.yaml").write_text("new: config")
        (templates_dir / "config.yaml").write_text("new: litellm")
        (templates_dir / "ccproxy.py").write_text("# new hook")

        mock_get_templates.return_value = templates_dir

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "ccproxy.yaml").write_text("old: config")

        install(config_dir, force=True)

        assert (config_dir / "ccproxy.yaml").read_text() == "new: config"


class TestRunWithProxy:
    """Test suite for run_with_proxy function."""

    def test_run_no_config(self, tmp_path: Path) -> None:
        """Test run when config doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["echo", "test"])

        assert exc_info.value.code == 1

    @patch("subprocess.run")
    def test_run_with_proxy_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful command execution with proxy environment."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 192.168.1.1
  port: 8888
""")

        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["echo", "test"])

        assert exc_info.value.code == 0

        # Check environment variables were set
        call_args = mock_run.call_args
        env = call_args[1]["env"]
        assert env["OPENAI_API_BASE"] == "http://192.168.1.1:8888/v1"
        assert env["ANTHROPIC_BASE_URL"] == "http://192.168.1.1:8888/v1"
        assert env["HTTP_PROXY"] == "http://192.168.1.1:8888"

    @patch("subprocess.run")
    @patch("psutil.pid_exists")
    def test_run_with_proxy_daemon_running(self, mock_pid_exists: Mock, mock_run: Mock, tmp_path: Path, capsys) -> None:
        """Test run command when daemon is running."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("12345")

        mock_pid_exists.return_value = True
        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit):
            run_with_proxy(tmp_path, ["echo", "test"])

        captured = capsys.readouterr()
        assert "Using running ccproxy instance (PID: 12345)" in captured.out

    @patch("subprocess.run")
    def test_run_with_proxy_invalid_pid(self, mock_run: Mock, tmp_path: Path, capsys) -> None:
        """Test run with invalid PID file."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        pid_file = tmp_path / "ccproxy.pid"
        pid_file.write_text("invalid")

        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit):
            run_with_proxy(tmp_path, ["echo", "test"])

        captured = capsys.readouterr()
        assert "Warning: CCProxy is not running (invalid PID file)" in captured.err

    @patch("subprocess.run")
    def test_run_with_env_override(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test run with environment variable overrides."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 192.168.1.1
  port: 8888
""")

        mock_run.return_value = Mock(returncode=0)

        with patch.dict(os.environ, {"HOST": "10.0.0.1", "PORT": "9999"}), pytest.raises(SystemExit):
            run_with_proxy(tmp_path, ["echo", "test"])

        # Check environment variables use env overrides
        call_args = mock_run.call_args
        env = call_args[1]["env"]
        assert env["OPENAI_API_BASE"] == "http://10.0.0.1:9999/v1"
        assert env["HTTP_PROXY"] == "http://10.0.0.1:9999"

    @patch("subprocess.run")
    def test_run_command_not_found(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test run with non-existent command."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["nonexistent", "command"])

        assert exc_info.value.code == 1

    @patch("subprocess.run")
    def test_run_command_keyboard_interrupt(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test run with keyboard interrupt."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["echo", "test"])

        assert exc_info.value.code == 130  # Standard exit code for Ctrl+C


class TestMainFunction:
    """Test suite for main CLI function."""

    @patch("ccproxy.cli.CCProxyDaemon")
    def test_main_no_command(self, mock_daemon_class: Mock, capsys) -> None:
        """Test main with no command."""
        with patch.object(sys, "argv", ["ccproxy"]), pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out

    @patch("ccproxy.cli.CCProxyDaemon")
    def test_main_start_command(self, mock_daemon_class: Mock) -> None:
        """Test main with start command."""
        mock_daemon = Mock()
        mock_daemon_class.return_value = mock_daemon

        with patch.object(sys, "argv", ["ccproxy", "start"]):
            main()

        mock_daemon.start.assert_called_once()

    @patch("ccproxy.cli.install")
    def test_main_install_command(self, mock_install: Mock) -> None:
        """Test main with install command."""
        with patch.object(sys, "argv", ["ccproxy", "install", "--force"]):
            main()

        mock_install.assert_called_once()
        # Check keyword arguments
        assert mock_install.call_args.kwargs["force"] is True

    @patch("ccproxy.cli.run_with_proxy")
    def test_main_run_command(self, mock_run: Mock) -> None:
        """Test main with run command."""
        with patch.object(sys, "argv", ["ccproxy", "run", "echo", "hello"]):
            main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0]
        assert call_args[1] == ["echo", "hello"]

    def test_main_run_no_args(self, capsys) -> None:
        """Test main run command without arguments."""
        with patch.object(sys, "argv", ["ccproxy", "run"]), pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No command specified" in captured.err
