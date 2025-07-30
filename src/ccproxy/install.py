#!/usr/bin/env python3
"""CCProxy installation helper module."""

import shutil
import sys
from pathlib import Path

# Configuration templates
CUSTOM_CALLBACKS_TEMPLATE = """from ccproxy.handler import CCProxyHandler

# Create the instance that LiteLLM will use
proxy_handler_instance = CCProxyHandler()
"""

CONFIG_YAML_TEMPLATE = """model_list:
  # Default model for regular use
  - model_name: default
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: ${ANTHROPIC_API_KEY}

  # Background model, see: https://docs.anthropic.com/en/docs/claude-code/costs#background-token-usage
  - model_name: background
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022
      api_key: ${ANTHROPIC_API_KEY}

  # Thinking model for complex reasoning (request.body.think = true)
  - model_name: think
    litellm_params:
      model: anthropic/claude-opus-4-20250514
      api_key: ${ANTHROPIC_API_KEY}

  # Large context model for >60k tokens (threshold configurable below)
  - model_name: large_context
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_key: ${GOOGLE_API_KEY}

  # Web search model for execution when the WebSearch tool is present
  - model_name: web_search
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: ${GOOGLE_API_KEY}

litellm_settings:
  callbacks: custom_callbacks.proxy_handler_instance

# CCProxy settings
ccproxy_settings:
  context_threshold: 60000  # Tokens threshold for large_context routing
  debug: true              # Enable debug logging to see routing decisions
"""


def install(force: bool = False) -> None:
    """Install CCProxy configuration files.

    Args:
        force: If True, overwrite existing files without prompting
    """
    # Check for old cclaude wrapper and inform about removal
    old_wrapper = Path.home() / ".local" / "bin" / "cclaude"
    if old_wrapper.exists() or old_wrapper.is_symlink():
        print("⚠️  Found old cclaude wrapper script")
        print("   The new version uses 'ccproxy claude' instead of 'cclaude'")
        try:
            response = input("   Remove old wrapper? [Y/n]: ")
            if response.lower() != "n":
                old_wrapper.unlink()
                print("   ✅ Removed old cclaude wrapper")
        except (EOFError, KeyboardInterrupt):
            print("   Skipping removal (non-interactive mode)")

    # Determine config directory
    config_dir = Path.home() / ".ccproxy"

    print("\n🚀 CCProxy Installation")
    print(f"📁 Creating configuration directory: {config_dir}")

    # Create directory
    config_dir.mkdir(exist_ok=True)

    # Create custom_callbacks.py
    callbacks_path = config_dir / "custom_callbacks.py"
    if callbacks_path.exists() and not force:
        try:
            response = input(f"\n⚠️  {callbacks_path} already exists. Overwrite? [y/N]: ")
            if response.lower() != "y":
                print("   Skipping custom_callbacks.py")
            else:
                callbacks_path.write_text(CUSTOM_CALLBACKS_TEMPLATE)
                print(f"✅ Created {callbacks_path}")
        except EOFError:
            print("   Skipping custom_callbacks.py (non-interactive mode)")
    else:
        callbacks_path.write_text(CUSTOM_CALLBACKS_TEMPLATE)
        print(f"✅ Created {callbacks_path}")

    # Create config.yaml
    config_path = config_dir / "config.yaml"
    if config_path.exists() and not force:
        try:
            response = input(f"\n⚠️  {config_path} already exists. Overwrite? [y/N]: ")
            if response.lower() != "y":
                print("   Skipping config.yaml")
            else:
                config_path.write_text(CONFIG_YAML_TEMPLATE)
                print(f"✅ Created {config_path}")
        except EOFError:
            print("   Skipping config.yaml (non-interactive mode)")
    else:
        config_path.write_text(CONFIG_YAML_TEMPLATE)
        print(f"✅ Created {config_path}")

    # Check if example config exists in package
    example_config = Path(__file__).parent.parent.parent / "config.yaml.example"
    if example_config.exists():
        example_dest = config_dir / "config.yaml.example"
        if not example_dest.exists():
            shutil.copy(example_config, example_dest)
            print(f"✅ Copied example config to {example_dest}")

    print("\n🎉 Installation complete!")
    print("\n📋 Next steps:")
    print("1. Set your API keys:")
    print("   export ANTHROPIC_API_KEY='your-key'")
    print("   export OPENAI_API_KEY='your-key'  # Optional")
    print("   export GOOGLE_API_KEY='your-key'   # Optional")
    print("")
    print("2. Use Claude with CCProxy routing:")
    print("   ccproxy claude --version")
    print("   ccproxy claude -p 'Hello world'")
    print("")
    print("   Or set an alias for convenience:")
    print("   alias claude='ccproxy claude'")
    print("")
    print("3. The proxy will start automatically when you use 'ccproxy claude'")
    print("")
    print("📚 For more information, see: https://github.com/starbased-co/ccproxy")


if __name__ == "__main__":
    # This module is meant to be run via -m ccproxy install
    print("Please run this module using: python -m ccproxy install")
    sys.exit(1)
