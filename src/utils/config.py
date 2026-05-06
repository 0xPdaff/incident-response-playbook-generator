"""Configuration loader for YAML configs and environment variables."""

import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _resolve_project_root() -> Path:
    """Resolve the project root directory.

    Works in two modes:
    1. Development mode: running from the project directory.
       PROJECT_ROOT is the parent of src/.
    2. Installed package mode: running as a pip-installed CLI.
       Config is looked up in ~/.ir-playbook/config/ and created
       from package-bundled defaults on first run.
    """
    # Try development mode first: look for config/ dir next to src/
    src_dir = Path(__file__).resolve().parent.parent
    candidate = src_dir.parent
    if (candidate / "config" / "model_config.yaml").exists():
        return candidate

    # Installed package mode: use ~/.ir-playbook/
    user_dir = Path.home() / ".ir-playbook"
    user_config_dir = user_dir / "config"

    if not (user_config_dir / "model_config.yaml").exists():
        # First run: copy default config from package data
        _initialize_user_config(src_dir, user_dir, user_config_dir)

    return user_dir


def _initialize_user_config(
    src_dir: Path,
    user_dir: Path,
    user_config_dir: Path,
) -> None:
    """Copy default config files to the user's ~/.ir-playbook/ directory."""
    # Package-bundled config is at <src_dir>/../config/
    bundled_config = src_dir.parent / "config"

    # If bundled config exists, copy it
    if bundled_config.exists():
        user_config_dir.mkdir(parents=True, exist_ok=True)
        for yaml_file in bundled_config.glob("*.yaml"):
            if not (user_config_dir / yaml_file.name).exists():
                shutil.copy2(yaml_file, user_config_dir / yaml_file.name)
    else:
        # Fallback: create minimal config
        user_config_dir.mkdir(parents=True, exist_ok=True)
        _write_minimal_config(user_config_dir)

    # Create data directories
    for subdir in ["cache", "processed", "raw"]:
        (user_dir / "data" / subdir).mkdir(parents=True, exist_ok=True)


def _write_minimal_config(config_dir: Path) -> None:
    """Write minimal config files when no bundled config is available."""
    if not (config_dir / "model_config.yaml").exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        minimal_model = {
            "enabled": True,
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "model": "gpt-4o",
                    "api_base": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "max_tokens": 4096,
                    "temperature": 0.3,
                    "timeout": 60,
                },
                "ollama": {
                    "model": "ollama/llama3",
                    "api_base": "http://localhost:11434",
                    "api_key_env": "",
                    "max_tokens": 4096,
                    "temperature": 0.3,
                    "timeout": 120,
                },
            },
            "fallback_chain": ["openai", "ollama"],
            "retry": {"max_retries": 3, "backoff_factor": 2},
            "cache": {"enabled": True, "ttl_seconds": 3600, "directory": "data/cache"},
        }
        with open(config_dir / "model_config.yaml", "w") as f:
            yaml.dump(minimal_model, f, default_flow_style=False, sort_keys=False)

    if not (config_dir / "prompts.yaml").exists():
        # Prompts will be loaded as empty; user should copy from repo
        with open(config_dir / "prompts.yaml", "w") as f:
            f.write("# Prompt templates — copy from the project repo or provide your own.\n")


# Project root directory (resolved once at import time)
PROJECT_ROOT = _resolve_project_root()

# Load .env file (from project root if present)
_dotenv_path = PROJECT_ROOT / ".env"
if not _dotenv_path.exists():
    # Also try CWD for installed mode
    _cwd_env = Path.cwd() / ".env"
    if _cwd_env.exists():
        _dotenv_path = _cwd_env
load_dotenv(_dotenv_path)


def load_yaml_config(filename: str, config_dir: str = "config") -> dict[str, Any]:
    """Load a YAML configuration file from the config directory.

    Search order:
    1. PROJECT_ROOT/config/<filename>
    2. CWD/config/<filename> (for installed package mode)

    Args:
        filename: Name of the YAML file (e.g., 'model_config.yaml').
        config_dir: Directory containing config files.

    Returns:
        Parsed YAML as dictionary. Empty dict if file not found.
    """
    config_path = PROJECT_ROOT / config_dir / filename
    if not config_path.exists():
        # Fallback: try CWD
        cwd_path = Path.cwd() / config_dir / filename
        if cwd_path.exists():
            config_path = cwd_path
        else:
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
