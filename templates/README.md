# CCProxy Templates

This directory contains template files that are copied to `~/.ccproxy` during installation.

## Files

- `ccproxy.yaml` - Main configuration file with routing rules and LiteLLM settings
- `config.yaml` - LiteLLM proxy configuration with model definitions
- `ccproxy.py` - Custom logger implementation for LiteLLM hooks
- `ccproxy.service` - Systemd user service file for managing the proxy server
