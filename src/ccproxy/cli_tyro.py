"""CCProxy CLI for managing the LiteLLM proxy server - Tyro implementation."""

import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import psutil
import tyro
import yaml
from tyro.extras import SubcommandApp

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


@dataclass
class GlobalConfig:
    """Global configuration for CCProxy."""

    config_dir: Path = field(default_factory=lambda: Path.home() / ".ccproxy")
    """Configuration directory for CCProxy."""


class CCProxyDaemon:
    """Manages the LiteLLM proxy server as a daemon process."""

    def __init__(self, config_dir: Path) -> None:
        """Initialize the daemon with configuration directory."""
        self.config_dir = config_dir
        self.pid_file = config_dir / "ccproxy.pid"
        self.log_file = config_dir / "ccproxy.log"

    def _load_litellm_config(self) -> dict[str, Any]:
        """Load LiteLLM configuration from ccproxy.yaml."""
        ccproxy_config_path = self.config_dir / "ccproxy.yaml"
        if not ccproxy_config_path.exists():
            return {}

        with ccproxy_config_path.open() as f:
            config = yaml.safe_load(f)

        litellm_config: dict[str, Any] = config.get("litellm", {}) if config else {}
        return litellm_config

    def _build_litellm_command(self, proxy_config: ProxyConfig) -> list[str]:
        """Build the litellm command with all configuration sources."""
        # Load config file defaults
        config = self._load_litellm_config()

        # Apply environment variable overrides
        host = os.environ.get("HOST", config.get("host", proxy_config.host))
        port = str(os.environ.get("PORT", config.get("port", proxy_config.port)))
        num_workers = str(os.environ.get("NUM_WORKERS", config.get("num_workers", proxy_config.workers)))
        debug = os.environ.get("DEBUG", str(config.get("debug", proxy_config.debug))).lower() == "true"
        detailed_debug = (
            os.environ.get("DETAILED_DEBUG", str(config.get("detailed_debug", proxy_config.detailed_debug))).lower()
            == "true"
        )

        # Build command
        cmd = [
            "litellm",
            "--config",
            str(self.config_dir / "config.yaml"),
            "--host",
            host,
            "--port",
            port,
            "--num_workers",
            num_workers,
        ]

        if debug:
            cmd.append("--debug")
        if detailed_debug:
            cmd.append("--detailed_debug")

        return cmd

    def _daemonize(self) -> None:
        """Daemonize the current process."""
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process exits
                sys.exit(0)
        except OSError as e:
            print(f"Fork #1 failed: {e}", file=sys.stderr)
            sys.exit(1)

        # Decouple from parent environment
        os.chdir(str(self.config_dir))
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process exits
                sys.exit(0)
        except OSError as e:
            print(f"Fork #2 failed: {e}", file=sys.stderr)
            sys.exit(1)

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Open log file for output
        log_fd = os.open(str(self.log_file), os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o666)
        os.dup2(log_fd, sys.stdout.fileno())
        os.dup2(log_fd, sys.stderr.fileno())
        os.close(log_fd)

    def start(self, proxy_config: ProxyConfig) -> None:
        """Start the LiteLLM proxy server as a daemon."""
        # Check if already running
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    print(f"CCProxy is already running (PID: {pid})")
                    sys.exit(1)
                else:
                    # Stale PID file
                    self.pid_file.unlink()
            except (ValueError, ProcessLookupError):
                # Invalid or stale PID file
                self.pid_file.unlink()

        # Build LiteLLM command
        cmd = self._build_litellm_command(proxy_config)

        # Daemonize
        self._daemonize()

        # Start LiteLLM as subprocess
        try:
            # Debug logging
            print(f"Starting LiteLLM with command: {cmd}")
            print(f"Working directory: {self.config_dir}")

            # Set up environment to include ccproxy in Python path
            env = os.environ.copy()
            # Add the site-packages directory where ccproxy is installed
            import ccproxy

            ccproxy_path = Path(ccproxy.__file__).parent.parent
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = f"{ccproxy_path}:{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = str(ccproxy_path)

            # S603: Command is built from validated config and CLI args only
            # After daemonizing, stdout/stderr are already redirected to log file
            # So we don't need PIPE here
            process = subprocess.Popen(  # noqa: S603
                cmd, stdout=None, stderr=None, text=True, cwd=str(self.config_dir), env=env
            )

            # Write PID file with LiteLLM process PID
            self.pid_file.write_text(str(process.pid))

            # Monitor the subprocess
            print(f"Started LiteLLM proxy (PID: {process.pid})")

            # Wait for the subprocess
            process.wait()

        except Exception as e:
            print(f"Failed to start LiteLLM: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            # Clean up PID file on exit
            if self.pid_file.exists():
                self.pid_file.unlink()

    def stop(self) -> None:
        """Stop the LiteLLM proxy server."""
        if not self.pid_file.exists():
            print("CCProxy is not running")
            sys.exit(1)

        try:
            pid = int(self.pid_file.read_text().strip())

            # Check if process exists
            if not psutil.pid_exists(pid):
                print("CCProxy is not running (stale PID file)")
                self.pid_file.unlink()
                sys.exit(1)

            # Send SIGTERM
            os.kill(pid, signal.SIGTERM)

            # Wait for graceful shutdown (up to 10 seconds)
            for _ in range(100):
                if not psutil.pid_exists(pid):
                    break
                time.sleep(0.1)
            else:
                # Force kill if still running
                print("Process did not terminate gracefully, forcing...")
                os.kill(pid, signal.SIGKILL)

            # Remove PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            print(f"Stopped CCProxy (PID: {pid})")

        except (ValueError, ProcessLookupError) as e:
            print(f"Failed to stop CCProxy: {e}", file=sys.stderr)
            if self.pid_file.exists():
                self.pid_file.unlink()
            sys.exit(1)

    def status(self) -> None:
        """Check the status of the LiteLLM proxy server."""
        if not self.pid_file.exists():
            print("CCProxy is not running")
            sys.exit(1)

        try:
            pid = int(self.pid_file.read_text().strip())

            if psutil.pid_exists(pid):
                try:
                    process = psutil.Process(pid)
                    print(f"CCProxy is running (PID: {pid})")
                    print(f"  CPU: {process.cpu_percent()}%")
                    print(f"  Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
                    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(process.create_time()))}")
                except psutil.NoSuchProcess:
                    print("CCProxy is not running (process not found)")
                    if self.pid_file.exists():
                        self.pid_file.unlink()
                    sys.exit(1)
            else:
                print("CCProxy is not running (stale PID file)")
                if self.pid_file.exists():
                    self.pid_file.unlink()
                sys.exit(1)

        except ValueError:
            print("Invalid PID file")
            if self.pid_file.exists():
                self.pid_file.unlink()
            sys.exit(1)


