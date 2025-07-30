#!/usr/bin/env python3
"""Demo showing CCProxy integration with LiteLLM proxy server."""

import asyncio
import os
from pathlib import Path

# Import CCProxy components
from ccproxy.config import CCProxyConfig, set_config_instance
from ccproxy.handler import CCProxyHandler


async def demo_with_litellm():
    """Demonstrate CCProxy working with actual LiteLLM completion calls."""

    # Load config
    config_path = Path(__file__).parent / "demo_config.yaml"
    config = CCProxyConfig.from_litellm_config(config_path)
    set_config_instance(config)

    # Create and register CCProxy handler
    handler = CCProxyHandler()

    # In a real LiteLLM proxy setup, you would add this to callbacks
    # For demo, we'll use the routing function directly
    from ccproxy.handler import ccproxy_get_model

    print("\n" + "=" * 60)
    print("CCProxy + LiteLLM Integration Demo")
    print("=" * 60)
    print("\nThis demo shows how CCProxy integrates with LiteLLM")
    print("Note: Actual API calls are disabled in this demo")
    print("=" * 60)

    # Example 1: Simple routing demonstration
    print("\nExample 1: Routing Logic Demonstration")
    print("-" * 40)

    requests = [
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "description": "Simple request",
        },
        {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": "Format this"}],
            "description": "Background task",
        },
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "<thinking>Complex analysis</thinking>\nSolve this"}],
            "description": "Thinking request",
        },
    ]

    for req in requests:
        routed_model = ccproxy_get_model(req)
        print(f"\n{req['description']}:")
        print(f"  Input model: {req['model']}")
        print(f"  Routed to: {routed_model}")

    # Example 2: Show how it would work in LiteLLM proxy
    print("\n\nExample 2: LiteLLM Proxy Integration Pattern")
    print("-" * 40)
    print("""
In your LiteLLM proxy config, you would use CCProxy like this:

```python
from litellm.proxy.proxy_server import ProxyConfig, initialize
from ccproxy.handler import CCProxyHandler

# Load proxy config
config = ProxyConfig()

# Add CCProxy as a callback
ccproxy_handler = CCProxyHandler()
config.litellm_settings["callbacks"] = [ccproxy_handler]

# The routing happens automatically in async_pre_call_hook!
```
""")

    # Example 3: Show metadata tracking
    print("\nExample 3: Request Metadata Tracking")
    print("-" * 40)

    # Process a request through the handler to show metadata
    request_data = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "<thinking>Need to analyze this problem</thinking>\nWhat is P=NP?"}],
    }

    # Process through handler
    modified_data = await handler.async_pre_call_hook(request_data, {})

    print("\nOriginal request model:", request_data["model"])
    print("After CCProxy processing:")
    print(f"  Routed model: {modified_data['model']}")
    print("  Metadata added:")
    for key, value in modified_data.get("metadata", {}).items():
        if key.startswith("ccproxy_"):
            print(f"    - {key}: {value}")


async def main():
    """Run the demo."""
    await demo_with_litellm()

    print("\n" + "=" * 60)
    print("Integration Demo Complete!")
    print("=" * 60)
    print("\nTo use CCProxy with a real LiteLLM proxy server:")
    print("1. Start LiteLLM proxy with the demo config")
    print("2. Register CCProxyHandler in callbacks")
    print("3. All requests will be automatically routed!")
    print("=" * 60)


if __name__ == "__main__":
    # Note: We're not making actual API calls in this demo
    # Set dummy keys to prevent errors
    os.environ.setdefault("ANTHROPIC_API_KEY", "demo-key")
    os.environ.setdefault("GOOGLE_API_KEY", "demo-key")
    os.environ.setdefault("PERPLEXITY_API_KEY", "demo-key")

    asyncio.run(main())
