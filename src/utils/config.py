"""Configuration loader for YAML configs and environment variables."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file
load_dotenv(PROJECT_ROOT / ".env")


def load_yaml_config(filename: str, config_dir: str = "config") -> dict[str, Any]:
    """Load a YAML configuration file from the config directory.

    Args:
        filename: Name of the YAML file (e.g., 'model_config.yaml').
        config_dir: Directory containing config files.

    Returns:
        Parsed YAML as dictionary. Empty dict if file not found.
    """
    config_path = PROJECT_ROOT / config_dir / filename
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_model_config() -> dict[str, Any]:
    """Load model configuration."""
    return load_yaml_config("model_config.yaml")


def get_prompts() -> dict[str, Any]:
    """Load prompt templates."""
    return load_yaml_config("prompts.yaml")


def get_org_profile() -> dict[str, Any]:
    """Load organization profile. Returns empty dict if not found."""
    return load_yaml_config("org_profile.yaml")


def get_env(key: str, default: str | None = None) -> str | None:
    """Get an environment variable value."""
    return os.environ.get(key, default)


def get_default_provider() -> str:
    """Get the default LLM provider name."""
    env_provider = get_env("DEFAULT_PROVIDER")
    if env_provider:
        return env_provider
    config = get_model_config()
    return config.get("default_provider", "openai")


def get_api_port() -> int:
    """Get the API server port."""
    return int(get_env("API_PORT", "8000"))


def get_log_level() -> str:
    """Get the configured log level."""
    return get_env("LOG_LEVEL", "INFO")


def is_agent_enabled() -> bool:
    """Check if the agent is enabled (kill switch)."""
    config = get_model_config()
    return config.get("enabled", True)
