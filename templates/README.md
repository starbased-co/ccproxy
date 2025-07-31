# CCProxy Templates

This directory contains template configuration files that are copied to ~/.ccproxy during installation.

## Template Files

- **ccproxy.py** - The hook file that LiteLLM loads
- **ccproxy.yaml** - Example ccproxy configuration with built-in rules
- **config.yaml** - Example LiteLLM configuration with model definitions

## For Custom Rule Examples

See the `examples/` directory for:
- Custom rule implementation examples
- Advanced configuration examples

## Installation

These files are automatically copied to `~/.ccproxy` when you run:

```bash
ccproxy install
```

You can then customize them for your specific needs.
