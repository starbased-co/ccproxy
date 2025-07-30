"""LiteLLM callback instance for CCProxy integration."""

from ccproxy.handler import CCProxyHandler

# Create the instance that LiteLLM will use
# This is what LiteLLM expects - a module with an instance
proxy_handler_instance = CCProxyHandler()
