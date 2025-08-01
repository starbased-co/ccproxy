"""Test OAuth token forwarding for Claude CLI requests."""

from unittest.mock import MagicMock

import pytest

from ccproxy.handler import CCProxyHandler


@pytest.mark.asyncio
async def test_oauth_forwarding_for_claude_cli():
    """Test that OAuth tokens are forwarded for claude-cli requests."""
    handler = CCProxyHandler()

    # Mock request with claude-cli user agent
    mock_request = MagicMock()
    mock_request.headers = {
        "user-agent": "claude-cli/1.0.62 (external, cli)",
        "authorization": "Bearer sk-ant-oat01-test-token-123",
    }

    # Test data for Anthropic model
    data = {"model": "anthropic/claude-3-5-haiku-20241022", "messages": [{"role": "user", "content": "test"}]}

    user_api_key_dict = {}
    kwargs = {"request": mock_request}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was added as x-api-key
    assert "extra_headers" in result
    assert result["extra_headers"]["x-api-key"] == "sk-ant-oat01-test-token-123"


@pytest.mark.asyncio
async def test_no_oauth_forwarding_for_non_claude_cli():
    """Test that OAuth tokens are NOT forwarded for non-claude-cli requests."""
    handler = CCProxyHandler()

    # Mock request with different user agent
    mock_request = MagicMock()
    mock_request.headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "authorization": "Bearer sk-ant-oat01-test-token-123",
    }

    # Test data for Anthropic model
    data = {"model": "anthropic/claude-3-5-haiku-20241022", "messages": [{"role": "user", "content": "test"}]}

    user_api_key_dict = {}
    kwargs = {"request": mock_request}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was NOT added
    assert "extra_headers" not in result or "x-api-key" not in result.get("extra_headers", {})


@pytest.mark.asyncio
async def test_no_oauth_forwarding_for_non_anthropic_models():
    """Test that OAuth tokens are NOT forwarded for non-Anthropic models."""
    handler = CCProxyHandler()

    # Mock request with claude-cli user agent
    mock_request = MagicMock()
    mock_request.headers = {
        "user-agent": "claude-cli/1.0.62 (external, cli)",
        "authorization": "Bearer sk-ant-oat01-test-token-123",
    }

    # Test data for non-Anthropic model
    data = {"model": "gemini-2.5-pro", "messages": [{"role": "user", "content": "test"}]}

    user_api_key_dict = {}
    kwargs = {"request": mock_request}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was NOT added
    assert "extra_headers" not in result or "x-api-key" not in result.get("extra_headers", {})


@pytest.mark.asyncio
async def test_oauth_forwarding_handles_missing_bearer_prefix():
    """Test that OAuth forwarding handles missing Bearer prefix gracefully."""
    handler = CCProxyHandler()

    # Mock request with claude-cli user agent but no Bearer prefix
    mock_request = MagicMock()
    mock_request.headers = {
        "user-agent": "claude-cli/1.0.62 (external, cli)",
        "authorization": "sk-ant-oat01-test-token-123",  # Missing "Bearer " prefix
    }

    # Test data for Anthropic model
    data = {"model": "anthropic/claude-3-5-haiku-20241022", "messages": [{"role": "user", "content": "test"}]}

    user_api_key_dict = {}
    kwargs = {"request": mock_request}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was NOT added (because Bearer prefix is missing)
    assert "extra_headers" not in result or "x-api-key" not in result.get("extra_headers", {})


@pytest.mark.asyncio
async def test_oauth_forwarding_preserves_existing_extra_headers():
    """Test that OAuth forwarding preserves existing extra_headers."""
    handler = CCProxyHandler()

    # Mock request with claude-cli user agent
    mock_request = MagicMock()
    mock_request.headers = {
        "user-agent": "claude-cli/1.0.62 (external, cli)",
        "authorization": "Bearer sk-ant-oat01-test-token-123",
    }

    # Test data with existing extra_headers
    data = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "extra_headers": {"existing-header": "existing-value"},
    }

    user_api_key_dict = {}
    kwargs = {"request": mock_request}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify both headers are present
    assert "extra_headers" in result
    assert result["extra_headers"]["x-api-key"] == "sk-ant-oat01-test-token-123"
    assert result["extra_headers"]["existing-header"] == "existing-value"
