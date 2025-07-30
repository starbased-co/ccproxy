"""Integration tests for LiteLLM hook compatibility."""

from unittest.mock import MagicMock, patch

from ccproxy.config import CCProxyConfig, LiteLLMConfig


class TestLiteLLMIntegration:
    """Test suite for LiteLLM hook integration."""

    @patch("ccproxy.router.ConfigProvider")
    def test_import_llm_router(self, mock_config_provider_class: MagicMock) -> None:
        """Test importing llm_router as LiteLLM hooks would."""
        # Mock config
        mock_litellm_config = LiteLLMConfig(
            model_list=[
                {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}},
                {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku-20241022"}},
            ]
        )

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.get_litellm_config.return_value = mock_litellm_config

        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_config
        mock_config_provider_class.return_value = mock_provider

        # Reset the singleton
        import ccproxy.router

        ccproxy.router._router_instance = None

        # Import as LiteLLM hook would
        from ccproxy.llm_router import llm_router

        # Verify we can access all public APIs
        assert hasattr(llm_router, "get_model_list")
        assert hasattr(llm_router, "model_list")
        assert hasattr(llm_router, "model_group_alias")
        assert hasattr(llm_router, "get_available_models")
        assert hasattr(llm_router, "get_model_for_label")
        assert hasattr(llm_router, "is_model_available")

        # Test functionality
        models = llm_router.get_model_list()
        assert len(models) == 2
        assert models[0]["model_name"] == "default"

        # Test property access
        assert llm_router.model_list == models

        # Test model groups
        groups = llm_router.model_group_alias
        assert "claude-3-5-sonnet-20241022" in groups
        assert "claude-3-5-haiku-20241022" in groups

        # Test available models
        available = llm_router.get_available_models()
        assert set(available) == {"background", "default"}

    @patch("ccproxy.router.ConfigProvider")
    def test_litellm_hook_usage_example(self, mock_config_provider_class: MagicMock) -> None:
        """Test a realistic LiteLLM hook usage pattern."""
        # Mock config
        mock_litellm_config = LiteLLMConfig(
            model_list=[
                {
                    "model_name": "default",
                    "litellm_params": {"model": "claude-3-5-sonnet-20241022", "api_key": "sk-***"},
                    "model_info": {"priority": "high", "cost_per_token": 0.003},
                },
                {
                    "model_name": "background",
                    "litellm_params": {"model": "claude-3-5-haiku-20241022", "api_key": "sk-***"},
                    "model_info": {"priority": "low", "cost_per_token": 0.0008},
                },
                {
                    "model_name": "think",
                    "litellm_params": {"model": "claude-3-5-sonnet-20241022", "api_key": "sk-***"},
                    "model_info": {"priority": "high", "cost_per_token": 0.003},
                },
            ]
        )

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.get_litellm_config.return_value = mock_litellm_config

        mock_provider = MagicMock()
        mock_provider.get.return_value = mock_config
        mock_config_provider_class.return_value = mock_provider

        # Reset the singleton
        import ccproxy.router

        ccproxy.router._router_instance = None

        # Simulate a LiteLLM hook accessing the router
        from ccproxy.llm_router import llm_router

        # Hook decides which model to use based on request
        classification_label = "background"  # From CCProxyHandler

        # Get the model configuration
        model_config = llm_router.get_model_for_label(classification_label)
        assert model_config is not None
        assert model_config["model_name"] == "background"
        assert model_config["litellm_params"]["model"] == "claude-3-5-haiku-20241022"
        assert model_config["model_info"]["priority"] == "low"
        assert model_config["model_info"]["cost_per_token"] == 0.0008

        # Check if a specific model is available
        assert llm_router.is_model_available("background") is True
        assert llm_router.is_model_available("web_search") is False

        # Get models grouped by underlying model
        groups = llm_router.model_group_alias
        assert len(groups["claude-3-5-sonnet-20241022"]) == 2  # default and think
        assert groups["claude-3-5-sonnet-20241022"] == ["default", "think"]

    def test_package_level_import(self) -> None:
        """Test that llm_router is accessible from package level."""
        # Import from package root
        from ccproxy import llm_router

        # Should be the same as direct import
        from ccproxy.llm_router import llm_router as direct_import

        assert llm_router is direct_import
