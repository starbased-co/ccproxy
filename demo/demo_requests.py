#!/usr/bin/env python3
"""Demo script showing CCProxy routing different types of requests."""

import asyncio
from pathlib import Path
from typing import Any

from ccproxy.config import CCProxyConfig, clear_config_instance, set_config_instance
from ccproxy.handler import CCProxyHandler


async def demo_request(handler: CCProxyHandler, request_data: dict[str, Any], description: str) -> None:
    """Process a demo request and show routing decision."""
    print(f"\n{'='*60}")
    print(f"Demo: {description}")
    print(f"{'='*60}")

    # Show request details
    print("\nRequest:")
    print(f"  Model: {request_data.get('model', 'unknown')}")

    messages = request_data.get("messages", [])
    if messages:
        print("  Messages:")
        for msg in messages[:2]:  # Show first 2 messages
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:100]
            if len(content) == 100:
                content += "..."
            print(f"    - {role}: {content}")

    tools = request_data.get("tools", [])
    if tools:
        print("  Tools:")
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("function", {}).get("name", tool.get("name", "unknown"))
                print(f"    - {name}")

    # Process through handler
    user_api_key_dict = {}
    modified_data = await handler.async_pre_call_hook(
        request_data.copy(),  # Copy to avoid modifying original
        user_api_key_dict,
    )

    # Show routing result
    print("\nRouting Decision:")
    metadata = modified_data.get("metadata", {})
    print(f"  Classification: {metadata.get('ccproxy_label', 'unknown')}")
    print(f"  Original Model: {metadata.get('ccproxy_original_model', 'unknown')}")
    print(f"  Routed Model: {modified_data.get('model', 'unknown')}")


async def main():
    """Run CCProxy routing demos."""
    # Load demo config
    config_path = Path(__file__).parent / "demo_config.yaml"
    config = CCProxyConfig.from_litellm_config(config_path)
    set_config_instance(config)

    # Create handler
    handler = CCProxyHandler()

    print("\n" + "=" * 60)
    print("CCProxy Routing Demo")
    print("=" * 60)
    print("\nThis demo shows how CCProxy routes different types of requests")
    print("to appropriate models based on their content and properties.")

    # Demo 1: Simple request → default model
    await demo_request(
        handler,
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "What is the capital of France?"}],
        },
        "Simple Question → Default Model",
    )

    # Demo 2: Haiku model → background processing
    await demo_request(
        handler,
        {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": "Format this JSON: {name:'test',value:123}"}],
        },
        "Haiku Request → Background Model",
    )

    # Demo 3: Thinking tags → complex reasoning model
    await demo_request(
        handler,
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "<thinking>I need to solve this step by step...</thinking>\nProve that √2 is irrational.",
                },
            ],
        },
        "Thinking Request → Reasoning Model",
    )

    # Demo 4: Large context → efficient model
    large_context = "Lorem ipsum " * 20000  # ~60k chars ≈ 15k tokens
    await demo_request(
        handler,
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": f"Summarize this document: {large_context}"}],
        },
        "Large Context → Efficient Model",
    )

    # Demo 5: Web search tool → internet-enabled model
    await demo_request(
        handler,
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Search for the latest AI news"}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "web_search", "description": "Search the web for information"},
                }
            ],
        },
        "Web Search Request → Internet Model",
    )

    # Demo 6: Combined features (priority demonstration)
    await demo_request(
        handler,
        {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": f"<thinking>Analyze this</thinking>\n{large_context}"}],
            "tools": [{"type": "function", "function": {"name": "web_search", "description": "Search the web"}}],
        },
        "Combined Features → Highest Priority (Large Context)",
    )

    # Demo 7: Unknown model fallback
    await demo_request(
        handler,
        {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "<thinking>Complex problem</thinking>"}],
        },
        "Non-Claude Model → Original Model (Fallback)",
    )

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)

    # Cleanup
    clear_config_instance()


if __name__ == "__main__":
    asyncio.run(main())
