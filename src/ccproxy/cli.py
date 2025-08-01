"""CCProxy CLI for managing the LiteLLM proxy server - Tyro implementation."""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import httpx
import tyro
import yaml

from ccproxy.utils import get_templates_dir


@dataclass
class ProxyConfig:
    """Configuration for the LiteLLM proxy server."""

    host: str = "127.0.0.1"
    """Host to bind the proxy server to."""

    port: int = 4000
    """Port to bind the proxy server to."""

    workers: int = 1
    """Number of worker processes."""

    debug: bool = False
    """Enable debug mode."""

    detailed_debug: bool = False
    """Enable detailed debug mode."""


class CCProxyManager:
    """Manages interactions with the LiteLLM proxy server."""

    def __init__(self, config_dir: Path) -> None:
        """Initialize the manager with configuration directory."""
        self.config_dir = config_dir

    def _load_litellm_config(self) -> dict[str, Any]:
        """Load LiteLLM configuration from ccproxy.yaml."""
        ccproxy_config_path = self.config_dir / "ccproxy.yaml"
        if not ccproxy_config_path.exists():
            return {}

        with ccproxy_config_path.open() as f:
            config = yaml.safe_load(f)

        litellm_config: dict[str, Any] = config.get("litellm", {}) if config else {}
        return litellm_config

    def _get_server_config(self) -> tuple[str, int]:
        """Get server host and port from configuration."""
        config = self._load_litellm_config()
        host = os.environ.get("HOST", config.get("host", "127.0.0.1"))
        port = int(os.environ.get("PORT", config.get("port", 4000)))
        return host, port

    def _check_server_status(self) -> bool:
        """Check if LiteLLM server is running by making HTTP request."""
        host, port = self._get_server_config()
        url = f"http://{host}:{port}/health"

        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(url)
                return bool(response.status_code == 200)
        except (httpx.ConnectError, httpx.TimeoutError):
            return False

    def start(self, proxy_config: ProxyConfig) -> None:
        """Start the LiteLLM proxy server."""
        # Check if already running
        if self._check_server_status():
            host, port = self._get_server_config()
            print(f"LiteLLM server is already running on {host}:{port}")
            sys.exit(1)

        print("\nTo start LiteLLM server, run:")
        print(f"\n  litellm --config {self.config_dir}/config.yaml")
        print("\nOr with additional options:")
        print(
            f"  litellm --config {self.config_dir}/config.yaml --host {proxy_config.host} --port {proxy_config.port} --num_workers {proxy_config.workers}"  # noqa: E501
        )
        if proxy_config.debug:
            print("  Add: --debug")
        if proxy_config.detailed_debug:
            print("  Add: --detailed_debug")
        print("\nMake sure ccproxy is installed in your Python environment for the hooks to work.")
        sys.exit(0)

    def stop(self) -> None:
        """Stop the LiteLLM proxy server."""
        if not self._check_server_status():
            print("LiteLLM server is not running")
            sys.exit(1)

        print("\nTo stop the LiteLLM server, find its process and terminate it.")
        print("You can use: ps aux | grep litellm")
        print("Then: kill <PID>")
        sys.exit(0)

    def status(self) -> None:
        """Check the status of the LiteLLM proxy server."""
        host, port = self._get_server_config()

        if self._check_server_status():
            print(f"LiteLLM server is running on {host}:{port}")

            # Try to get additional info from server
            try:
                with httpx.Client(timeout=2.0) as client:
                    # Try health endpoint first
                    health_url = f"http://{host}:{port}/health"
                    response = client.get(health_url)
                    if response.status_code == 200:
                        print("  Status: Healthy")

                    # Try to get model info
                    models_url = f"http://{host}:{port}/models"
                    try:
                        response = client.get(models_url)
                        if response.status_code == 200:
                            data = response.json()
                            if "data" in data:
                                print(f"  Available models: {len(data['data'])}")
                    except Exception:  # noqa: S110
                        pass
            except Exception:  # noqa: S110
                pass

            sys.exit(0)
        else:
            print(f"LiteLLM server is not running on {host}:{port}")
            sys.exit(1)


# Subcommand definitions using dataclasses
@dataclass
class Start:
    """Show instructions to start the LiteLLM proxy server."""

    host: str | None = None
    """Host to bind to (overrides config)."""

    port: int | None = None
    """Port to bind to (overrides config)."""

    workers: int | None = None
    """Number of workers (overrides config)."""

    debug: bool = False
    """Enable debug mode."""

    detailed_debug: bool = False
    """Enable detailed debug mode."""


@dataclass
class Stop:
    """Show instructions to stop the LiteLLM proxy server."""

    pass


@dataclass
class Status:
    """Check status of the LiteLLM proxy server."""

    pass


@dataclass
class Install:
    """Install CCProxy configuration files."""

    force: bool = False
    """Overwrite existing configuration."""


@dataclass
class Run:
    """Run a command with ccproxy environment."""

    command: Annotated[list[str], tyro.conf.Positional]
    """Command and arguments to execute with proxy settings."""


# Type alias for all subcommands
Command = Start | Stop | Status | Install | Run


