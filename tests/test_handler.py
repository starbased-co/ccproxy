"""Tests for CCProxyHandler."""

from ccproxy.handler import CCProxyHandler


def test_handler_initialization() -> None:
    """Test that CCProxyHandler can be initialized."""
    handler = CCProxyHandler()
    assert handler is not None
    assert isinstance(handler, CCProxyHandler)