# Subcommand definitions using dataclasses
@dataclass
class Start:
    """Start the LiteLLM proxy server."""

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
    """Stop the LiteLLM proxy server."""

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
    pid_file = config_dir / "ccproxy.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if psutil.pid_exists(pid):
                print(f"Using running ccproxy instance (PID: {pid})")
            else:
                print("Warning: CCProxy is not running (stale PID file)", file=sys.stderr)
                print("Run 'ccproxy start' to start the proxy server", file=sys.stderr)
        except (ValueError, ProcessLookupError):
            print("Warning: CCProxy is not running (invalid PID file)", file=sys.stderr)
            print("Run 'ccproxy start' to start the proxy server", file=sys.stderr)
    else:
        print("Note: CCProxy is not running. Starting without proxy.", file=sys.stderr)
        print("Run 'ccproxy start' to start the proxy server", file=sys.stderr)

    # Load config
    with ccproxy_config_path.open() as f:
        config = yaml.safe_load(f)

    litellm_config = config.get("litellm", {}) if config else {}

    # Get proxy settings with defaults
    host = os.environ.get("HOST", litellm_config.get("host", "127.0.0.1"))
    port = os.environ.get("PORT", litellm_config.get("port", "4000"))

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
    global_config: GlobalConfig | None = None,
) -> None:
    """CCProxy - LiteLLM Transformation Hook System.

    A powerful routing system for LiteLLM that dynamically routes requests
    to different models based on configurable rules.
    """
    if global_config is None:
        global_config = GlobalConfig()

    # Create daemon instance
    daemon = CCProxyDaemon(global_config.config_dir)

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
        daemon.start(proxy_config)

    elif isinstance(cmd, Stop):
        daemon.stop()

    elif isinstance(cmd, Status):
        daemon.status()

    elif isinstance(cmd, Install):
        install_config(global_config.config_dir, force=cmd.force)

    elif isinstance(cmd, Run):
        if not cmd.command:
            print("Error: No command specified to run", file=sys.stderr)
            print("Usage: ccproxy run <command> [args...]", file=sys.stderr)
            sys.exit(1)
        run_with_proxy(global_config.config_dir, cmd.command)


