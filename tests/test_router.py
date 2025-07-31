"""Tests for the ModelRouter component."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from ccproxy.config import CCProxyConfig, ConfigProvider
from ccproxy.router import ModelRouter, get_router


class TestModelRouter:
    """Test suite for ModelRouter."""

    def test_init_loads_config(self) -> None:
        """Test that initialization loads model mapping from config."""
        # Create temporary YAML file with model config
        test_yaml_content = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {"model": "claude-3-5-sonnet-20241022", "api_base": "https://api.anthropic.com"},
                },
                {
                    "model_name": "background",
                    "litellm_params": {"model": "claude-3-5-haiku-20241022", "api_base": "https://api.anthropic.com"},
                    "model_info": {"priority": "low"},
                },
            ]
        }

        # Create mock config
        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        # Mock open to return our test YAML
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Verify config was loaded
        assert mock_provider.get.called

        # Check model mapping
        model = router.get_model_for_label("default")
        assert model is not None
        assert model["model_name"] == "default"
        assert model["litellm_params"]["model"] == "claude-3-5-sonnet-20241022"

        # Check model with metadata
        model = router.get_model_for_label("background")
        assert model is not None
        assert model["model_info"]["priority"] == "low"

    def test_get_model_for_label_with_string(self) -> None:
        """Test get_model_for_label with string labels."""
        test_yaml_content = {
            "model_list": [{"model_name": "think", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}}]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Test with string
        model = router.get_model_for_label("think")
        assert model is not None
        assert model["model_name"] == "think"

    def test_get_model_for_unknown_label(self) -> None:
        """Test get_model_for_label returns None for unknown labels."""
        test_yaml_content = {"model_list": []}

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        assert router.get_model_for_label("unknown") is None
        assert router.get_model_for_label("default") is None

    def test_get_model_list(self) -> None:
        """Test get_model_list returns all models."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}},
                {"model_name": "custom-model", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku-20241022"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        models = router.get_model_list()
        assert len(models) == 3
        assert models[0]["model_name"] == "default"
        assert models[1]["model_name"] == "custom-model"
        assert models[2]["model_name"] == "background"

    def test_model_list_property(self) -> None:
        """Test model_list property access."""
        test_yaml_content = {"model_list": [{"model_name": "default", "litellm_params": {"model": "claude"}}]}

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Property should return same as method
        assert router.model_list == router.get_model_list()

    def test_model_group_alias(self) -> None:
        """Test model_group_alias groups models by underlying model."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}},
                {"model_name": "think", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}},
                {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku-20241022"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        groups = router.model_group_alias
        assert "claude-3-5-sonnet-20241022" in groups
        assert set(groups["claude-3-5-sonnet-20241022"]) == {"default", "think"}
        assert groups["claude-3-5-haiku-20241022"] == ["background"]

    def test_get_available_models(self) -> None:
        """Test get_available_models returns sorted model names."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "think", "litellm_params": {"model": "claude"}},
                {"model_name": "background", "litellm_params": {"model": "claude"}},
                {"model_name": "default", "litellm_params": {"model": "claude"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        available = router.get_available_models()
        assert available == ["background", "default", "think"]  # Sorted

    def test_malformed_config_handling(self) -> None:
        """Test handling of malformed configurations."""
        # Test with missing model_name entries
        test_yaml_content = {
            "model_list": [
                {"no_model_name": "test"},
                {"model_name": "valid", "litellm_params": {"model": "claude"}},
                {"model_name": "", "litellm_params": {"model": "claude"}},  # Empty name
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        models = router.get_model_list()
        assert len(models) == 1
        assert models[0]["model_name"] == "valid"

    def test_missing_litellm_params(self) -> None:
        """Test handling of models without litellm_params."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default"},  # No litellm_params
                {"model_name": "background", "litellm_params": None},  # None params
                {"model_name": "think", "litellm_params": {"model": "claude"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # All models should be in list
        assert len(router.get_model_list()) == 3

        # Only model with valid params should be in groups
        groups = router.model_group_alias
        assert "claude" in groups
        assert groups["claude"] == ["think"]

    def test_config_update(self) -> None:
        """Test configuration update handling."""
        initial_yaml_content = {"model_list": [{"model_name": "default", "litellm_params": {"model": "claude"}}]}

        updated_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "background", "litellm_params": {"model": "claude"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        # Start with initial config
        yaml_content = initial_yaml_content

        def mock_yaml_load(*args, **kwargs):
            return yaml_content

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(initial_yaml_content)
            with patch("yaml.safe_load", side_effect=mock_yaml_load):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

                # Initial state
                assert len(router.get_model_list()) == 1
                assert router.get_model_for_label("default")["litellm_params"]["model"] == "claude"

                # Simulate config update
                yaml_content = updated_yaml_content
                mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(updated_yaml_content)
                router._load_model_mapping()  # Manually trigger mapping update

                # Check updated state
                assert len(router.get_model_list()) == 2
                assert router.get_model_for_label("default")["litellm_params"]["model"] == "gpt-4"
                assert router.get_model_for_label("background") is not None

    def test_thread_safety(self) -> None:
        """Test thread-safe access to router methods."""
        test_yaml_content = {
            "model_list": [{"model_name": f"model-{i}", "litellm_params": {"model": "claude"}} for i in range(10)]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        results = []
        errors = []

        def access_router():
            try:
                # Perform multiple operations
                router.get_model_list()
                router.get_available_models()
                _ = router.model_group_alias
                router.get_model_for_label("model-5")
                results.append("success")
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=access_router) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0
        assert len(results) == 10

    @patch("ccproxy.router.ConfigProvider")
    def test_get_router_singleton(self, mock_config_provider_class: MagicMock) -> None:
        """Test get_router returns singleton instance."""
        # Mock config provider
        mock_provider = MagicMock()
        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = False
        mock_provider.get.return_value = mock_config
        mock_config_provider_class.return_value = mock_provider

        # Reset global instance for test
        import ccproxy.router

        ccproxy.router._router_instance = None

        router1 = get_router()
        router2 = get_router()

        assert router1 is router2

        # Test thread-safe singleton creation
        routers = []

        def get_router_instance():
            routers.append(get_router())

        threads = [threading.Thread(target=get_router_instance) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be same instance
        assert all(r is routers[0] for r in routers)

    def test_fallback_to_default_model(self) -> None:
        """Test fallback to default model when requested label is unavailable."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet-20241022"}},
                {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku-20241022"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Request unavailable model, should fallback to default
        model = router.get_model_for_label("think")
        assert model is not None
        assert model["model_name"] == "default"

    def test_fallback_priority_order(self) -> None:
        """Test fallback follows priority order when default is unavailable."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku-20241022"}},
                {"model_name": "token_count", "litellm_params": {"model": "gpt-4"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Request unavailable model, should fallback to first (background)
        model = router.get_model_for_label("think")
        assert model is not None
        assert model["model_name"] == "background"

    def test_fallback_to_first_available(self) -> None:
        """Test fallback to first available model when no priority models exist."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "custom-model-1", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "custom-model-2", "litellm_params": {"model": "claude"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Request unavailable model with no standard fallbacks
        model = router.get_model_for_label("think")
        assert model is not None
        assert model["model_name"] == "custom-model-1"  # First in list

    def test_no_fallback_when_empty_config(self) -> None:
        """Test returns None when no models are available."""
        test_yaml_content = {"model_list": []}

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Should return None when no models available
        assert router.get_model_for_label("think") is None
        assert router.get_model_for_label("default") is None

    def test_is_model_available(self) -> None:
        """Test is_model_available method."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "claude"}},
                {"model_name": "background", "litellm_params": {"model": "haiku"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            with patch("yaml.safe_load", return_value=test_yaml_content):
                mock_provider = MagicMock(spec=ConfigProvider)
                mock_provider.get.return_value = mock_config

                router = ModelRouter(config_provider=mock_provider)

        # Test available models
        assert router.is_model_available("default") is True
        assert router.is_model_available("background") is True

        # Test unavailable models
        assert router.is_model_available("think") is False
        assert router.is_model_available("unknown") is False
        assert router.is_model_available("") is False