def install_config(config_dir: Path, force: bool = False) -> None:
    """Install CCProxy configuration files.

    Args:
        config_dir: Directory to install configuration files to
        force: Whether to overwrite existing configuration
    """
    # Check if config directory exists
    if config_dir.exists() and not force:
        print(f"Configuration directory {config_dir} already exists.")
        print("Use --force to overwrite existing configuration.")
        sys.exit(1)

    # Create config directory
    config_dir.mkdir(parents=True, exist_ok=True)
    print(f"Creating configuration directory: {config_dir}")

    # Get templates directory
    try:
        templates_dir = get_templates_dir()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # List of files to copy
    template_files = [
        "ccproxy.yaml",
        "config.yaml",
        "ccproxy.py",
    ]

    # Copy template files
    for filename in template_files:
        src = templates_dir / filename
        dst = config_dir / filename

        if src.exists():
            if dst.exists() and not force:
                print(f"  Skipping {filename} (already exists)")
            else:
                shutil.copy2(src, dst)
                print(f"  Copied {filename}")
        else:
            print(f"  Warning: Template {filename} not found", file=sys.stderr)

    print(f"\nInstallation complete! Configuration files installed to: {config_dir}")
    print("\nNext steps:")
    print(f"  1. Edit {config_dir}/ccproxy.yaml to configure routing rules")
    print(f"  2. Edit {config_dir}/config.yaml to configure LiteLLM models")
    print("  3. Start the proxy with: ccproxy start")


def run_with_proxy(config_dir: Path, command: list[str]) -> None:
    """Run a command with ccproxy environment variables set.

    Args:
        config_dir: Configuration directory
        command: Command and arguments to execute
    """
    # Load litellm config to get proxy settings
    ccproxy_config_path = config_dir / "ccproxy.yaml"
    if not ccproxy_config_path.exists():
        print(f"Error: Configuration not found at {ccproxy_config_path}", file=sys.stderr)
        print("Run 'ccproxy install' first to set up configuration.", file=sys.stderr)
        sys.exit(1)

    # Check if proxy is running
    manager = CCProxyManager(config_dir)
    if manager._check_server_status():
        host, port = manager._get_server_config()
        print(f"Using running LiteLLM server on {host}:{port}")
    else:
        print("Warning: LiteLLM server is not running.", file=sys.stderr)
        print("Run 'litellm --config <config.yaml>' to start the proxy server", file=sys.stderr)

    # Load config
    with ccproxy_config_path.open() as f:
        config = yaml.safe_load(f)

    litellm_config = config.get("litellm", {}) if config else {}

    # Get proxy settings with defaults
    host = os.environ.get("HOST", litellm_config.get("host", "127.0.0.1"))
    port = int(os.environ.get("PORT", litellm_config.get("port", 4000)))

    # Set up environment for the subprocess
    env = os.environ.copy()

    # Set proxy environment variables
    proxy_url = f"http://{host}:{port}"
    env["OPENAI_API_BASE"] = f"{proxy_url}/v1"
    env["OPENAI_BASE_URL"] = f"{proxy_url}/v1"
    env["ANTHROPIC_BASE_URL"] = f"{proxy_url}/v1"
    env["LITELLM_PROXY_BASE_URL"] = proxy_url
    env["LITELLM_PROXY_API_BASE"] = f"{proxy_url}/v1"

    # Also set standard HTTP proxy variables for general compatibility
    env["HTTP_PROXY"] = proxy_url
    env["HTTPS_PROXY"] = proxy_url
    env["http_proxy"] = proxy_url
    env["https_proxy"] = proxy_url

    # Execute the command with the proxy environment
    try:
        # S603: Command comes from user input - this is the intended behavior
        result = subprocess.run(command, env=env)  # noqa: S603
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"Error: Command not found: {command[0]}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)  # Standard exit code for Ctrl+C


def main(
    cmd: Annotated[Command, tyro.conf.arg(name="")],
    *,
    config_dir: Annotated[Path | None, tyro.conf.arg(help="Configuration directory")] = None,
) -> None:
    """CCProxy - LiteLLM Transformation Hook System.

    A powerful routing system for LiteLLM that dynamically routes requests
    to different models based on configurable rules.
    """
    if config_dir is None:
        config_dir = Path.home() / ".ccproxy"

    # Create manager instance
    manager = CCProxyManager(config_dir)

    # Handle each command type
    if isinstance(cmd, Start):
        # Build proxy config from command options
        proxy_config = ProxyConfig(
            host=cmd.host or "127.0.0.1",
            port=cmd.port or 4000,
            workers=cmd.workers or 1,
            debug=cmd.debug,
            detailed_debug=cmd.detailed_debug,
        )
        manager.start(proxy_config)

    elif isinstance(cmd, Stop):
        manager.stop()

    elif isinstance(cmd, Status):
        manager.status()

    elif isinstance(cmd, Install):
        install_config(config_dir, force=cmd.force)

    elif isinstance(cmd, Run):
        if not cmd.command:
            print("Error: No command specified to run", file=sys.stderr)
            print("Usage: ccproxy run <command> [args...]", file=sys.stderr)
            sys.exit(1)
        run_with_proxy(config_dir, cmd.command)


def entry_point() -> None:
    """Entry point for the ccproxy command."""
    tyro.cli(main)


if __name__ == "__main__":
    entry_point()
