"""Configuration file watcher for hot-reload functionality."""

import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler  # type: ignore[import-not-found]

from ccproxy.config import reload_config


class ConfigFileHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Handles file system events for configuration files."""

    def __init__(
        self,
        config_path: Path,
        callback: Callable[[], None] | None = None,
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize the config file handler.

        Args:
            config_path: Path to the configuration file to watch
            callback: Optional callback to run after config reload
            debounce_seconds: Seconds to wait before reloading (to avoid multiple rapid reloads)
        """
        self.config_path = config_path.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._reload_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async operations."""
        self._loop = loop

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        # Check if the modified file is our config file
        if Path(str(event.src_path)).resolve() == self.config_path:
            self._schedule_reload()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events (for atomic file updates)."""
        if event.is_directory:
            return

        # Some editors create a new file and rename it
        if Path(str(event.src_path)).resolve() == self.config_path:
            self._schedule_reload()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events (for atomic file updates)."""
        if event.is_directory:
            return

        # Check if file was moved to our config path
        if hasattr(event, "dest_path") and Path(str(event.dest_path)).resolve() == self.config_path:
            self._schedule_reload()

    def _schedule_reload(self) -> None:
        """Schedule a config reload with debouncing."""
        # Cancel any pending reload
        if self._reload_task and not self._reload_task.done():
            self._reload_task.cancel()

        # Schedule new reload
        if self._loop:
            self._reload_task = self._loop.create_task(self._reload_config())

    async def _reload_config(self) -> None:
        """Reload configuration after debounce period."""
        await asyncio.sleep(self.debounce_seconds)

        try:
            # Reload the configuration
            reload_config()
            print(f"Configuration reloaded from {self.config_path}")

            # Call the callback if provided
            if self.callback:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback()
                else:
                    self.callback()

        except Exception as e:
            print(f"Error reloading configuration: {e}")


class ConfigWatcher:
    """Watches configuration files for changes and triggers hot-reload."""

    def __init__(
        self,
        config_path: Path | None = None,
        callback: Callable[[], None] | None = None,
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize the configuration watcher.

        Args:
            config_path: Path to config file (defaults to LITELLM_CONFIG_PATH env var)
            callback: Optional callback to run after config reload
            debounce_seconds: Seconds to wait before reloading
        """
        if config_path is None:
            config_path = Path(os.getenv("LITELLM_CONFIG_PATH", "./config.yaml"))

        self.config_path = config_path.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._observer: Any = None
        self._handler: ConfigFileHandler | None = None

    def start(self) -> None:
        """Start watching the configuration file."""
        if self._observer is not None:
            # Stop old observer if it exists
            self.stop()

        # Create event handler
        self._handler = ConfigFileHandler(
            self.config_path,
            self.callback,
            self.debounce_seconds,
        )

        # Set event loop for async operations
        try:
            loop = asyncio.get_running_loop()
            self._handler.set_event_loop(loop)
        except RuntimeError:
            # No running loop, handler will work in sync mode
            pass

        # Create and start observer
        from watchdog.observers import Observer  # type: ignore[import-not-found]

        self._observer = Observer()

        # Watch the directory containing the config file
        watch_dir = self.config_path.parent
        self._observer.schedule(self._handler, str(watch_dir), recursive=False)

        self._observer.start()
        print(f"Started watching {self.config_path} for changes")

    def stop(self) -> None:
        """Stop watching the configuration file."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            print(f"Stopped watching {self.config_path}")

    def __enter__(self) -> "ConfigWatcher":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.stop()


# Global watcher instance
_config_watcher: ConfigWatcher | None = None


def start_config_watcher(
    config_path: Path | None = None,
    callback: Callable[[], None] | None = None,
) -> ConfigWatcher:
    """Start the global configuration watcher.

    Args:
        config_path: Path to config file (defaults to LITELLM_CONFIG_PATH env var)
        callback: Optional callback to run after config reload

    Returns:
        The ConfigWatcher instance
    """
    global _config_watcher

    if _config_watcher is not None:
        _config_watcher.stop()

    _config_watcher = ConfigWatcher(config_path, callback)
    _config_watcher.start()

    return _config_watcher


def stop_config_watcher() -> None:
    """Stop the global configuration watcher."""
    global _config_watcher

    if _config_watcher is not None:
        _config_watcher.stop()
        _config_watcher = None
