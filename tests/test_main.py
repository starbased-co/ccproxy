"""Tests for ccproxy __main__ module."""

import runpy
import sys
from unittest.mock import patch


class TestMain:
    """Test suite for __main__ module."""

    @patch("ccproxy.cli.main")
    def test_main_entry_point(self, mock_main) -> None:
        """Test that __main__ calls the CLI main function."""
        # Run the module as __main__
        with patch.object(sys, "argv", ["ccproxy"]):
            runpy.run_module("ccproxy", run_name="__main__")

        # Verify it called the CLI main
        mock_main.assert_called_once()
