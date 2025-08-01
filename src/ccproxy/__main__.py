"""Allow ccproxy to be run as a module with -m."""

import tyro

from ccproxy.cli import main

if __name__ == "__main__":
    tyro.cli(main)
