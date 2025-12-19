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
    assert "# ccproxy shell integration" in captured.out
    assert "ccproxy_check_running()" in captured.out
    assert "alias claude='ccproxy run claude'" in captured.out
    assert "precmd_functions" in captured.out  # zsh-specific
    assert "PROMPT_COMMAND" not in captured.out  # bash-specific


def test_generate_shell_integration_auto_detect_bash(tmp_path: Path, capsys):
    """Test auto-detection of bash shell."""
    with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
        generate_shell_integration(tmp_path, shell="auto", install=False)  # noqa: S604

    captured = capsys.readouterr()
    assert "# ccproxy shell integration" in captured.out
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
    output = captured.out.replace("\n", "")  # Handle console line wrapping
    assert "# ccproxy shell integration" in output
    # Check the path components separately to handle line breaks
    assert str(tmp_path) in output
    # Check for lock file by looking for the pattern
    assert "local" in output
    assert "pid_file=" in output
    assert "litellm.lock" in output


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
    assert "# ccproxy shell integration" in content
    assert "ccproxy_check_running()" in content
    assert "precmd_functions" in content

    # Check output (handle console line wrapping)
    captured = capsys.readouterr()
    output = captured.out.replace("\n", "")
    assert "✓ ccproxy shell integration installed" in output
    assert str(zshrc) in output


def test_generate_shell_integration_install_bash(tmp_path: Path, capsys):
    """Test installing integration to bash config."""
    # Create a fake .bashrc
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# Existing bash config\n")

    with patch("pathlib.Path.home", return_value=tmp_path):
        generate_shell_integration(tmp_path, shell="bash", install=True)  # noqa: S604

    # Check installation
    content = bashrc.read_text()
    assert "# ccproxy shell integration" in content
    assert "ccproxy_check_running()" in content
    assert "PROMPT_COMMAND" in content

    # Check output (handle console line wrapping)
    captured = capsys.readouterr()
    output = captured.out.replace("\n", "")
    assert "✓ ccproxy shell integration installed" in output
    assert str(bashrc) in output


def test_generate_shell_integration_already_installed(tmp_path: Path):
    """Test handling of already installed integration."""
    # Create a fake .zshrc with existing integration
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# Existing config\n# ccproxy shell integration\n# Already installed\n")

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
    assert "# ccproxy shell integration" in zshrc.read_text()


def test_shell_integration_script_content(tmp_path: Path, capsys):
    """Test the generated shell integration script content."""
    generate_shell_integration(tmp_path, shell="bash", install=False)  # noqa: S604

    captured = capsys.readouterr()
    output = captured.out.replace("\n", "")

    # Check key components (handle line breaks)
    assert str(tmp_path) in output  # Path is included
    assert "litellm.lock" in output  # Lock file referenced
    assert 'kill -0 "$pid"' in output  # Process check
    assert "alias claude='ccproxy run claude'" in output
    assert "unalias claude 2>/dev/null || true" in output
    assert "ccproxy_setup_alias" in output
