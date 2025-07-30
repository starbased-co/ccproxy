"""Configuration management for ccproxy."""

import os
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]


class CCProxySettings(BaseModel):
    """CCProxy-specific settings from LiteLLM config."""

    context_threshold: int = Field(default=60000, ge=1000, description="Token threshold for large_context")
    debug: bool = Field(default=False, description="Enable debug logging")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    reload_config_on_change: bool = Field(default=False, description="Enable hot-reload of config")


class LiteLLMConfig(BaseModel):
    """Representation of LiteLLM proxy configuration."""

    model_list: list[dict[str, Any]] = Field(default_factory=list)
    litellm_settings: dict[str, Any] = Field(default_factory=dict)
    general_settings: dict[str, Any] = Field(default_factory=dict)
    ccproxy_settings: CCProxySettings = Field(default_factory=CCProxySettings)


class CCProxyConfig(BaseSettings):  # type: ignore[misc]
    """Main configuration for ccproxy that reads from LiteLLM proxy config."""

    model_config = SettingsConfigDict(
        env_prefix="CCPROXY_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core settings from ccproxy_settings section
    context_threshold: int = Field(default=60000, ge=1000)
    debug: bool = False
    metrics_enabled: bool = True
    reload_config_on_change: bool = False

    # Path to LiteLLM config
    litellm_config_path: Path = Field(default_factory=lambda: Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml")))

    # Cached LiteLLM config
    _litellm_config: LiteLLMConfig | None = None

    @classmethod
    def from_litellm_config(cls, yaml_path: Path, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from LiteLLM proxy YAML file."""
        config_data: dict[str, Any] = {}

        # Load YAML if it exists
        if yaml_path.exists():
            with yaml_path.open() as f:
                litellm_data = yaml.safe_load(f) or {}

                # Extract ccproxy_settings if present
                if "ccproxy_settings" in litellm_data:
                    ccproxy_settings = litellm_data["ccproxy_settings"]
                    config_data.update(ccproxy_settings)

                # Store the full LiteLLM config for reference
                config_data["_litellm_config"] = LiteLLMConfig(**litellm_data)

        # Apply any kwargs overrides
        config_data.update(kwargs)
        config_data["litellm_config_path"] = yaml_path

        # Create config instance (env vars will be auto-loaded by pydantic-settings)
        return cls(**config_data)

    def get_litellm_config(self) -> LiteLLMConfig:
        """Get the full LiteLLM configuration."""
        if self._litellm_config is None:
            # Reload from file if not cached
            with self.litellm_config_path.open() as f:
                litellm_data = yaml.safe_load(f) or {}
                self._litellm_config = LiteLLMConfig(**litellm_data)
        return self._litellm_config

    def get_model_for_label(self, label: str) -> str | None:
        """Get the model name for a given routing label from LiteLLM config."""
        litellm_config = self.get_litellm_config()

        # Look for model with matching model_name
        for model in litellm_config.model_list:
            if model.get("model_name") == label:
                # Return the actual model identifier from litellm_params
                litellm_params = model.get("litellm_params", {})
                model_name = litellm_params.get("model")
                return model_name if isinstance(model_name, str) else None

        return None


# Singleton instance holder with thread safety
_config_instance: CCProxyConfig | None = None
_config_lock = threading.Lock()


def get_config() -> CCProxyConfig:
    """Get the singleton configuration instance (thread-safe)."""
    global _config_instance

    if _config_instance is None:
        with _config_lock:
            # Double-check locking pattern
            if _config_instance is None:
                config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
                _config_instance = CCProxyConfig.from_litellm_config(config_path)

    return _config_instance


def reload_config() -> CCProxyConfig:
    """Reload configuration from disk (thread-safe)."""
    global _config_instance

    with _config_lock:
        config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
        _config_instance = CCProxyConfig.from_litellm_config(config_path)

    return _config_instance


def set_config_instance(config: CCProxyConfig) -> None:
    """Set the global configuration instance (for testing)."""
    global _config_instance
    with _config_lock:
        _config_instance = config


def clear_config_instance() -> None:
    """Clear the global configuration instance (for testing)."""
    global _config_instance
    with _config_lock:
        _config_instance = None

    # Also clear the router instance to ensure clean state
    from ccproxy.router import clear_router

    clear_router()


class ConfigProvider:
    """Dependency injection provider for configuration.

    This provides an alternative to the singleton pattern, allowing
    for easier testing and multiple configuration instances.
    """

    def __init__(self, config: CCProxyConfig | None = None) -> None:
        """Initialize the config provider.

        Args:
            config: Optional initial configuration. If not provided,
                   will load from environment on first access.
        """
        self._config = config
        self._lock = threading.Lock()

    def get(self) -> CCProxyConfig:
        """Get the configuration instance."""
        if self._config is None:
            with self._lock:
                if self._config is None:
                    # Use the global singleton if no config was provided
                    self._config = get_config()
        return self._config

    def reload(self) -> CCProxyConfig:
        """Reload configuration from disk."""
        with self._lock:
            config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
            self._config = CCProxyConfig.from_litellm_config(config_path)
        return self._config

    def set(self, config: CCProxyConfig) -> None:
        """Set the configuration instance."""
        with self._lock:
            self._config = config
