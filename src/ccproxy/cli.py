"""Main CLI entry point for ccproxy."""

import sys
from typing import NoReturn

from ccproxy.claude_wrapper import main as claude_main
from ccproxy.install import install


def print_usage() -> None:
    """Print usage information."""
    print("Usage: ccproxy <command> [options]")
    print("")
    print("Commands:")
    print("  install    Install ccproxy as claude command wrapper")
    print("  claude     Run claude CLI through ccproxy")
    print("")
    print("Examples:")
    print("  ccproxy install                  # Install ccproxy")
    print("  ccproxy claude --version         # Run claude with ccproxy routing")
    print("  ccproxy claude -p 'Hello'        # Use claude interactively")


def main() -> NoReturn:
    """Main entry point for ccproxy CLI."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "install":
        # Handle install command
        force = "--force" in sys.argv
        try:
            install(force=force)
        except KeyboardInterrupt:
            print("\n\n❌ Installation cancelled by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Installation failed: {e}")
            sys.exit(1)

    elif command == "claude":
        # Remove 'ccproxy' and 'claude' from argv to pass the rest to claude
        sys.argv = [sys.argv[0]] + sys.argv[2:]

        # Run claude wrapper
        try:
            exit_code = claude_main()
            sys.exit(exit_code)
        except KeyboardInterrupt:
            sys.exit(130)  # Standard exit code for Ctrl+C
        except Exception as e:
            print(f"Error running claude: {e}", file=sys.stderr)
            sys.exit(1)

    elif command in ["--help", "-h", "help"]:
        print_usage()
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        print()
        print_usage()
        sys.exit(1)

    # This should never be reached, but satisfies mypy
    raise SystemExit(1)


if __name__ == "__main__":
    main()
