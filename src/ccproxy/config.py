"""Configuration management for ccproxy."""

import importlib
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import proxy_server to access runtime configuration
try:
    from litellm.proxy import proxy_server
except ImportError:
    # Handle case where proxy_server is not available (e.g., during testing)
    proxy_server = None


class RuleConfig:
    """Configuration for a single classification rule."""

    def __init__(self, label: str, rule_path: str, params: list[Any] | None = None) -> None:
        """Initialize a rule configuration.

        Args:
            label: The routing label for this rule
            rule_path: Python import path to the rule class
            params: Optional parameters to pass to the rule constructor
        """
        self.label = label
        self.rule_path = rule_path
        self.params = params or []

    def create_instance(self) -> Any:
        """Create an instance of the rule class.

        Returns:
            An instance of the ClassificationRule

        Raises:
            ImportError: If the rule class cannot be imported
            TypeError: If the rule class cannot be instantiated with provided params
        """
        # Import the rule class
        module_path, class_name = self.rule_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        rule_class = getattr(module, class_name)

        # Create instance with parameters
        if not self.params:
            # No parameters
            return rule_class()

        if isinstance(self.params, list):
            # If all params are dicts, assume they're kwargs
            if all(isinstance(p, dict) for p in self.params):
                # Merge all dicts into one kwargs dict
                kwargs = {}
                for p in self.params:
                    kwargs.update(p)
                return rule_class(**kwargs)
            # Otherwise treat as positional args
            return rule_class(*self.params)
        if isinstance(self.params, dict):  # type: ignore[unreachable]
            # Single dict of kwargs
            return rule_class(**self.params)
        # Single positional arg
        return rule_class(self.params)


class CCProxyConfig(BaseSettings):
    """Main configuration for ccproxy that reads from ccproxy.yaml."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Core settings
    debug: bool = False
    metrics_enabled: bool = True

    # Rule configurations
    rules: list[RuleConfig] = Field(default_factory=list)

    # Path to ccproxy config
    ccproxy_config_path: Path = Field(default_factory=lambda: Path("./ccproxy.yaml"))

    # Path to LiteLLM config (for model lookups)
    litellm_config_path: Path = Field(default_factory=lambda: Path("./config.yaml"))

    @classmethod
    def from_proxy_runtime(cls, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from ccproxy.yaml file in the same directory as config.yaml.

        This method looks for ccproxy.yaml in the same directory as the LiteLLM config.
        """
        # Create instance with defaults
        instance = cls(**kwargs)

        # Try to find ccproxy.yaml in the same directory as config.yaml
        config_dir = instance.litellm_config_path.parent
        ccproxy_yaml_path = config_dir / "ccproxy.yaml"

        if ccproxy_yaml_path.exists():
            instance = cls.from_yaml(ccproxy_yaml_path, **kwargs)

        return instance

    @classmethod
    def from_yaml(cls, yaml_path: Path, **kwargs: Any) -> "CCProxyConfig":
        """Load configuration from ccproxy.yaml file.

        Args:
            yaml_path: Path to the ccproxy.yaml file
            **kwargs: Additional keyword arguments

        Returns:
            CCProxyConfig instance
        """
        instance = cls(ccproxy_config_path=yaml_path, **kwargs)

        # Load YAML if it exists
        if yaml_path.exists():
            with yaml_path.open() as f:
                data = yaml.safe_load(f) or {}

                # Get ccproxy section
                ccproxy_data = data.get("ccproxy", {})

                # Apply basic settings
                if "debug" in ccproxy_data:
                    instance.debug = ccproxy_data["debug"]
                if "metrics_enabled" in ccproxy_data:
                    instance.metrics_enabled = ccproxy_data["metrics_enabled"]

                # Load rules
                rules_data = ccproxy_data.get("rules", [])
                instance.rules = []
                for rule_data in rules_data:
                    if isinstance(rule_data, dict):
                        label = rule_data.get("label", "")
                        rule_path = rule_data.get("rule", "")
                        params = rule_data.get("params", [])
                        if label and rule_path:
                            rule_config = RuleConfig(label, rule_path, params)
                            instance.rules.append(rule_config)

        return instance


# Global configuration instance
_config_instance: CCProxyConfig | None = None
_config_lock = threading.Lock()


def get_config() -> CCProxyConfig:
    """Get the configuration instance."""
    global _config_instance

    if _config_instance is None:
        with _config_lock:
            # Double-check locking pattern
            if _config_instance is None:
                # Try to get config path from environment variable set by CLI
                config_path = None
                import os

                env_config_dir = os.environ.get("CCPROXY_CONFIG_DIR")

                if env_config_dir:
                    config_path = Path(env_config_dir)
                else:
                    # Try to get config path from LiteLLM proxy_server runtime
                    try:
                        from litellm.proxy import proxy_server

                        if proxy_server and hasattr(proxy_server, "config_path") and proxy_server.config_path:
                            config_path = Path(proxy_server.config_path).parent
                    except ImportError:
                        pass

                # If we found the runtime config path, look for ccproxy.yaml there
                if config_path:
                    ccproxy_yaml_path = config_path / "ccproxy.yaml"
                    if ccproxy_yaml_path.exists():
                        _config_instance = CCProxyConfig.from_yaml(ccproxy_yaml_path)
                    else:
                        # Create default config with proper paths
                        _config_instance = CCProxyConfig(
                            litellm_config_path=config_path / "config.yaml", ccproxy_config_path=ccproxy_yaml_path
                        )
                else:
                    # Fallback: Try to load from ~/.ccproxy directory
                    fallback_config_dir = Path.home() / ".ccproxy"
                    ccproxy_path = fallback_config_dir / "ccproxy.yaml"
                    if ccproxy_path.exists():
                        _config_instance = CCProxyConfig.from_yaml(ccproxy_path)
                    else:
                        # Use from_proxy_runtime which will look for ccproxy.yaml
                        # in the same directory as config.yaml
                        _config_instance = CCProxyConfig.from_proxy_runtime()

    return _config_instance


def set_config_instance(config: CCProxyConfig) -> None:
    """Set the global configuration instance (for testing)."""
    global _config_instance
    _config_instance = config


def clear_config_instance() -> None:
    """Clear the global configuration instance (for testing)."""
    global _config_instance
    _config_instance = None
