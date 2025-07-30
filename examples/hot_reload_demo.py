#!/usr/bin/env python3
"""Demo script showing hot-reload functionality."""

import asyncio
import os
from pathlib import Path

import yaml

from ccproxy.config import get_config
from ccproxy.watcher import start_config_watcher, stop_config_watcher


def on_config_reload() -> None:
    """Callback when config is reloaded."""
    config = get_config()
    print(f"✓ Config reloaded! New context threshold: {config.context_threshold}")
    print(f"  Debug mode: {config.debug}")
    print(f"  Metrics enabled: {config.metrics.enabled}")


async def main() -> None:
    """Run the hot-reload demo."""
    # Create a demo config file
    config_path = Path("demo_config.yaml")

    print("🚀 Starting CCProxy Config Hot-Reload Demo")
    print("-" * 50)

    # Create initial config
    initial_config = {
        "context_threshold": 50000,
        "debug": False,
        "metrics": {
            "enabled": True,
            "port": 9090,
        },
        "logging": {
            "level": "INFO",
        },
    }

    with config_path.open("w") as f:
        yaml.dump(initial_config, f)

    # Set config path in environment
    os.environ["LITELLM_CONFIG_PATH"] = str(config_path)

    # Load initial config
    config = get_config()
    print("Initial config loaded:")
    print(f"  Context threshold: {config.context_threshold}")
    print(f"  Debug mode: {config.debug}")
    print(f"  Metrics enabled: {config.metrics.enabled}")
    print()

    # Start watching for changes
    start_config_watcher(config_path, on_config_reload)
    print(f"👀 Watching {config_path} for changes...")
    print("   (Try editing the file to see hot-reload in action)")
    print()

    # Simulate config changes
    await asyncio.sleep(2)

    print("📝 Updating config file...")
    updated_config = {
        "context_threshold": 60000,
        "debug": True,
        "metrics": {
            "enabled": False,
            "port": 8080,
        },
        "logging": {
            "level": "DEBUG",
        },
    }

    with config_path.open("w") as f:
        yaml.dump(updated_config, f)

    # Wait for reload
    await asyncio.sleep(2)

    # Check if hot-reload is enabled in config
    if config.reload_config_on_change:
        print("✅ Hot-reload is enabled in configuration")
    else:
        print("⚠️  Hot-reload is not enabled in configuration")
        print("   Set 'reload_config_on_change: true' to enable")

    print()
    print("Demo complete! Press Ctrl+C to exit...")

    try:
        # Keep running
        await asyncio.sleep(300)
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        stop_config_watcher()
        config_path.unlink(missing_ok=True)
        print("\n🛑 Stopped watching for config changes")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
