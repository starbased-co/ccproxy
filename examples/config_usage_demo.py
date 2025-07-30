#!/usr/bin/env python3
"""Demo script showing configuration usage patterns."""

import asyncio
import os
from pathlib import Path

import yaml

from ccproxy import CCProxyConfig, ConfigProvider, get_config


async def singleton_demo() -> None:
    """Demonstrate singleton pattern usage."""
    print("🔧 Singleton Pattern Demo")
    print("-" * 50)

    # Get the singleton config instance
    config = get_config()
    print(f"Context threshold: {config.context_threshold}")
    print(f"Debug mode: {config.debug}")

    # Multiple calls return the same instance
    config2 = get_config()
    print(f"Same instance: {config is config2}")

    # Access nested configs
    if config.metrics:
        print(f"Metrics port: {config.metrics.port}")
    if config.logging:
        print(f"Log level: {config.logging.level}")
    print()


async def dependency_injection_demo() -> None:
    """Demonstrate dependency injection pattern."""
    print("💉 Dependency Injection Demo")
    print("-" * 50)

    # Create a provider with custom config
    custom_config = CCProxyConfig(
        context_threshold=45000,
        debug=True,
        metrics={"enabled": False},
    )
    provider = ConfigProvider(custom_config)

    # Use the provider
    config = provider.get()
    print(f"Custom context threshold: {config.context_threshold}")
    print(f"Custom debug mode: {config.debug}")

    # Multiple providers can coexist
    provider2 = ConfigProvider(CCProxyConfig(context_threshold=70000))

    print(f"Provider 1 threshold: {provider.get().context_threshold}")
    print(f"Provider 2 threshold: {provider2.get().context_threshold}")
    print(f"Independent instances: {provider.get() is not provider2.get()}")
    print()


async def hot_reload_integration_demo() -> None:
    """Demonstrate hot-reload with singleton pattern."""
    print("🔄 Hot-Reload Integration Demo")
    print("-" * 50)

    # Create a demo config file
    config_path = Path("demo_singleton_config.yaml")
    initial_config = {
        "context_threshold": 55000,
        "reload_config_on_change": True,
        "metrics": {"enabled": True, "port": 9191},
    }

    with config_path.open("w") as f:
        yaml.dump(initial_config, f)

    # Set config path
    os.environ["LITELLM_CONFIG_PATH"] = str(config_path)

    try:
        # Use singleton pattern
        config = get_config()
        print(f"Initial threshold: {config.context_threshold}")

        # Simulate config update
        await asyncio.sleep(1)

        updated_config = {
            "context_threshold": 65000,
            "reload_config_on_change": True,
            "metrics": {"enabled": False, "port": 8181},
        }

        with config_path.open("w") as f:
            yaml.dump(updated_config, f)

        # Reload config manually (or use watcher)
        from ccproxy import reload_config

        new_config = reload_config()

        print(f"Updated threshold: {new_config.context_threshold}")
        print(f"Metrics enabled: {new_config.metrics.enabled}")

    finally:
        # Cleanup
        config_path.unlink(missing_ok=True)
    print()


class ServiceWithInjectedConfig:
    """Example service using dependency injection."""

    def __init__(self, config_provider: ConfigProvider) -> None:
        """Initialize with a config provider."""
        self._config_provider = config_provider

    def process_request(self, token_count: int) -> str:
        """Process a request using injected config."""
        config = self._config_provider.get()

        if token_count > config.context_threshold:
            return "large_context"
        elif config.debug:
            return "debug_mode"
        else:
            return "default"


async def service_demo() -> None:
    """Demonstrate using config in a service."""
    print("🏗️  Service with Injected Config Demo")
    print("-" * 50)

    # Create service with injected config
    provider = ConfigProvider(CCProxyConfig(context_threshold=50000, debug=True))
    service = ServiceWithInjectedConfig(provider)

    # Test different scenarios
    print(f"30k tokens: {service.process_request(30000)}")
    print(f"60k tokens: {service.process_request(60000)}")

    # Update config
    provider.set(CCProxyConfig(context_threshold=40000, debug=False))
    print("Config updated...")
    print(f"45k tokens: {service.process_request(45000)}")
    print()


async def main() -> None:
    """Run all demos."""
    print("🚀 CCProxy Configuration Usage Demo")
    print("=" * 50)
    print()

    await singleton_demo()
    await dependency_injection_demo()
    await hot_reload_integration_demo()
    await service_demo()

    print("✅ All demos complete!")


if __name__ == "__main__":
    asyncio.run(main())
