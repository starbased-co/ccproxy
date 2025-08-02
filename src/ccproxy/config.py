"""Configuration management for ccproxy.

Configuration Discovery Precedence (Highest to Lowest Priority):
===============================================================

1. **CCPROXY_CONFIG_DIR Environment Variable** (Highest Priority)
   - Set by CLI or manually: `export CCPROXY_CONFIG_DIR=/path/to/config`
   - Looks for: `${CCPROXY_CONFIG_DIR}/ccproxy.yaml`
   - Use case: Development, testing, custom deployments

2. **LiteLLM Proxy Server Runtime Directory**
   - Automatically detected from proxy_server.config_path
   - Looks for: `{proxy_runtime_dir}/ccproxy.yaml`
   - Use case: Production deployments with LiteLLM proxy

3. **~/.ccproxy Directory** (Fallback)
   - User's home directory default location
   - Looks for: `~/.ccproxy/ccproxy.yaml`
   - Use case: Default user installations

The first existing `ccproxy.yaml` found in this order is used.
If no `ccproxy.yaml` is found, default configuration is applied.

Examples:
--------
# Override with environment variable (highest priority)
export CCPROXY_CONFIG_DIR=/custom/path
litellm --config /custom/path/config.yaml

# Use proxy runtime directory (automatic detection)
litellm --config /etc/litellm/config.yaml
# Will look for /etc/litellm/ccproxy.yaml

# Fallback to user directory
# Will look for ~/.ccproxy/ccproxy.yaml
"""

import importlib
import logging
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

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
                # Configuration discovery precedence:
                # 1. CCPROXY_CONFIG_DIR environment variable (highest priority)
                # 2. LiteLLM proxy server runtime directory
                # 3. ~/.ccproxy directory (fallback)

                import os

                config_path = None
                config_source = None

                # Priority 1: Environment variable
                env_config_dir = os.environ.get("CCPROXY_CONFIG_DIR")
                if env_config_dir:
                    config_path = Path(env_config_dir)
                    config_source = f"ENV:CCPROXY_CONFIG_DIR={env_config_dir}"
                    logger.info(f"Using config directory from environment: {config_path}")
                else:
                    # Priority 2: LiteLLM proxy server runtime directory
                    try:
                        from litellm.proxy import proxy_server

                        if proxy_server and hasattr(proxy_server, "config_path") and proxy_server.config_path:
                            config_path = Path(proxy_server.config_path).parent
                            config_source = f"PROXY_RUNTIME:{config_path}"
                            logger.info(f"Using config directory from proxy runtime: {config_path}")
                    except ImportError:
                        logger.debug("LiteLLM proxy server not available for config discovery")

                if config_path:
                    # Try to load ccproxy.yaml from discovered path
                    ccproxy_yaml_path = config_path / "ccproxy.yaml"
                    if ccproxy_yaml_path.exists():
                        logger.info(f"Loading ccproxy config from: {ccproxy_yaml_path} (source: {config_source})")
                        _config_instance = CCProxyConfig.from_yaml(ccproxy_yaml_path)
                        _config_instance.litellm_config_path = config_path / "config.yaml"
                    else:
                        logger.info(
                            f"ccproxy.yaml not found at {ccproxy_yaml_path}, using default config "
                            f"(source: {config_source})"
                        )
                        # Create default config with proper paths
                        _config_instance = CCProxyConfig(
                            litellm_config_path=config_path / "config.yaml", ccproxy_config_path=ccproxy_yaml_path
                        )
                else:
                    # Priority 3: Fallback to ~/.ccproxy directory
                    fallback_config_dir = Path.home() / ".ccproxy"
                    ccproxy_path = fallback_config_dir / "ccproxy.yaml"
                    if ccproxy_path.exists():
                        logger.info(f"Using fallback config directory: {fallback_config_dir}")
                        _config_instance = CCProxyConfig.from_yaml(ccproxy_path)
                        _config_instance.litellm_config_path = fallback_config_dir / "config.yaml"
                    else:
                        logger.info("No ccproxy.yaml found in any location, using proxy runtime defaults")
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
