"""Custom callbacks for LiteLLM proxy with CCProxy integration."""

import sys
from pathlib import Path

# Add the src directory to Python path so we can import ccproxy
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ccproxy.handler import CCProxyHandler

# Create the instance that LiteLLM will use
proxy_handler_instance = CCProxyHandler()
