"""Utility functions for ccproxy."""

from pathlib import Path
from typing import Any


def get_templates_dir() -> Path:
    """Get the path to the templates directory.

    This function handles both development (running from source) and
    production (installed package) scenarios.

    Returns:
        Path to the templates directory

    Raises:
        RuntimeError: If templates directory cannot be found
    """
    module_dir = Path(__file__).parent

    # Development mode: templates at project root
    dev_templates = module_dir.parent.parent / "templates"
    if dev_templates.exists() and (dev_templates / "ccproxy.yaml").exists():
        return dev_templates

    # Installed mode: templates inside the package
    package_templates = module_dir / "templates"
    if package_templates.exists() and (package_templates / "ccproxy.yaml").exists():
        return package_templates

    raise RuntimeError("Could not find templates directory. Please ensure ccproxy is properly installed.")


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


def calculate_duration_ms(start_time: Any, end_time: Any) -> float:
    """Calculate duration in milliseconds between two timestamps.

    Handles both float timestamps and timedelta objects.

    Args:
        start_time: Start timestamp (float or timedelta)
        end_time: End timestamp (float or timedelta)

    Returns:
        Duration in milliseconds, rounded to 2 decimal places
    """
    try:
        if isinstance(end_time, float) and isinstance(start_time, float):
            duration_ms = (end_time - start_time) * 1000
        else:
            # Handle timedelta objects or mixed types
            duration_seconds = (end_time - start_time).total_seconds()  # type: ignore[operator,unused-ignore,unreachable]
            duration_ms = duration_seconds * 1000
    except (TypeError, AttributeError):
        duration_ms = 0.0

    return round(duration_ms, 2)
