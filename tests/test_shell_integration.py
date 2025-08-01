"""Test shell integration functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ccproxy.cli import generate_shell_integration


def test_generate_shell_integration_auto_detect_zsh(tmp_path: Path, capsys):
    """Test auto-detection of zsh shell."""
    with patch.dict("os.environ", {"SHELL": "/usr/bin/zsh"}):
        generate_shell_integration(tmp_path, shell="auto", install=False)  # noqa: S604

    captured = capsys.readouterr()
    assert "# CCProxy shell integration" in captured.out
    assert "ccproxy_check_running()" in captured.out
    assert "alias claude='ccproxy run claude'" in captured.out
    assert "precmd_functions" in captured.out  # zsh-specific
    assert "PROMPT_COMMAND" not in captured.out  # bash-specific


def test_generate_shell_integration_auto_detect_bash(tmp_path: Path, capsys):
    """Test auto-detection of bash shell."""
    with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
        generate_shell_integration(tmp_path, shell="auto", install=False)  # noqa: S604

    captured = capsys.readouterr()
    assert "# CCProxy shell integration" in captured.out
    assert "ccproxy_check_running()" in captured.out
    assert "alias claude='ccproxy run claude'" in captured.out
    assert "PROMPT_COMMAND" in captured.out  # bash-specific
    assert "precmd_functions" not in captured.out  # zsh-specific


def test_generate_shell_integration_auto_detect_failure(tmp_path: Path):
    """Test auto-detection failure."""
    with patch.dict("os.environ", {"SHELL": "/bin/fish"}):
        with pytest.raises(SystemExit) as exc_info:
            generate_shell_integration(tmp_path, shell="auto", install=False)  # noqa: S604
        assert exc_info.value.code == 1


def test_generate_shell_integration_explicit_shell(tmp_path: Path, capsys):
    """Test explicit shell specification."""
    generate_shell_integration(tmp_path, shell="zsh", install=False)  # noqa: S604

    captured = capsys.readouterr()
    assert "# CCProxy shell integration" in captured.out
    # Check the path components separately to handle line breaks
    assert str(tmp_path) in captured.out
    # Check for lock file by looking for the pattern split across lines
    assert "local" in captured.out
    assert "pid_file=" in captured.out
    assert "itellm.lock" in captured.out  # Part of "litellm.lock" after line break


def test_generate_shell_integration_unsupported_shell(tmp_path: Path):
    """Test unsupported shell type."""
    with pytest.raises(SystemExit) as exc_info:
        generate_shell_integration(tmp_path, shell="fish", install=False)  # noqa: S604
    assert exc_info.value.code == 1


def test_generate_shell_integration_install_zsh(tmp_path: Path, capsys):
    """Test installing integration to zsh config."""
    # Create a fake .zshrc
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# Existing zsh config\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        generate_shell_integration(tmp_path, shell="zsh", install=True)  # noqa: S604

    # Check installation
    content = zshrc.read_text()
    assert "# CCProxy shell integration" in content
    assert "ccproxy_check_running()" in content
    assert "precmd_functions" in content

    # Check output
    captured = capsys.readouterr()
    assert "✓ CCProxy shell integration installed" in captured.out
    assert str(zshrc) in captured.out


def test_generate_shell_integration_install_bash(tmp_path: Path, capsys):
    """Test installing integration to bash config."""
    # Create a fake .bashrc
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# Existing bash config\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        generate_shell_integration(tmp_path, shell="bash", install=True)  # noqa: S604

    # Check installation
    content = bashrc.read_text()
    assert "# CCProxy shell integration" in content
    assert "ccproxy_check_running()" in content
    assert "PROMPT_COMMAND" in content

    # Check output
    captured = capsys.readouterr()
    assert "✓ CCProxy shell integration installed" in captured.out
    assert str(bashrc) in captured.out


def test_generate_shell_integration_already_installed(tmp_path: Path):
    """Test handling of already installed integration."""
    # Create a fake .zshrc with existing integration
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# Existing config\n# CCProxy shell integration\n# Already installed\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            generate_shell_integration(tmp_path, shell="zsh", install=True)  # noqa: S604
        assert exc_info.value.code == 0


def test_generate_shell_integration_creates_config_if_missing(tmp_path: Path):
    """Test that shell config file is created if it doesn't exist."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        generate_shell_integration(tmp_path, shell="zsh", install=True)  # noqa: S604

    # Check that .zshrc was created
    zshrc = tmp_path / ".zshrc"
    assert zshrc.exists()
    assert "# CCProxy shell integration" in zshrc.read_text()


def test_shell_integration_script_content(tmp_path: Path, capsys):
    """Test the generated shell integration script content."""
    generate_shell_integration(tmp_path, shell="bash", install=False)  # noqa: S604

    captured = capsys.readouterr()

    # Check key components
    assert str(tmp_path) in captured.out  # Path is included
    assert "itellm.lock" in captured.out  # Lock file name (partial after line break)
    assert 'kill -0 "$pid"' in captured.out  # Process check
    assert "alias claude='ccproxy run claude'" in captured.out
    assert "unalias claude 2>/dev/null || true" in captured.out
    assert "ccproxy_setup_alias" in captured.out
