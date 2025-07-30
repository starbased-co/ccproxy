#!/usr/bin/env python3
"""Test script to verify CCProxy routing via LiteLLM proxy."""

import requests

# LiteLLM proxy endpoint
PROXY_URL = "http://localhost:8000/v1/chat/completions"


def test_routing(name: str, request_data: dict) -> None:
    """Send a request to LiteLLM proxy and show routing result."""
    print(f"\n{'='*50}")
    print(f"Test: {name}")
    print(f"{'='*50}")

    # Show request
    print("\nRequest:")
    print(f"  Model: {request_data['model']}")
    if request_data.get("messages"):
        print(f"  Message: {request_data['messages'][-1]['content'][:80]}...")
    if request_data.get("tools"):
        print(f"  Tools: {[t.get('function', {}).get('name', 'unknown') for t in request_data['tools']]}")

    # Send request
    print("\nSending to LiteLLM proxy...")

    try:
        response = requests.post(PROXY_URL, json=request_data, headers={"Content-Type": "application/json"}, timeout=30)

        if response.status_code == 200:
            result = response.json()
            print("✓ Success! Response received")
            print(f"  Model used: {result.get('model', 'unknown')}")

            # The actual model used is in the response
            if "choices" in result and result["choices"]:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"  Response preview: {content[:100]}...")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed. Is the LiteLLM proxy running?")
        print("  Run: ./start_litellm_proxy.sh")
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    """Run routing tests."""
    print("\nCCProxy Routing Tests via LiteLLM Proxy")
    print("=" * 50)
    print("Make sure the proxy is running: ./start_litellm_proxy.sh")

    # Test 1: Default routing
    test_routing(
        "Default Model (Simple Query)",
        {"model": "claude-3-5-sonnet-20241022", "messages": [{"role": "user", "content": "What is 2+2?"}]},
    )

    # Test 2: Background routing (Haiku)
    test_routing(
        "Background Model (Haiku Request)",
        {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": "Format this JSON: {a:1,b:2}"}],
        },
    )

    # Test 3: Thinking routing
    test_routing(
        "Thinking Model (Complex Reasoning)",
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {
                    "role": "user",
                    "content": "<thinking>I need to analyze this carefully</thinking>\nExplain quantum entanglement",
                }
            ],
        },
    )

    # Test 4: Web search routing
    test_routing(
        "Web Search Model (Internet Query)",
        {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "What are the latest AI developments?"}],
            "tools": [{"type": "function", "function": {"name": "web_search", "description": "Search the web"}}],
        },
    )

    # Test 5: Large context routing
    large_text = "Please analyze this text. " * 5000  # ~30k chars
    test_routing(
        "Large Context Model (>60k tokens)",
        {"model": "claude-3-5-sonnet-20241022", "messages": [{"role": "user", "content": large_text}]},
    )

    print("\n" + "=" * 50)
    print("Tests Complete!")
    print("Check the proxy logs to see CCProxy routing decisions")
    print("=" * 50)


if __name__ == "__main__":
    main()
