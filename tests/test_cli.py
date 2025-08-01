"""Tests for the CCProxy CLI."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from ccproxy.cli import (
    CCProxyManager,
    Install,
    ProxyConfig,
    Run,
    Start,
    Status,
    Stop,
    install_config,
    main,
    run_with_proxy,
)


class TestCCProxyManager:
    """Test suite for CCProxyManager class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test manager initialization."""
        manager = CCProxyManager(tmp_path)
        assert manager.config_dir == tmp_path

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
        manager = CCProxyManager(tmp_path)
        config = manager._load_litellm_config()

        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8080
        assert config["num_workers"] == 4
        assert config["debug"] is True

    def test_load_litellm_config_not_exists(self, tmp_path: Path) -> None:
        """Test loading litellm config when file doesn't exist."""
        manager = CCProxyManager(tmp_path)
        config = manager._load_litellm_config()
        assert config == {}

    def test_get_server_config_defaults(self, tmp_path: Path) -> None:
        """Test getting server config with defaults."""
        manager = CCProxyManager(tmp_path)
        host, port = manager._get_server_config()

        assert host == "127.0.0.1"
        assert port == 4000

    def test_get_server_config_from_file(self, tmp_path: Path) -> None:
        """Test getting server config from file."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 192.168.1.1
  port: 8888
""")
        manager = CCProxyManager(tmp_path)
        host, port = manager._get_server_config()

        assert host == "192.168.1.1"
        assert port == 8888

    def test_get_server_config_env_override(self, tmp_path: Path) -> None:
        """Test getting server config with environment overrides."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 192.168.1.1
  port: 8888
""")
        manager = CCProxyManager(tmp_path)

        with patch.dict(os.environ, {"HOST": "10.0.0.1", "PORT": "9999"}):
            host, port = manager._get_server_config()

        assert host == "10.0.0.1"
        assert port == 9999

    @patch("httpx.Client")
    def test_check_server_status_running(self, mock_client_class: Mock, tmp_path: Path) -> None:
        """Test checking server status when running."""
        manager = CCProxyManager(tmp_path)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        assert manager._check_server_status() is True
        mock_client.get.assert_called_once_with("http://127.0.0.1:4000/health")

    @patch("httpx.Client")
    def test_check_server_status_not_running(self, mock_client_class: Mock, tmp_path: Path) -> None:
        """Test checking server status when not running."""
        manager = CCProxyManager(tmp_path)

        mock_client = Mock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client_class.return_value.__enter__.return_value = mock_client

        assert manager._check_server_status() is False

    @patch("httpx.Client")
    def test_check_server_status_timeout(self, mock_client_class: Mock, tmp_path: Path) -> None:
        """Test checking server status with timeout."""
        manager = CCProxyManager(tmp_path)

        mock_client = Mock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        assert manager._check_server_status() is False

    @patch.object(CCProxyManager, "_check_server_status")
    def test_start_already_running(self, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test start when server is already running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = True

        proxy_config = ProxyConfig()

        with pytest.raises(SystemExit) as exc_info:
            manager.start(proxy_config)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "LiteLLM server is already running" in captured.out

    @patch.object(CCProxyManager, "_check_server_status")
    def test_start_not_running(self, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test start when server is not running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = False

        proxy_config = ProxyConfig(
            host="192.168.1.1",
            port=8080,
            workers=4,
            debug=True,
            detailed_debug=True,
        )

        with pytest.raises(SystemExit) as exc_info:
            manager.start(proxy_config)

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "To start LiteLLM server, run:" in captured.out
        assert f"litellm --config {tmp_path}/config.yaml" in captured.out
        assert "--host 192.168.1.1" in captured.out
        assert "--port 8080" in captured.out
        assert "--num_workers 4" in captured.out
        assert "Add: --debug" in captured.out
        assert "Add: --detailed_debug" in captured.out

    @patch.object(CCProxyManager, "_check_server_status")
    def test_stop_not_running(self, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test stop when server is not running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            manager.stop()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "LiteLLM server is not running" in captured.out

    @patch.object(CCProxyManager, "_check_server_status")
    def test_stop_running(self, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test stop when server is running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            manager.stop()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "To stop the LiteLLM server" in captured.out
        assert "ps aux | grep litellm" in captured.out
        assert "kill <PID>" in captured.out

    @patch.object(CCProxyManager, "_check_server_status")
    @patch("httpx.Client")
    def test_status_running(self, mock_client_class: Mock, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test status when server is running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = True

        mock_client = Mock()
        # Health response
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        # Models response
        mock_models_response = Mock()
        mock_models_response.status_code = 200
        mock_models_response.json.return_value = {"data": [{"id": "model1"}, {"id": "model2"}]}

        mock_client.get.side_effect = [mock_health_response, mock_models_response]
        mock_client_class.return_value.__enter__.return_value = mock_client

        with pytest.raises(SystemExit) as exc_info:
            manager.status()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "LiteLLM server is running on 127.0.0.1:4000" in captured.out
        assert "Status: Healthy" in captured.out
        assert "Available models: 2" in captured.out

    @patch.object(CCProxyManager, "_check_server_status")
    def test_status_not_running(self, mock_check_status: Mock, tmp_path: Path, capsys) -> None:
        """Test status when server is not running."""
        manager = CCProxyManager(tmp_path)
        mock_check_status.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            manager.status()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "LiteLLM server is not running on 127.0.0.1:4000" in captured.out


class TestInstallConfig:
    """Test suite for install_config function."""

    @patch("ccproxy.cli.get_templates_dir")
    def test_install_fresh(self, mock_get_templates: Mock, tmp_path: Path, capsys) -> None:
        """Test fresh installation."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template files
        (templates_dir / "ccproxy.yaml").write_text("test: config")
        (templates_dir / "config.yaml").write_text("litellm: config")
        (templates_dir / "ccproxy.py").write_text("# hook code")

        mock_get_templates.return_value = templates_dir

        config_dir = tmp_path / "config"
        install_config(config_dir)

        assert (config_dir / "ccproxy.yaml").exists()
        assert (config_dir / "config.yaml").exists()
        assert (config_dir / "ccproxy.py").exists()

        captured = capsys.readouterr()
        assert "Installation complete!" in captured.out
        assert "Next steps:" in captured.out

    def test_install_exists_no_force(self, tmp_path: Path, capsys) -> None:
        """Test install when config already exists without force."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            install_config(config_dir, force=False)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.out
        assert "Use --force to overwrite" in captured.out

    @patch("ccproxy.cli.get_templates_dir")
    def test_install_with_force(self, mock_get_templates: Mock, tmp_path: Path, capsys) -> None:
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

        install_config(config_dir, force=True)

        assert (config_dir / "ccproxy.yaml").read_text() == "new: config"
        captured = capsys.readouterr()
        assert "Copied ccproxy.yaml" in captured.out

    @patch("ccproxy.cli.get_templates_dir")
    def test_install_template_not_found(self, mock_get_templates: Mock, tmp_path: Path, capsys) -> None:
        """Test install when template file is missing."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        # Only create some template files
        (templates_dir / "ccproxy.yaml").write_text("test: config")

        mock_get_templates.return_value = templates_dir

        config_dir = tmp_path / "config"
        install_config(config_dir)

        captured = capsys.readouterr()
        assert "Warning: Template config.yaml not found" in captured.err
        assert "Warning: Template ccproxy.py not found" in captured.err


class TestRunWithProxy:
    """Test suite for run_with_proxy function."""

    def test_run_no_config(self, tmp_path: Path, capsys) -> None:
        """Test run when config doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["echo", "test"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Configuration not found" in captured.err
        assert "Run 'ccproxy install' first" in captured.err

    @patch("subprocess.run")
    @patch.object(CCProxyManager, "_check_server_status")
    def test_run_with_proxy_success(self, mock_check_status: Mock, mock_run: Mock, tmp_path: Path, capsys) -> None:
        """Test successful command execution with proxy environment."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("""
litellm:
  host: 192.168.1.1
  port: 8888
""")

        mock_check_status.return_value = True
        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["echo", "test"])

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Using running LiteLLM server on 192.168.1.1:8888" in captured.out

        # Check environment variables were set
        call_args = mock_run.call_args
        env = call_args[1]["env"]
        assert env["OPENAI_API_BASE"] == "http://192.168.1.1:8888/v1"
        assert env["ANTHROPIC_BASE_URL"] == "http://192.168.1.1:8888/v1"
        assert env["HTTP_PROXY"] == "http://192.168.1.1:8888"

    @patch("subprocess.run")
    @patch.object(CCProxyManager, "_check_server_status")
    def test_run_with_proxy_server_not_running(
        self, mock_check_status: Mock, mock_run: Mock, tmp_path: Path, capsys
    ) -> None:
        """Test run command when server is not running."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        mock_check_status.return_value = False
        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit):
            run_with_proxy(tmp_path, ["echo", "test"])

        captured = capsys.readouterr()
        assert "Warning: LiteLLM server is not running." in captured.err
        assert "Run 'litellm --config" in captured.err

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

        with (
            patch.dict(os.environ, {"HOST": "10.0.0.1", "PORT": "9999"}),
            pytest.raises(SystemExit),
        ):
            run_with_proxy(tmp_path, ["echo", "test"])

        # Check environment variables use env overrides
        call_args = mock_run.call_args
        env = call_args[1]["env"]
        assert env["OPENAI_API_BASE"] == "http://10.0.0.1:9999/v1"
        assert env["HTTP_PROXY"] == "http://10.0.0.1:9999"

    @patch("subprocess.run")
    def test_run_command_not_found(self, mock_run: Mock, tmp_path: Path, capsys) -> None:
        """Test run with non-existent command."""
        config_file = tmp_path / "ccproxy.yaml"
        config_file.write_text("litellm: {}")

        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as exc_info:
            run_with_proxy(tmp_path, ["nonexistent", "command"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Command not found: nonexistent" in captured.err

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
    """Test suite for main CLI function using Tyro."""

    @patch.object(CCProxyManager, "start")
    def test_main_start_command(self, mock_start: Mock, tmp_path: Path) -> None:
        """Test main with start command."""
        cmd = Start(host="192.168.1.1", port=8080, debug=True)
        main(cmd, config_dir=tmp_path)

        mock_start.assert_called_once()
        call_args = mock_start.call_args[0][0]
        assert isinstance(call_args, ProxyConfig)
        assert call_args.host == "192.168.1.1"
        assert call_args.port == 8080
        assert call_args.debug is True

    @patch.object(CCProxyManager, "stop")
    def test_main_stop_command(self, mock_stop: Mock, tmp_path: Path) -> None:
        """Test main with stop command."""
        cmd = Stop()
        main(cmd, config_dir=tmp_path)

        mock_stop.assert_called_once()

    @patch.object(CCProxyManager, "status")
    def test_main_status_command(self, mock_status: Mock, tmp_path: Path) -> None:
        """Test main with status command."""
        cmd = Status()
        main(cmd, config_dir=tmp_path)

        mock_status.assert_called_once()

    @patch("ccproxy.cli.install_config")
    def test_main_install_command(self, mock_install: Mock, tmp_path: Path) -> None:
        """Test main with install command."""
        cmd = Install(force=True)
        main(cmd, config_dir=tmp_path)

        mock_install.assert_called_once_with(tmp_path, force=True)

    @patch("ccproxy.cli.run_with_proxy")
    def test_main_run_command(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test main with run command."""
        cmd = Run(command=["echo", "hello", "world"])
        main(cmd, config_dir=tmp_path)

        mock_run.assert_called_once_with(tmp_path, ["echo", "hello", "world"])

    def test_main_run_no_args(self, tmp_path: Path, capsys) -> None:
        """Test main run command without arguments."""
        cmd = Run(command=[])

        with pytest.raises(SystemExit) as exc_info:
            main(cmd, config_dir=tmp_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No command specified" in captured.err
        assert "Usage: ccproxy run <command>" in captured.err

    def test_main_default_config_dir(self, tmp_path: Path) -> None:
        """Test main uses default config directory when not specified."""
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("ccproxy.cli.CCProxyManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            cmd = Status()
            main(cmd)

            # Check that the manager was created with the default config dir
            mock_manager_class.assert_called_once_with(tmp_path / ".ccproxy")
            mock_manager.status.assert_called_once()
