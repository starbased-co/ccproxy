"""Configuration management for ccproxy."""

import threading
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]

import litellm

# Import proxy_server to access runtime configuration
try:
    from litellm.proxy import proxy_server
except ImportError:
    # Handle case where proxy_server is not available (e.g., during testing)
    proxy_server = None  # type: ignore[assignment]


class CCProxySettings(BaseModel):
    """CCProxy-specific settings from LiteLLM config."""

    token_count_threshold: int = Field(default=60000, ge=1000, description="Token threshold for token_count")
    debug: bool = Field(default=False, description="Enable debug logging")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")




class CCProxyConfig(BaseSettings):  # type: ignore[misc]
    """Main configuration for ccproxy that reads from LiteLLM proxy runtime config."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Core settings from ccproxy_settings section or general_settings
    token_count_threshold: int = Field(default=60000, ge=1000)
    debug: bool = False
    metrics_enabled: bool = True

    # Path to LiteLLM config (kept for backward compatibility)
    litellm_config_path: Path = Field(default_factory=lambda: Path("./config.yaml"))

    @classmethod
    def from_proxy_runtime(cls, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from LiteLLM proxy server runtime.
        
        This method reads configuration directly from the proxy_server global
        variables, which are already loaded from the config.yaml by LiteLLM.
        """
        # Create instance with defaults
        instance = cls(**kwargs)
        
        # If proxy_server is available, read settings from it
        if proxy_server and hasattr(proxy_server, 'general_settings'):
            general_settings = proxy_server.general_settings or {}
            
            # Check for ccproxy_settings in general_settings
            if "ccproxy_settings" in general_settings:
                ccproxy_settings = general_settings["ccproxy_settings"]
                if isinstance(ccproxy_settings, dict):
                    # Apply settings
                    for key, value in ccproxy_settings.items():
                        if hasattr(instance, key):
                            setattr(instance, key, value)
        
        return instance

    @classmethod
    def from_litellm_config(cls, yaml_path: Path, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from LiteLLM proxy YAML file.
        
        DEPRECATED: Use from_proxy_runtime() when running as a hook.
        This method is kept for backward compatibility and testing.
        """
        # Always read from YAML file in this method
        # (from_proxy_runtime should be used explicitly for runtime config)
        instance = cls(litellm_config_path=yaml_path, **kwargs)

        # Load YAML if it exists
        if yaml_path.exists():
            with yaml_path.open() as f:
                litellm_data = yaml.safe_load(f) or {}

                # Check general_settings for ccproxy_settings
                general_settings = litellm_data.get("general_settings", {})
                if "ccproxy_settings" in general_settings:
                    ccproxy_settings = general_settings["ccproxy_settings"]
                    
                    # Apply all settings from YAML
                    for key, value in ccproxy_settings.items():
                        if hasattr(instance, key):
                            setattr(instance, key, value)

        return instance

    def get_model_for_label(self, label: str) -> str | None:
        """Get the model name for a given routing label from LiteLLM runtime config."""
        # Try to get from proxy_server runtime first
        if proxy_server and hasattr(proxy_server, 'llm_router') and proxy_server.llm_router:
            model_list = proxy_server.llm_router.model_list or []
            
            # Look for model with matching model_name
            for model in model_list:
                if model.get("model_name") == label:
                    # Return the actual model identifier from litellm_params
                    litellm_params = model.get("litellm_params", {})
                    model_name = litellm_params.get("model")
                    return model_name if isinstance(model_name, str) else None
        
        # Fall back to reading from YAML if proxy_server not available
        if self.litellm_config_path.exists():
            with self.litellm_config_path.open() as f:
                litellm_data = yaml.safe_load(f) or {}
                model_list = litellm_data.get("model_list", [])
                
                for model in model_list:
                    if model.get("model_name") == label:
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
                # Use runtime config when available (in hook context)
                if proxy_server and hasattr(proxy_server, 'general_settings'):
                    _config_instance = CCProxyConfig.from_proxy_runtime()
                else:
                    # Fall back to YAML for testing or standalone usage
                    config_path = Path("./config.yaml")
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

    def set(self, config: CCProxyConfig) -> None:
        """Set the configuration instance."""
        with self._lock:
            self._config = config
