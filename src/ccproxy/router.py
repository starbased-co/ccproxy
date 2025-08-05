"""Model routing component for mapping classification labels to models."""

import threading
from typing import Any


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

    def __init__(self) -> None:
        """Initialize the model router."""
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
        with self._lock:
            # Clear existing mappings
            self._model_map.clear()
            self._model_list.clear()
            self._model_group_alias.clear()
            self._available_models.clear()

            # Get model list from proxy server
            from litellm.proxy import proxy_server

            if proxy_server and hasattr(proxy_server, "llm_router") and proxy_server.llm_router:
                model_list = proxy_server.llm_router.model_list or []
            else:
                model_list = []

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
                # All model names can be used as routing labels
                self._model_map[model_name] = model_entry.copy()

                # Build model group aliases (models with same underlying model)
                litellm_params = model_entry.get("litellm_params", {})
                if isinstance(litellm_params, dict):
                    underlying_model = litellm_params.get("model")
                    if underlying_model:
                        if underlying_model not in self._model_group_alias:
                            self._model_group_alias[underlying_model] = []
                        self._model_group_alias[underlying_model].append(model_name)

    def get_model_for_label(self, model_name: str) -> dict[str, Any] | None:
        """Get model configuration for a given classification model_name.

        Args:
            model_name: The model_name to map to a model

        Returns:
            Model configuration dict with keys:
                - model_name: The model alias name
                - litellm_params: Parameters for litellm.completion()
                - model_info: Optional metadata (if present)
            Returns None if no model is mapped to the model_name.

        Example:
            >>> router = ModelRouter()
            >>> model = router.get_model_for_label("background")
            >>> print(model["model_name"])  # "background"
            >>> print(model["litellm_params"]["model"])  # "claude-3-5-haiku-20241022"
        """
        model_name_str = model_name

        with self._lock:
            # Try to get the direct mapping first
            model = self._model_map.get(model_name_str)
            if model is not None:
                return model

            # Fallback to 'default' model if model_name not found
            return self._model_map.get("default")

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


# Global router instance
_router_instance: ModelRouter | None = None


def get_router() -> ModelRouter:
    """Get the global ModelRouter instance.

    Returns:
        The global ModelRouter instance
    """
    global _router_instance

    if _router_instance is None:
        _router_instance = ModelRouter()

    return _router_instance


def clear_router() -> None:
    """Clear the global router instance.

    This function is used in testing to ensure clean state
    between test runs.
    """
    global _router_instance
    _router_instance = None
