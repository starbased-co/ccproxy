"""Utility functions for ccproxy."""

import sys
from pathlib import Path


def get_templates_dir() -> Path:
    """Get the path to the templates directory.

    This function handles both development (running from source) and
    production (installed package) scenarios.

    Returns:
        Path to the templates directory

    Raises:
        RuntimeError: If templates directory cannot be found
    """
    # First, try relative to this module (development mode)
    module_dir = Path(__file__).parent
    dev_templates = module_dir.parent.parent / "templates"
    if dev_templates.exists():
        return dev_templates

    # Then try in site-packages (installed mode)
    # When installed, templates will be at the package root level
    for path in sys.path:
        site_templates = Path(path) / "templates"
        if site_templates.exists() and (site_templates / "ccproxy.yaml").exists():
            return site_templates

    # Try one more location - next to the package directory
    package_templates = module_dir.parent / "templates"
    if package_templates.exists():
        return package_templates

    raise RuntimeError("Could not find templates directory. " "Please ensure ccproxy is properly installed.")


def get_template_file(filename: str) -> Path:
    """Get the path to a specific template file.

    Args:
        filename: Name of the template file

    Returns:
        Path to the template file

    Raises:
        FileNotFoundError: If the template file doesn't exist
    """
    templates_dir = get_templates_dir()
    template_path = templates_dir / filename

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {filename}")

    return template_path
