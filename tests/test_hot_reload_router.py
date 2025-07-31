"""Integration tests for hot-reload of ModelRouter configuration."""

import asyncio
import tempfile
import time
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from ccproxy.config import CCProxyConfig, ConfigProvider
from ccproxy.router import ModelRouter, reload_router
from ccproxy.watcher import ConfigWatcher


class TestHotReloadRouter:
    """Test suite for hot-reload functionality of ModelRouter."""

    def test_router_reload_method(self) -> None:
        """Test that router.reload() updates model mappings."""
        # Create initial config
        initial_config = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "background", "litellm_params": {"model": "gpt-3.5-turbo"}},
            ]
        }

        # Create router with initial config
        config_provider = ConfigProvider(CCProxyConfig())
        with patch.object(config_provider, "get") as mock_get:
            mock_config = MagicMock()
            mock_config.get_litellm_config.return_value = MagicMock(model_list=initial_config["model_list"])
            mock_get.return_value = mock_config

            router = ModelRouter(config_provider)

            # Verify initial state
            assert router.is_model_available("default")
            assert router.is_model_available("background")
            assert not router.is_model_available("think")

            default_model = router.get_model_for_label("default")
            assert default_model is not None
            assert default_model["litellm_params"]["model"] == "gpt-4"

            # Update config to add new models
            updated_config = {
                "model_list": [
                    {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet"}},
                    {"model_name": "background", "litellm_params": {"model": "claude-3-5-haiku"}},
                    {"model_name": "think", "litellm_params": {"model": "o1-preview"}},
                    {"model_name": "web_search", "litellm_params": {"model": "perplexity-online"}},
                ]
            }

            mock_config.get_litellm_config.return_value = MagicMock(model_list=updated_config["model_list"])

            # Reload router
            router.reload()

            # Verify updated state
            assert router.is_model_available("default")
            assert router.is_model_available("background")
            assert router.is_model_available("think")
            assert router.is_model_available("web_search")

            # Check model values changed
            default_model = router.get_model_for_label("default")
            assert default_model is not None
            assert default_model["litellm_params"]["model"] == "claude-3-5-sonnet"

            think_model = router.get_model_for_label("think")
            assert think_model is not None
            assert think_model["litellm_params"]["model"] == "o1-preview"

    def test_reload_router_global_function(self) -> None:
        """Test the global reload_router function."""
        # Mock the singleton
        import ccproxy.router

        mock_router = MagicMock(spec=ModelRouter)
        ccproxy.router._router_instance = mock_router

        # Call reload_router
        reload_router()

        # Verify reload was called
        mock_router.reload.assert_called_once()

    @pytest.mark.asyncio
    async def test_hot_reload_integration(self) -> None:
        """Test hot-reload integration with ConfigWatcher."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"

            # Write initial config
            initial_yaml = """
model_list:
  - model_name: default
    litellm_params:
      model: gpt-4
      api_key: test-key
  - model_name: background
    litellm_params:
      model: gpt-3.5-turbo
      api_key: test-key
"""
            config_path.write_text(initial_yaml)

            # Reset router singleton
            import ccproxy.router

            ccproxy.router._router_instance = None

            # Track reload calls
            reload_calls = []

            def track_reload() -> None:
                reload_calls.append(time.time())

            # Create a custom callback
            callback_calls = []

            def custom_callback() -> None:
                callback_calls.append(time.time())

            # Start watcher with callback
            watcher = ConfigWatcher(config_path, callback=custom_callback, debounce_seconds=0.1)

            # Mock the reload functions to track calls
            with (
                patch("ccproxy.watcher.reload_config") as mock_reload_config,
                patch("ccproxy.router.reload_router", side_effect=track_reload) as mock_reload_router,
            ):
                # Start event loop in thread
                loop = asyncio.new_event_loop()

                def run_loop() -> None:
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                thread = Thread(target=run_loop, daemon=True)
                thread.start()

                # Set event loop for handler
                watcher._handler = watcher._handler or MagicMock()
                watcher._handler.set_event_loop(loop)

                try:
                    # Start watching
                    watcher.start()

                    # Give watcher time to start
                    await asyncio.sleep(0.2)

                    # Update config file
                    updated_yaml = """
model_list:
  - model_name: default
    litellm_params:
      model: claude-3-5-sonnet
      api_key: test-key
  - model_name: background
    litellm_params:
      model: claude-3-5-haiku
      api_key: test-key
  - model_name: think
    litellm_params:
      model: o1-preview
      api_key: test-key
"""
                    config_path.write_text(updated_yaml)

                    # Wait for reload (debounce + processing)
                    await asyncio.sleep(0.5)

                    # Verify reload was triggered
                    assert len(reload_calls) >= 1
                    assert len(callback_calls) >= 1
                    mock_reload_config.assert_called()
                    mock_reload_router.assert_called()

                finally:
                    # Cleanup
                    watcher.stop()
                    loop.call_soon_threadsafe(loop.stop)
                    thread.join(timeout=1)

    def test_atomic_reload_thread_safety(self) -> None:
        """Test that reloads are atomic and thread-safe."""
        # Create config provider with mocked config
        initial_config = {"model_list": [{"model_name": "default", "litellm_params": {"model": "model-v0"}}]}

        config_provider = ConfigProvider(CCProxyConfig())

        # Create a shared mock config that can be updated
        mock_config = MagicMock()
        mock_config.get_litellm_config.return_value = MagicMock(model_list=initial_config["model_list"])

        with patch.object(config_provider, "get", return_value=mock_config):
            # Create router
            router = ModelRouter(config_provider)

            # Mock config changes
            configs = [
                {"model_list": [{"model_name": "default", "litellm_params": {"model": f"model-v{i}"}}]}
                for i in range(10)
            ]

            reload_count = 0
            read_results: list[str] = []

            def reload_worker() -> None:
                """Worker that performs reloads."""
                nonlocal reload_count
                for config in configs:
                    # Update the shared mock config
                    mock_config.get_litellm_config.return_value = MagicMock(model_list=config["model_list"])
                    router.reload()
                    reload_count += 1
                    time.sleep(0.001)  # Small delay to encourage race conditions

            def read_worker() -> None:
                """Worker that reads from router."""
                for _ in range(100):
                    model = router.get_model_for_label("default")
                    if model:
                        read_results.append(model["litellm_params"]["model"])
                    time.sleep(0.0001)

            # Start concurrent workers
            reload_thread = Thread(target=reload_worker)
            read_threads = [Thread(target=read_worker) for _ in range(5)]

            reload_thread.start()
            for thread in read_threads:
                thread.start()

            # Wait for completion
            reload_thread.join()
            for thread in read_threads:
                thread.join()

            # Verify results
            assert reload_count == len(configs)
            assert len(read_results) > 0

            # All reads should have valid model names
            for result in read_results:
                assert result.startswith("model-v")

    def test_reload_preserves_model_info(self) -> None:
        """Test that reload preserves model_info metadata."""
        # Create config with model_info
        config_with_info = {
            "model_list": [
                {
                    "model_name": "default",
                    "litellm_params": {"model": "gpt-4", "temperature": 0.7},
                    "model_info": {"priority": "high", "cost_per_token": 0.03, "custom_field": "value"},
                },
                {
                    "model_name": "background",
                    "litellm_params": {"model": "gpt-3.5-turbo"},
                    "model_info": {"priority": "low", "cost_per_token": 0.002},
                },
            ]
        }

        config_provider = ConfigProvider(CCProxyConfig())
        with patch.object(config_provider, "get") as mock_get:
            mock_config = MagicMock()
            mock_config.get_litellm_config.return_value = MagicMock(model_list=config_with_info["model_list"])
            mock_get.return_value = mock_config

            router = ModelRouter(config_provider)

            # Check initial state
            default_model = router.get_model_for_label("default")
            assert default_model is not None
            assert default_model["model_info"]["priority"] == "high"
            assert default_model["model_info"]["cost_per_token"] == 0.03
            assert default_model["model_info"]["custom_field"] == "value"

            # Update config
            updated_config = {
                "model_list": [
                    {
                        "model_name": "default",
                        "litellm_params": {"model": "claude-3-5-sonnet"},
                        "model_info": {"priority": "medium", "cost_per_token": 0.015, "new_field": "new_value"},
                    }
                ]
            }

            mock_config.get_litellm_config.return_value = MagicMock(model_list=updated_config["model_list"])

            # Reload
            router.reload()

            # Verify model_info is updated
            default_model = router.get_model_for_label("default")
            assert default_model is not None
            assert default_model["model_info"]["priority"] == "medium"
            assert default_model["model_info"]["cost_per_token"] == 0.015
            assert default_model["model_info"]["new_field"] == "new_value"
            assert "custom_field" not in default_model["model_info"]

    def test_reload_clears_removed_models(self) -> None:
        """Test that reload removes models that are no longer in config."""
        # Initial config with multiple models
        initial_config = {
            "model_list": [
                {"model_name": "default", "litellm_params": {"model": "gpt-4"}},
                {"model_name": "background", "litellm_params": {"model": "gpt-3.5-turbo"}},
                {"model_name": "think", "litellm_params": {"model": "o1-preview"}},
            ]
        }

        config_provider = ConfigProvider(CCProxyConfig())
        with patch.object(config_provider, "get") as mock_get:
            mock_config = MagicMock()
            mock_config.get_litellm_config.return_value = MagicMock(model_list=initial_config["model_list"])
            mock_get.return_value = mock_config

            router = ModelRouter(config_provider)

            # Verify all models available
            assert set(router.get_available_models()) == {"default", "background", "think"}

            # Update config to remove some models
            reduced_config = {
                "model_list": [
                    {"model_name": "default", "litellm_params": {"model": "claude-3-5-sonnet"}},
                ]
            }

            mock_config.get_litellm_config.return_value = MagicMock(model_list=reduced_config["model_list"])

            # Reload
            router.reload()

            # Verify only remaining model is available
            assert set(router.get_available_models()) == {"default"}
            assert not router.is_model_available("background")
            assert not router.is_model_available("think")

            # But fallback should still work
            background_model = router.get_model_for_label("background")
            assert background_model is not None
            assert background_model["model_name"] == "default"  # Falls back to default
