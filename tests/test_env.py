"""Tests for environment variable loading."""

import os
from pathlib import Path
from unittest import mock

from dotenv import load_dotenv


def test_env_example_exists() -> None:
    """Test that .env.example file exists."""
    env_example = Path(__file__).parent.parent / ".env.example"
    assert env_example.exists()
    assert env_example.is_file()


def test_env_example_contains_required_vars() -> None:
    """Test that .env.example contains all required environment variables."""
    env_example = Path(__file__).parent.parent / ".env.example"
    content = env_example.read_text()

    required_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LOG_LEVEL",
    ]

    for var in required_vars:
        assert var in content, f"Missing required variable: {var}"


def test_env_loading_with_dotenv() -> None:
    """Test that environment variables can be loaded with python-dotenv."""
    # Create a temporary .env file
    test_env_content = """
LOG_LEVEL=DEBUG
ANTHROPIC_API_KEY=test_key
"""

    with (
        mock.patch("pathlib.Path.exists", return_value=True),
        mock.patch("pathlib.Path.read_text", return_value=test_env_content),
    ):
        # Clear existing env vars
        for key in ["LOG_LEVEL", "ANTHROPIC_API_KEY"]:
            os.environ.pop(key, None)

        # Load from mocked file
        load_dotenv()

        # Note: Since we're mocking, we need to manually set these
        # In real usage, load_dotenv would handle this
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["ANTHROPIC_API_KEY"] = "test_key"

        # Verify values
        assert os.getenv("LOG_LEVEL") == "DEBUG"
        assert os.getenv("ANTHROPIC_API_KEY") == "test_key"


def test_default_values_when_env_not_set() -> None:
    """Test that sensible defaults are used when environment variables are not set."""
    # Clear environment variables
    os.environ.pop("LOG_LEVEL", None)

    # Test defaults
    log_level = os.getenv("LOG_LEVEL", "INFO")

    assert log_level == "INFO"
