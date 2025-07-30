"""Example demonstrating hot-reload of model router configuration.

This example shows how the ModelRouter automatically updates its
model mappings when the configuration file changes.
"""

import asyncio
import os
from pathlib import Path

import yaml

from ccproxy import get_router, start_config_watcher, stop_config_watcher
from ccproxy.llm_router import llm_router


def display_router_state() -> None:
    """Display current router state."""
    router = get_router()

    print("\n=== Router State ===")
    print(f"Available models: {router.get_available_models()}")

    print("\nModel mappings:")
    for label in ["default", "background", "think", "web_search", "large_context"]:
        model = router.get_model_for_label(label)
        if model:
            underlying = model["litellm_params"].get("model", "unknown")
            print(f"  {label} -> {underlying}")
        else:
            print(f"  {label} -> None")

    print("\nModel groups:")
    for underlying_model, aliases in router.model_group_alias.items():
        print(f"  {underlying_model}: {aliases}")


async def main() -> None:
    """Main demo function."""
    # Create a temporary config file
    config_path = Path("demo_config.yaml")

    # Initial configuration
    initial_config = {
        "model_list": [
            {
                "model_name": "default",
                "litellm_params": {
                    "model": "gpt-4",
                    "api_key": "demo-key",
                },
                "model_info": {
                    "priority": "high",
                    "cost_per_token": 0.03,
                },
            },
            {
                "model_name": "background",
                "litellm_params": {
                    "model": "gpt-3.5-turbo",
                    "api_key": "demo-key",
                },
                "model_info": {
                    "priority": "low",
                    "cost_per_token": 0.002,
                },
            },
        ]
    }

    # Write initial config
    with open(config_path, "w") as f:
        yaml.dump(initial_config, f)

    # Set environment variable
    os.environ["LITELLM_CONFIG_PATH"] = str(config_path)

    try:
        print("Starting hot-reload demo...")
        print("Initial configuration loaded")
        display_router_state()

        # Start config watcher
        start_config_watcher(config_path)
        print("\n✓ Config watcher started - monitoring for changes")

        # Demonstrate LiteLLM hook access
        print("\n=== LiteLLM Hook Access ===")
        print(f"llm_router.get_available_models(): {llm_router.get_available_models()}")
        print(f"llm_router.is_model_available('background'): {llm_router.is_model_available('background')}")
        print(f"llm_router.is_model_available('think'): {llm_router.is_model_available('think')}")

        await asyncio.sleep(2)

        # Update configuration
        print("\n📝 Updating configuration file...")
        updated_config = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                        "api_key": "demo-key",
                    },
                    "model_info": {
                        "priority": "high",
                        "cost_per_token": 0.015,
                    },
                },
                {
                    "model_name": "background",
                    "litellm_params": {
                        "model": "claude-3-5-haiku-20241022",
                        "api_key": "demo-key",
                    },
                    "model_info": {
                        "priority": "low",
                        "cost_per_token": 0.0008,
                    },
                },
                {
                    "model_name": "think",
                    "litellm_params": {
                        "model": "o1-preview",
                        "api_key": "demo-key",
                    },
                    "model_info": {
                        "priority": "high",
                        "cost_per_token": 0.06,
                    },
                },
                {
                    "model_name": "web_search",
                    "litellm_params": {
                        "model": "perplexity/llama-3.1-sonar-large-128k-online",
                        "api_key": "demo-key",
                    },
                    "model_info": {
                        "priority": "medium",
                        "cost_per_token": 0.005,
                    },
                },
            ]
        }

        with open(config_path, "w") as f:
            yaml.dump(updated_config, f)

        # Wait for reload (debounce + processing)
        await asyncio.sleep(2)

        print("\n✓ Configuration reloaded automatically!")
        display_router_state()

        # Show updated LiteLLM hook access
        print("\n=== Updated LiteLLM Hook Access ===")
        print(f"llm_router.is_model_available('think'): {llm_router.is_model_available('think')}")
        print(f"llm_router.is_model_available('web_search'): {llm_router.is_model_available('web_search')}")

        # Get model with metadata
        think_model = llm_router.get_model_for_label("think")
        if think_model:
            print("\nThink model details:")
            print(f"  Model: {think_model['litellm_params']['model']}")
            print(f"  Priority: {think_model['model_info']['priority']}")
            print(f"  Cost per token: ${think_model['model_info']['cost_per_token']}")

        await asyncio.sleep(2)

        # Remove some models
        print("\n📝 Removing some models from configuration...")
        reduced_config = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {
                        "model": "claude-3-5-sonnet-20241022",
                        "api_key": "demo-key",
                    },
                },
            ]
        }

        with open(config_path, "w") as f:
            yaml.dump(reduced_config, f)

        await asyncio.sleep(2)

        print("\n✓ Configuration reduced - fallback logic active!")
        display_router_state()

        # Show fallback behavior
        print("\n=== Fallback Behavior ===")
        for label in ["background", "think", "web_search"]:
            model = llm_router.get_model_for_label(label)
            if model:
                print(f"{label} request -> fallback to: {model['model_name']}")

    finally:
        # Cleanup
        stop_config_watcher()
        print("\n✓ Config watcher stopped")

        if config_path.exists():
            config_path.unlink()
            print("✓ Demo config file removed")


if __name__ == "__main__":
    asyncio.run(main())
