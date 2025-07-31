"""Model routing component for mapping classification labels to models."""

import threading
from typing import Any

from ccproxy.classifier import RoutingLabel
from ccproxy.config import ConfigProvider


class ModelRouter:
    """Routes classification labels to model configurations.

    This component maps classification labels (e.g., 'default', 'background', 'think')
    to specific model configurations defined in the LiteLLM proxy YAML config.

    The router is designed to be used by LiteLLM hooks through the public API:

    ```python
    # Inside a LiteLLM CustomLogger hook:
    from litellm.proxy.proxy_server import llm_router

    # Get all available models
    models = llm_router.get_model_list()

    # Access via property
    models = llm_router.model_list

    # Get model groups
    groups = llm_router.model_group_alias

    # Get available models (names only)
    available = llm_router.get_available_models()
    ```

    Thread Safety:
        All public methods are thread-safe for concurrent read access.
        Configuration updates are performed atomically.
    """

    def __init__(self, config_provider: ConfigProvider | None = None) -> None:
        """Initialize the model router.

        Args:
            config_provider: Optional config provider. If None, uses global config.
        """
        self._config_provider = config_provider or ConfigProvider()
        self._lock = threading.RLock()
        self._model_map: dict[str, dict[str, Any]] = {}
        self._model_list: list[dict[str, Any]] = []
        self._model_group_alias: dict[str, list[str]] = {}
        self._available_models: set[str] = set()

        # Load initial configuration
        self._load_model_mapping()

    def _load_model_mapping(self) -> None:
        """Load and parse model mapping from configuration.

        This method extracts model routing information from the LiteLLM
        proxy configuration and builds internal lookup structures.
        """
        config = self._config_provider.get()

        with self._lock:
            # Clear existing mappings
            self._model_map.clear()
            self._model_list.clear()
            self._model_group_alias.clear()
            self._available_models.clear()

            # Get model list from LiteLLM config
            litellm_config = config.get_litellm_config()
            model_list = litellm_config.model_list

            # Build model mapping and list
            for model_entry in model_list:
                model_name = model_entry.get("model_name")
                if not model_name:
                    continue

                # Add to model list (preserving all fields)
                self._model_list.append(model_entry.copy())

                # Add to available models set
                self._available_models.add(model_name)

                # Map routing labels to models
                if model_name in ["default", "background", "think", "token_count", "web_search"]:
                    self._model_map[model_name] = model_entry.copy()

                # Build model group aliases (models with same underlying model)
                litellm_params = model_entry.get("litellm_params", {})
                if isinstance(litellm_params, dict):
                    underlying_model = litellm_params.get("model")
                    if underlying_model:
                        if underlying_model not in self._model_group_alias:
                            self._model_group_alias[underlying_model] = []
                        self._model_group_alias[underlying_model].append(model_name)

    def get_model_for_label(self, label: RoutingLabel | str) -> dict[str, Any] | None:
        """Get model configuration for a given classification label.

        Args:
            label: The routing label to map to a model

        Returns:
            Model configuration dict with keys:
                - model_name: The model alias name
                - litellm_params: Parameters for litellm.completion()
                - model_info: Optional metadata (if present)
            Returns None if no model is mapped to the label.

        Example:
            >>> router = ModelRouter()
            >>> model = router.get_model_for_label(RoutingLabel.BACKGROUND)
            >>> print(model["model_name"])  # "background"
            >>> print(model["litellm_params"]["model"])  # "claude-3-5-haiku-20241022"
        """
        # Convert enum to string if needed
        label_str = str(label) if isinstance(label, RoutingLabel) else label

        with self._lock:
            # Try to get the direct mapping first
            model = self._model_map.get(label_str)
            if model is not None:
                return model

            # Fallback logic: try to find an alternative model
            return self._get_fallback_model(label_str)

    def get_model_list(self) -> list[dict[str, Any]]:
        """Get the complete list of available models.

        Returns:
            List of model configuration dicts, each containing:
                - model_name: The model alias name
                - litellm_params: Parameters for litellm.completion()
                - model_info: Optional metadata (if present)

        This method is designed for use by LiteLLM hooks to access
        the full model configuration.
        """
        with self._lock:
            return self._model_list.copy()

    @property
    def model_list(self) -> list[dict[str, Any]]:
        """Property access to model list for LiteLLM compatibility.

        Returns:
            List of model configuration dicts
        """
        return self.get_model_list()

    @property
    def model_group_alias(self) -> dict[str, list[str]]:
        """Get model group aliases.

        Returns:
            Dict mapping underlying model names to lists of aliases.
            For example:
            {
                "claude-3-5-sonnet-20241022": ["default", "think", "token_count"],
                "claude-3-5-haiku-20241022": ["background"]
            }
        """
        with self._lock:
            return self._model_group_alias.copy()

    def get_available_models(self) -> list[str]:
        """Get list of available model names.

        Returns:
            List of model alias names (e.g., ["default", "background", "think"])
        """
        with self._lock:
            return sorted(self._available_models)

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available in the configuration.

        Args:
            model_name: The model alias name to check

        Returns:
            True if the model is available, False otherwise
        """
        with self._lock:
            return model_name in self._available_models

    def _get_fallback_model(self, label: str) -> dict[str, Any] | None:
        """Get a fallback model when the preferred model is unavailable.

        This method implements a fallback strategy:
        1. If label is unknown, try 'default' model
        2. If 'default' is unavailable, use first available model
        3. Return None only if no models are available

        Args:
            label: The routing label that was not found

        Returns:
            A fallback model configuration or None
        """
        # Define fallback priority order
        fallback_order = ["default", "background", "think", "token_count", "web_search"]

        # Try fallback models in order
        for fallback_label in fallback_order:
            if fallback_label != label and fallback_label in self._model_map:
                return self._model_map[fallback_label]

        # If no predefined fallback found, use the first available model
        if self._model_list:
            return self._model_list[0].copy()

        # No models available at all
        return None


# Global singleton instance for LiteLLM hook access
_router_instance: ModelRouter | None = None
_router_lock = threading.Lock()


def get_router() -> ModelRouter:
    """Get the global ModelRouter instance.

    Returns:
        The singleton ModelRouter instance
    """
    global _router_instance

    if _router_instance is None:
        with _router_lock:
            if _router_instance is None:
                _router_instance = ModelRouter()

    return _router_instance


def clear_router() -> None:
    """Clear the global router instance.

    This function is used in testing to ensure clean state
    between test runs.
    """
    global _router_instance
    with _router_lock:
        _router_instance = None
