"""Tests for the ModelRouter component."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from ccproxy.config import CCProxyConfig
from ccproxy.router import ModelRouter, clear_router, get_router


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
        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

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

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

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

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Test unknown label returns None
        model = router.get_model_for_label("non_existent")
        assert model is None

    def test_get_model_list(self) -> None:
        """Test get_model_list returns full model configuration."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "background", "litellm_params": {"model": "gpt-3.5"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Get model list
        models = router.get_model_list()
        assert len(models) == 2
        assert models[0]["model_name"] == "default"
        assert models[1]["model_name"] == "background"

    def test_model_list_property(self) -> None:
        """Test model_list property returns same as get_model_list."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

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

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Check grouping
        groups = router.model_group_alias
        assert "claude-3-5-sonnet-20241022" in groups
        assert set(groups["claude-3-5-sonnet-20241022"]) == {"default", "think"}
        assert groups["claude-3-5-haiku-20241022"] == ["background"]

    def test_get_available_models(self) -> None:
        """Test get_available_models returns sorted model names."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "zebra", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "alpha", "litellm_params": {"model": "gpt-3.5"}},
                {"model_name": "beta", "litellm_params": {"model": "gpt-3.5"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Should be sorted
        models = router.get_available_models()
        assert models == ["alpha", "beta", "zebra"]

    def test_malformed_config_handling(self) -> None:
        """Test handling of malformed model configurations."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "valid", "litellm_params": {"model": "gpt-4"}},
                {"litellm_params": {"model": "gpt-3.5"}},  # Missing model_name
                {"model_name": "no_params"},  # Missing litellm_params
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Both models with model_name should be loaded (even without litellm_params)
        models = router.get_available_models()
        assert models == ["no_params", "valid"]  # Sorted alphabetically

    def test_missing_litellm_params(self) -> None:
        """Test models without litellm_params are handled."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "incomplete"},  # No litellm_params
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Model should still be available but group alias will be empty
        assert "incomplete" in router.get_available_models()
        # No underlying model, so no group alias
        assert "incomplete" not in router.model_group_alias

    def test_config_update(self) -> None:
        """Test reloading configuration updates model mapping."""
        initial_yaml = {"model_list": [{"model_name": "default", "litellm_params": {"model": "gpt-4"}}]}

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=initial_yaml),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(initial_yaml)
            router = ModelRouter()

        # Initial state
        assert router.get_available_models() == ["default"]

        # Update config
        updated_yaml = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "new_model", "litellm_params": {"model": "gpt-3.5"}},
            ]
        }

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=updated_yaml),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(updated_yaml)
            router._load_model_mapping()

        # Should have new model
        assert set(router.get_available_models()) == {"default", "new_model"}

    def test_thread_safety(self) -> None:
        """Test concurrent access to router is thread-safe."""
        test_yaml_content = {
            "model_list": [{"model_name": f"model_{i}", "litellm_params": {"model": f"gpt-{i}"}} for i in range(10)]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        results = []
        threads = []

        def access_router():
            # Multiple operations
            models = router.get_model_list()
            available = router.get_available_models()
            model = router.get_model_for_label("model_5")
            results.append((len(models), len(available), model is not None))

        # Create multiple threads
        for _ in range(20):
            t = threading.Thread(target=access_router)
            threads.append(t)
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # All results should be consistent
        assert all(r == (10, 10, True) for r in results)

    def test_get_router_singleton(self) -> None:
        """Test get_router returns singleton instance."""
        # Clear any existing instance
        clear_router()

        # Mock the get_config to avoid file system access
        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = False

        with patch("ccproxy.router.get_config", return_value=mock_config):
            router1 = get_router()
            router2 = get_router()

        assert router1 is router2

        # Clean up
        clear_router()

    def test_fallback_to_default_model(self) -> None:
        """Test fallback to 'default' model when label not found."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "other", "litellm_params": {"model": "gpt-3.5"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Unknown label should return default
        model = router.get_model_for_label("unknown")
        assert model is not None
        assert model["model_name"] == "default"
        assert model["litellm_params"]["model"] == "gpt-4"

    def test_fallback_priority_order(self) -> None:
        """Test fallback priority: requested -> default -> first available."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "first", "litellm_params": {"model": "gpt-3.5"}},
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "other", "litellm_params": {"model": "claude"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # Should get exact match
        model = router.get_model_for_label("other")
        assert model["model_name"] == "other"

        # Should fallback to default
        model = router.get_model_for_label("unknown")
        assert model["model_name"] == "default"

    def test_fallback_to_first_available(self) -> None:
        """Test fallback to first model when no default exists."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "alpha", "litellm_params": {"model": "gpt-3.5"}},
                {"model_name": "beta", "litellm_params": {"model": "gpt-4"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # No default, should use first model
        model = router.get_model_for_label("unknown")
        assert model is not None
        assert model["model_name"] == "alpha"

    def test_no_fallback_when_empty_config(self) -> None:
        """Test returns None when no models configured."""
        test_yaml_content = {"model_list": []}

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        # No models, should return None
        model = router.get_model_for_label("any")
        assert model is None

    def test_is_model_available(self) -> None:
        """Test is_model_available method."""
        test_yaml_content = {
            "model_list": [
                {"model_name": "available", "litellm_params": {"model": "gpt-4"}},
            ]
        }

        mock_config = MagicMock(spec=CCProxyConfig)
        mock_config.litellm_config_path = MagicMock(spec=Path)
        mock_config.litellm_config_path.exists.return_value = True

        with (
            patch("builtins.open", create=True) as mock_open,
            patch("yaml.safe_load", return_value=test_yaml_content),
            patch("ccproxy.router.get_config", return_value=mock_config),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = yaml.dump(test_yaml_content)
            router = ModelRouter()

        assert router.is_model_available("available") is True
        assert router.is_model_available("not_available") is False
