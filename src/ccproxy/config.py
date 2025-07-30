"""Configuration management for ccproxy."""

import os
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]

from ccproxy.types import LogFormat, LogLevel, ModelProvider


class ModelConfig(BaseModel):
    """Configuration for a specific model."""

    provider: ModelProvider
    model_name: str
    api_base: str | None = None
    api_version: str | None = None
    max_tokens: int | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)


class RoutingConfig(BaseModel):
    """Configuration for request routing."""

    # Model mappings for each routing label
    default: ModelConfig
    background: ModelConfig
    think: ModelConfig
    large_context: ModelConfig
    web_search: ModelConfig

    # Fallback configuration
    fallback_model: ModelConfig | None = None
    fallback_enabled: bool = True


class MetricsConfig(BaseModel):
    """Configuration for metrics collection."""

    enabled: bool = True
    port: int = Field(default=9090, ge=1024, le=65535)
    path: str = "/metrics"


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: LogLevel = "INFO"
    format: LogFormat = "json"
    file_path: Path | None = None
    max_file_size: int = Field(default=10_485_760, ge=1_048_576)  # 10MB default, min 1MB
    backup_count: int = Field(default=5, ge=0, le=100)


class SecurityConfig(BaseModel):
    """Configuration for security settings."""

    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = Field(default=60, ge=1)
    enable_https_only: bool = True
    verify_ssl: bool = True
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])


class CCProxyConfig(BaseSettings):  # type: ignore[misc]
    """Main configuration for ccproxy."""

    model_config = SettingsConfigDict(
        env_prefix="CCPROXY_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core settings
    context_threshold: int = Field(default=60000, ge=1000)
    config_path: Path = Field(default=Path("./config.yaml"))

    # Sub-configurations
    routing: RoutingConfig | None = None
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Development settings
    debug: bool = False
    reload_config_on_change: bool = False

    @classmethod
    def from_yaml(cls, yaml_path: Path, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from YAML file with environment overrides."""
        config_data: dict[str, Any] = {}

        # Load YAML if it exists
        if yaml_path.exists():
            with yaml_path.open() as f:
                yaml_data = yaml.safe_load(f) or {}
                config_data.update(yaml_data)

        # Apply any kwargs overrides
        config_data.update(kwargs)

        # Create config instance (env vars will be auto-loaded by pydantic-settings)
        return cls(**config_data)

    def to_yaml(self, yaml_path: Path) -> None:
        """Save current configuration to YAML file."""
        # Export to dict, excluding None values
        config_dict = self.model_dump(exclude_none=True, exclude={"config_path"})

        # Ensure directory exists
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # Write YAML
        with yaml_path.open("w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


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
                _config_instance = CCProxyConfig.from_yaml(config_path)

    return _config_instance


def reload_config() -> CCProxyConfig:
    """Reload configuration from disk (thread-safe)."""
    global _config_instance

    with _config_lock:
        config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
        _config_instance = CCProxyConfig.from_yaml(config_path)

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
                    config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
                    self._config = CCProxyConfig.from_yaml(config_path)
        return self._config

    def reload(self) -> CCProxyConfig:
        """Reload configuration from disk."""
        with self._lock:
            config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))
            self._config = CCProxyConfig.from_yaml(config_path)
        return self._config

    def set(self, config: CCProxyConfig) -> None:
        """Set the configuration instance."""
        with self._lock:
            self._config = config
