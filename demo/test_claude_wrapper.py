#!/usr/bin/env python3
"""Demo script to test the Claude wrapper functionality."""

import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str], capture: bool = True) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    print(f"\n$ {' '.join(cmd)}")

    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        return result.returncode, result.stdout, result.stderr
    else:
        returncode = subprocess.call(cmd)
        return returncode, "", ""


def main():
    """Demo the Claude wrapper."""
    print("=== CCProxy Claude Wrapper Demo ===\n")

    # Check if wrapper is installed
    print("1. Checking if claude wrapper is available...")
    rc, _, _ = run_command([sys.executable, "-m", "ccproxy.claude_wrapper", "--help"])
    if rc != 0:
        print("ERROR: Claude wrapper module not found. Make sure ccproxy is installed.")
        return 1

    # Check proxy state directory
    state_dir = Path.home() / ".ccproxy"
    print(f"\n2. Checking state directory: {state_dir}")
    if state_dir.exists():
        print("   State directory exists")
        state_file = state_dir / "claude_proxy.json"
        if state_file.exists():
            print(f"   Found existing state file: {state_file}")
            with open(state_file) as f:
                print(f"   Current state: {f.read()}")
    else:
        print("   State directory will be created on first run")

    # Simulate multiple Claude instances
    print("\n3. Simulating multiple Claude wrapper calls...")

    # First call - should start proxy
    print("\n   a) First wrapper call (should start new proxy):")
    env = os.environ.copy()
    env["CC_PROXY_CONFIG"] = str(Path("demo/demo_config.yaml").absolute())

    proc1 = subprocess.Popen(
        [sys.executable, "-m", "ccproxy.claude_wrapper", "--version"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give it time to start
    time.sleep(2)

    # Check state after first call
    if state_file.exists():
        print("\n   State after first call:")
        with open(state_file) as f:
            print(f"   {f.read()}")

    # Second call - should reuse proxy
    print("\n   b) Second wrapper call (should reuse proxy):")
    proc2 = subprocess.Popen(
        [sys.executable, "-m", "ccproxy.claude_wrapper", "--help"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for both to complete
    print("\n   Waiting for processes to complete...")
    out1, err1 = proc1.communicate()
    out2, err2 = proc2.communicate()

    print(f"\n   First call result: rc={proc1.returncode}")
    if out1:
        print(f"   Output: {out1}")
    if err1:
        print(f"   Error: {err1}")

    print(f"\n   Second call result: rc={proc2.returncode}")
    if out2:
        print(f"   Output: {out2}")
    if err2:
        print(f"   Error: {err2}")

    # Check final state
    print("\n4. Checking final state...")
    if state_file.exists():
        print("   State file still exists (proxy might still be running)")
        with open(state_file) as f:
            print(f"   Final state: {f.read()}")
    else:
        print("   State file removed (proxy shut down)")

    # Check log file
    log_file = state_dir / "proxy.log"
    if log_file.exists():
        print(f"\n5. Recent log entries from {log_file}:")
        with open(log_file) as f:
            lines = f.readlines()
            for line in lines[-20:]:  # Last 20 lines
                print(f"   {line.rstrip()}")

    print("\n=== Demo Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
