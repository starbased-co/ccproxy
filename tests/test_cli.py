"""Tests for the CCProxy CLI."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ccproxy.cli import (
    Install,
    LiteLLM,
    Run,
    install_config,
    litellm_with_config,
    main,
    run_with_proxy,
)


class TestLiteLLMWithConfig:
    """Test suite for litellm_with_config function."""

    def test_litellm_no_config(self, tmp_path: Path, capsys) -> None:
        """Test litellm when config doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            litellm_with_config(tmp_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Configuration not found" in captured.err
        assert "Run 'ccproxy install' first" in captured.err

    @patch("subprocess.run")
    def test_litellm_with_config_success(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test successful litellm execution."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("litellm: config")

        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit) as exc_info:
            litellm_with_config(tmp_path)

        assert exc_info.value.code == 0
        mock_run.assert_called_once_with(["litellm", "--config", str(config_file)])

    @patch("subprocess.run")
    def test_litellm_with_args(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test litellm with additional arguments."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("litellm: config")

        mock_run.return_value = Mock(returncode=0)

        with pytest.raises(SystemExit) as exc_info:
            litellm_with_config(tmp_path, args=["--debug", "--port", "8080"])

        assert exc_info.value.code == 0
        mock_run.assert_called_once_with(["litellm", "--config", str(config_file), "--debug", "--port", "8080"])

    @patch("subprocess.run")
    def test_litellm_command_not_found(self, mock_run: Mock, tmp_path: Path, capsys) -> None:
        """Test litellm when command is not found."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("litellm: config")

        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as exc_info:
            litellm_with_config(tmp_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "litellm command not found" in captured.err
        assert "pip install litellm" in captured.err

    @patch("subprocess.run")
    def test_litellm_keyboard_interrupt(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test litellm with keyboard interrupt."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("litellm: config")

        mock_run.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            litellm_with_config(tmp_path)

        assert exc_info.value.code == 130


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

    @patch("ccproxy.cli.litellm_with_config")
    def test_main_litellm_command(self, mock_litellm: Mock, tmp_path: Path) -> None:
        """Test main with litellm command."""
        cmd = LiteLLM(args=["--debug", "--port", "8080"])
        main(cmd, config_dir=tmp_path)

        mock_litellm.assert_called_once_with(tmp_path, args=["--debug", "--port", "8080"])

    @patch("ccproxy.cli.litellm_with_config")
    def test_main_litellm_no_args(self, mock_litellm: Mock, tmp_path: Path) -> None:
        """Test main with litellm command without args."""
        cmd = LiteLLM()
        main(cmd, config_dir=tmp_path)

        mock_litellm.assert_called_once_with(tmp_path, args=None)

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
            patch("ccproxy.cli.litellm_with_config") as mock_litellm,
        ):
            cmd = LiteLLM()
            main(cmd)

            # Check that litellm was called with the default config dir
            mock_litellm.assert_called_once_with(tmp_path / ".ccproxy", args=None)
