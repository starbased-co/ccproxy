#!/usr/bin/env python3
"""Claude CLI wrapper that transparently routes through CCProxy-enabled LiteLLM."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import fasteners  # type: ignore[import-not-found]
import psutil  # type: ignore[import-untyped]

# Setup logging with rotation
LOG_DIR = Path.home() / ".ccproxy"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "proxy.log"

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=10_485_760,
    backupCount=5,  # 10MB
)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Constants
LOCK_FILE = LOG_DIR / "claude.lock"
STATE_FILE = LOG_DIR / "claude_proxy.json"
CONFIG_FILE = LOG_DIR / "config.yaml"
PROXY_START_TIMEOUT = 30  # seconds
PROXY_SHUTDOWN_GRACE = 5  # seconds


def find_free_port() -> int:
    """Find a free port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return int(port)


def is_process_alive(pid: int) -> bool:
    """Check if a process is alive using psutil."""
    try:
        process = psutil.Process(pid)
        return bool(process.is_running() and process.status() != psutil.STATUS_ZOMBIE)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def is_port_listening(port: int, timeout: float = 1.0) -> bool:
    """Check if a port is listening."""
    try:
        with socket.create_connection(("localhost", port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False


def wait_for_proxy_start(port: int, timeout: float = PROXY_START_TIMEOUT) -> bool:
    """Wait for proxy to start listening on the given port."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_listening(port):
            return True
        time.sleep(0.5)
    return False


def get_proxy_env(port: int) -> dict[str, str]:
    """Get environment variables for routing through the proxy."""
    proxy_url = f"http://localhost:{port}"
    openai_base = f"{proxy_url}/v1"

    env = {
        "LITELLM_PROXY_PORT": str(port),
        "HTTP_PROXY": proxy_url,
        "HTTPS_PROXY": proxy_url,
        "OPENAI_BASE_URL": openai_base,
        "ANTHROPIC_BASE_URL": openai_base,  # LiteLLM handles the routing
        # Pass through Claude API key if set
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    }

    # Remove empty values
    return {k: v for k, v in env.items() if v}


def start_proxy(port: int) -> subprocess.Popen[bytes]:
    """Start the LiteLLM proxy with CCProxy handler."""
    # Prepare clean environment
    clean_env = os.environ.copy()
    clean_env["LITELLM_PROXY_PORT"] = str(port)

    # Set config path if available
    if CONFIG_FILE.exists():
        clean_env["LITELLM_CONFIG_PATH"] = str(CONFIG_FILE)
    else:
        # Look for config in standard locations
        for config_path in [
            Path("config.yaml"),
            Path("litellm_config.yaml"),
            Path(".ccproxy/config.yaml"),
        ]:
            if config_path.exists():
                clean_env["LITELLM_CONFIG_PATH"] = str(config_path.absolute())
                break

    # Respect user overrides
    if "CC_PROXY_CONFIG" in os.environ:
        clean_env["LITELLM_CONFIG_PATH"] = os.environ["CC_PROXY_CONFIG"]

    # Start proxy subprocess
    cmd = [
        "litellm",
        "--port",
        str(port),
        "--drop_params",  # Allow pass-through of Claude-specific params
    ]

    if "LITELLM_CONFIG_PATH" in clean_env:
        cmd.extend(["--config", clean_env["LITELLM_CONFIG_PATH"]])

    logger.info(f"Starting proxy: {' '.join(cmd)}")

    with LOG_FILE.open("a") as log_fd:
        process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            env=clean_env,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )

    return process


def load_state() -> dict[str, Any] | None:
    """Load proxy state from file."""
    if not STATE_FILE.exists():
        return None

    try:
        with STATE_FILE.open() as f:
            state: dict[str, Any] = json.load(f)
            return state
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load state: {e}")
        return None


def save_state(state: dict[str, Any]) -> None:
    """Save proxy state to file."""
    try:
        with STATE_FILE.open("w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save state: {e}")


def delete_state() -> None:
    """Delete proxy state file."""
    try:
        STATE_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.error(f"Failed to delete state: {e}")


def shutdown_proxy(pid: int) -> None:
    """Gracefully shutdown the proxy process."""
    if not is_process_alive(pid):
        return

    try:
        process = psutil.Process(pid)

        # Try graceful shutdown first
        logger.info(f"Sending SIGTERM to proxy {pid}")
        process.terminate()

        # Wait for graceful shutdown
        try:
            process.wait(timeout=PROXY_SHUTDOWN_GRACE)
            logger.info(f"Proxy {pid} shut down gracefully")
        except psutil.TimeoutExpired:
            # Force kill if still running
            logger.warning(f"Proxy {pid} didn't stop gracefully, killing")
            process.kill()
            process.wait()
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.error(f"Failed to shutdown proxy: {e}")


def main() -> int:
    """Main entry point for the Claude wrapper."""
    # Get lock for coordination
    lock = fasteners.InterProcessLock(str(LOCK_FILE))

    # Respect user settings
    port = int(os.environ.get("CC_PROXY_PORT", "0"))

    try:
        with lock:
            state = load_state()

            # Check if proxy is alive and valid
            if state and is_process_alive(state["pid"]) and is_port_listening(state["port"]):
                # Reuse existing proxy
                logger.info(f"Reusing existing proxy on port {state['port']}")
                port = state["port"]
                state["refcount"] = state.get("refcount", 0) + 1
                save_state(state)
            else:
                # Start new proxy
                if port == 0:
                    port = find_free_port()

                logger.info(f"Starting new proxy on port {port}")
                proxy_process = start_proxy(port)

                # Wait for proxy to start
                if not wait_for_proxy_start(port):
                    logger.error("Proxy failed to start")
                    proxy_process.terminate()
                    return 1

                # Save state
                state = {
                    "pid": proxy_process.pid,
                    "port": port,
                    "start_time": time.time(),
                    "refcount": 1,
                }
                save_state(state)
                logger.info(f"Proxy started successfully on port {port}")

    except Exception as e:
        logger.error(f"Failed to start/connect to proxy: {e}")
        return 1

    # Prepare environment for Claude
    claude_env = os.environ.copy()
    claude_env.update(get_proxy_env(port))

    # Execute the real Claude CLI
    try:
        # Check if claude command exists
        claude_cmd = "claude"
        if subprocess.run(["which", claude_cmd], capture_output=True, check=False).returncode != 0:  # noqa: S603, S607
            logger.error("Claude CLI not found.")
            print("Error: Claude CLI not found. Please install Claude Code.", file=sys.stderr)
            return 1

        # Run Claude with all original arguments
        logger.info(f"Running {claude_cmd} with args: {sys.argv[1:]}")
        result = subprocess.call([claude_cmd] + sys.argv[1:], env=claude_env)  # noqa: S603

        return result

    finally:
        # Cleanup: decrement refcount and potentially shutdown proxy
        try:
            with lock:
                state = load_state()
                if state:
                    state["refcount"] = max(0, state.get("refcount", 1) - 1)

                    if state["refcount"] == 0:
                        logger.info("Last Claude instance exiting, shutting down proxy")
                        shutdown_proxy(state["pid"])
                        delete_state()
                    else:
                        logger.info(f"Claude instance exiting, {state['refcount']} instances remaining")
                        save_state(state)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