def main_decorator() -> None:
    """Alternative entry point using decorator-based subcommand API."""
    app = SubcommandApp()

    @app.command
    def start(
        config_dir: Path | None = None,
        host: str | None = None,
        port: int | None = None,
        workers: int | None = None,
        debug: bool = False,
        detailed_debug: bool = False,
    ) -> None:
        """Start the LiteLLM proxy server.

        Args:
            config_dir: Configuration directory
            host: Host to bind to (overrides config)
            port: Port to bind to (overrides config)
            workers: Number of workers (overrides config)
            debug: Enable debug mode
            detailed_debug: Enable detailed debug mode
        """
        if config_dir is None:
            config_dir = Path.home() / ".ccproxy"
        daemon = CCProxyDaemon(config_dir)
        proxy_config = ProxyConfig(
            host=host or "127.0.0.1",
            port=port or 4000,
            workers=workers or 1,
            debug=debug,
            detailed_debug=detailed_debug,
        )
        daemon.start(proxy_config)

    @app.command
    def stop(config_dir: Path | None = None) -> None:
        """Stop the LiteLLM proxy server.

        Args:
            config_dir: Configuration directory
        """
        if config_dir is None:
            config_dir = Path.home() / ".ccproxy"
        daemon = CCProxyDaemon(config_dir)
        daemon.stop()

    @app.command
    def status(config_dir: Path | None = None) -> None:
        """Check status of the LiteLLM proxy server.

        Args:
            config_dir: Configuration directory
        """
        if config_dir is None:
            config_dir = Path.home() / ".ccproxy"
        daemon = CCProxyDaemon(config_dir)
        daemon.status()

    @app.command
    def install(
        config_dir: Path | None = None,
        force: bool = False,
    ) -> None:
        """Install CCProxy configuration files.

        Args:
            config_dir: Configuration directory
            force: Overwrite existing configuration
        """
        if config_dir is None:
            config_dir = Path.home() / ".ccproxy"
        install_config(config_dir, force=force)

    @app.command(name="run")
    def run_cmd(
        *command: str,
        config_dir: Path | None = None,
    ) -> None:
        """Run a command with ccproxy environment.

        Args:
            command: Command and arguments to execute
            config_dir: Configuration directory
        """
        if not command:
            print("Error: No command specified to run", file=sys.stderr)
            print("Usage: ccproxy run <command> [args...]", file=sys.stderr)
            sys.exit(1)
        if config_dir is None:
            config_dir = Path.home() / ".ccproxy"
        run_with_proxy(config_dir, list(command))

    app.cli()


if __name__ == "__main__":
    main_decorator()
