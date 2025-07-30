"""Allow ccproxy to be run as a module with -m."""

import sys

from ccproxy.install import install

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "install":
        print("Usage: python -m ccproxy install [--force]")
        print("       uv run -m ccproxy install [--force]")
        print("")
        print("Options:")
        print("  --force    Overwrite existing files without prompting")
        sys.exit(1)

    force = "--force" in sys.argv
    try:
        install(force=force)
    except KeyboardInterrupt:
        print("\n\n❌ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)
