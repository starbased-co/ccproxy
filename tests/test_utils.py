"""Tests for ccproxy utilities."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ccproxy.utils import get_template_file, get_templates_dir


class TestGetTemplatesDir:
    """Test suite for get_templates_dir function."""

    def test_templates_dir_development_mode(self, tmp_path: Path) -> None:
        """Test finding templates in development mode."""
        # Create a fake development structure
        src_dir = tmp_path / "src" / "ccproxy"
        src_dir.mkdir(parents=True)
        utils_file = src_dir / "utils.py"
        utils_file.touch()

        # Create templates directory two levels up
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "ccproxy.yaml").touch()

        # Mock __file__ to point to our fake utils.py
        with patch("ccproxy.utils.__file__", str(utils_file)):
            result = get_templates_dir()
            assert result == templates_dir

    def test_templates_dir_installed_mode(self, tmp_path: Path) -> None:
        """Test finding templates in sys.path."""
        # Create a fake module location
        fake_module = tmp_path / "fake" / "location" / "ccproxy"
        fake_module.mkdir(parents=True)
        fake_utils = fake_module / "utils.py"
        fake_utils.touch()

        # Create site-packages structure
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        templates_dir = site_packages / "templates"
        templates_dir.mkdir()
        (templates_dir / "ccproxy.yaml").touch()

        # Mock sys.path and __file__
        with patch("sys.path", [str(site_packages), "/other/path"]), patch("ccproxy.utils.__file__", str(fake_utils)):
            result = get_templates_dir()
            assert result == templates_dir

    def test_templates_dir_not_found(self) -> None:
        """Test error when templates directory not found."""
        # Mock __file__ to point to a location without templates
        with (
            patch("ccproxy.utils.__file__", "/nowhere/utils.py"),
            patch.object(Path, "exists", return_value=False),
            pytest.raises(RuntimeError) as exc_info,
        ):
            get_templates_dir()

        assert "Could not find templates directory" in str(exc_info.value)


class TestGetTemplateFile:
    """Test suite for get_template_file function."""

    @patch("ccproxy.utils.get_templates_dir")
    def test_get_existing_template(self, mock_get_templates: Mock, tmp_path: Path) -> None:
        """Test getting an existing template file."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "test.yaml"
        template_file.write_text("test content")

        mock_get_templates.return_value = templates_dir

        result = get_template_file("test.yaml")
        assert result == template_file

    @patch("ccproxy.utils.get_templates_dir")
    def test_get_nonexistent_template(self, mock_get_templates: Mock, tmp_path: Path) -> None:
        """Test error when template file doesn't exist."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        mock_get_templates.return_value = templates_dir

        with pytest.raises(FileNotFoundError) as exc_info:
            get_template_file("missing.yaml")

        assert "Template file not found: missing.yaml" in str(exc_info.value)
