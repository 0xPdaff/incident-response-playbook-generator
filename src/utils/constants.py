"""Constants used across the application."""

from enum import Enum


class Severity(str, Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    """Incident type categories."""
    MALWARE = "malware"
    PHISHING = "phishing"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    DDOS = "ddos"
    INSIDER_THREAT = "insider_threat"
    SUPPLY_CHAIN = "supply_chain"
    MISCONFIGURATION = "misconfiguration"
    WEB_ATTACK = "web_attack"
    PHYSICAL = "physical"
    UNKNOWN = "unknown"


class OutputFormat(str, Enum):
    """Output format options."""
    MARKDOWN = "markdown"
    PDF = "pdf"


class InputMode(str, Enum):
    """Input mode options."""
    CLI_ARG = "cli_arg"
    CLI_INTERACTIVE = "cli_interactive"
    API = "api"
    FILE = "file"


class NISTPhase(str, Enum):
    """NIST incident response phases."""
    DETECTION = "Detection & Analysis"
    CONTAINMENT = "Containment"
    ERADICATION = "Eradication"
    RECOVERY = "Recovery"
    LESSONS_LEARNED = "Lessons Learned"


# Valid providers
SUPPORTED_PROVIDERS = [
    "openai",
    "anthropic",
    "deepseek",
    "minimax",
    "kimi",
    "qwen",
    "glm",
    "ollama",
]

# Maximum incident description length
MAX_DESCRIPTION_LENGTH = 10000

# Minimum incident description length
MIN_DESCRIPTION_LENGTH = 10

# Default output directory
DEFAULT_OUTPUT_DIR = "data/processed"

# Cache directory
CACHE_DIR = "data/cache"

# NIST phases in order
NIST_PHASES = [
    NISTPhase.DETECTION,
    NISTPhase.CONTAINMENT,
    NISTPhase.ERADICATION,
    NISTPhase.RECOVERY,
    NISTPhase.LESSONS_LEARNED,
]
