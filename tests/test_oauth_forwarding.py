"""Test OAuth token forwarding for Claude CLI requests."""

import pytest

from ccproxy.handler import CCProxyHandler


@pytest.mark.asyncio
async def test_oauth_forwarding_for_claude_cli():
    """Test that OAuth tokens are forwarded for claude-cli requests."""
    handler = CCProxyHandler()

    # Test data for Anthropic model with required structure
    data = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was forwarded in authorization header
    assert "provider_specific_header" in result
    assert "extra_headers" in result["provider_specific_header"]
    assert result["provider_specific_header"]["extra_headers"]["authorization"] == "Bearer sk-ant-oat01-test-token-123"


@pytest.mark.asyncio
async def test_no_oauth_forwarding_for_non_claude_cli():
    """Test that OAuth tokens are NOT forwarded for non-claude-cli requests."""
    handler = CCProxyHandler()

    # Test data with different user agent
    data = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was NOT forwarded
    assert "authorization" not in result["provider_specific_header"]["extra_headers"]


@pytest.mark.asyncio
async def test_no_oauth_forwarding_for_non_anthropic_models():
    """Test that OAuth tokens are NOT forwarded for non-Anthropic models."""
    handler = CCProxyHandler()

    # Test data for non-Anthropic model
    data = {
        "model": "gemini-2.5-pro",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was NOT forwarded
    assert "authorization" not in result["provider_specific_header"]["extra_headers"]


@pytest.mark.asyncio
async def test_oauth_forwarding_handles_missing_headers():
    """Test that OAuth forwarding handles missing headers gracefully."""
    handler = CCProxyHandler()

    # Test data with missing secret_fields
    data = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        # secret_fields is missing
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook - should not crash
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify no OAuth token was added
    assert "authorization" not in result["provider_specific_header"]["extra_headers"]


@pytest.mark.asyncio
async def test_oauth_forwarding_preserves_existing_extra_headers():
    """Test that OAuth forwarding preserves existing extra_headers."""
    handler = CCProxyHandler()

    # Test data with existing extra_headers
    data = {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {"existing-header": "existing-value"}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify both headers are present
    assert "provider_specific_header" in result
    assert "extra_headers" in result["provider_specific_header"]
    assert result["provider_specific_header"]["extra_headers"]["authorization"] == "Bearer sk-ant-oat01-test-token-123"
    assert result["provider_specific_header"]["extra_headers"]["existing-header"] == "existing-value"


@pytest.mark.asyncio
async def test_oauth_forwarding_with_claude_prefix_model():
    """Test that OAuth tokens are forwarded for models starting with 'claude'."""
    handler = CCProxyHandler()

    # Test data for model starting with 'claude'
    data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # Verify OAuth token was forwarded
    assert result["provider_specific_header"]["extra_headers"]["authorization"] == "Bearer sk-ant-oat01-test-token-123"


@pytest.mark.asyncio
async def test_oauth_forwarding_with_routed_model():
    """Test that OAuth forwarding works with routed models."""
    handler = CCProxyHandler()

    # Test data that will be routed to an Anthropic model
    data = {
        "model": "default",  # This will be routed to an anthropic model
        "messages": [{"role": "user", "content": "test"}],
        "metadata": {},
        "provider_specific_header": {"extra_headers": {}},
        "proxy_server_request": {"headers": {"user-agent": "claude-cli/1.0.62 (external, cli)"}},
        "secret_fields": {"raw_headers": {"authorization": "Bearer sk-ant-oat01-test-token-123"}},
    }

    user_api_key_dict = {}
    kwargs = {}

    # Call the hook
    result = await handler.async_pre_call_hook(data, user_api_key_dict, **kwargs)

    # The routed model should be checked in the handler
    # If it routes to an anthropic model, OAuth should be forwarded
    # This test verifies the logic works with routing
    if "anthropic/" in result.get("model", "") or result.get("model", "").startswith("claude"):
        expected_token = "Bearer sk-ant-oat01-test-token-123"  # noqa: S105
        assert result["provider_specific_header"]["extra_headers"]["authorization"] == expected_token
