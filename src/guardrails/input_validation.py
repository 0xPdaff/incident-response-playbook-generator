"""Input validation and sanitization guardrails."""

import re
import logging
from dataclasses import dataclass, field

from src.utils.constants import (
    MAX_DESCRIPTION_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    SUPPORTED_PROVIDERS,
)
from src.utils.helpers import validate_description, validate_severity, validate_provider

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_description: str = ""
    severity: str | None = None
    provider: str | None = None


# Patterns that may indicate PII in incident description
PII_PATTERNS = [
    (r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b", "Possible SSN"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email address"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "Phone number"),
    (r"\b\d{16,19}\b", "Possible credit card number"),
    (r"\b(?:\d[ -]?){15,16}\b", "Possible credit card number (with spaces)"),
]


def detect_pii(text: str) -> list[str]:
    """Detect potential PII in text. Returns list of warnings."""
    warnings = []
    for pattern, description in PII_PATTERNS:
        if re.search(pattern, text):
            warnings.append(f"Potential PII detected: {description}")
    return warnings


def sanitize_input(text: str) -> str:
    """Sanitize user input for safe processing.

    - Strip leading/trailing whitespace
    - Normalize line endings
    - Remove null bytes
    - Truncate if too long
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip whitespace
    text = text.strip()

    # Truncate if needed
    if len(text) > MAX_DESCRIPTION_LENGTH:
        logger.warning(
            "Description truncated from %d to %d characters",
            len(text),
            MAX_DESCRIPTION_LENGTH,
        )
        text = text[:MAX_DESCRIPTION_LENGTH]

    return text


def validate_playbook_request(
    description: str,
    severity: str | None = None,
    provider: str | None = None,
) -> ValidationResult:
    """Validate a complete playbook generation request.

    Args:
        description: The incident description text.
        severity: Optional severity level.
        provider: Optional LLM provider override.

    Returns:
        ValidationResult with validation status, errors, and sanitized data.
    """
    result = ValidationResult()

    # Sanitize description
    sanitized = sanitize_input(description)
    result.sanitized_description = sanitized

    # Validate description
    is_valid_desc, desc_error = validate_description(sanitized)
    if not is_valid_desc:
        result.is_valid = False
        result.errors.append(desc_error)
        return result

    # Check for PII
    pii_warnings = detect_pii(sanitized)
    result.warnings.extend(pii_warnings)

    # Validate severity
    if severity:
        is_valid_sev, sev_error = validate_severity(severity)
        if not is_valid_sev:
            result.is_valid = False
            result.errors.append(sev_error)
        else:
            result.severity = severity.lower()

    # Validate provider
    if provider:
        is_valid_prov, prov_error = validate_provider(provider)
        if not is_valid_prov:
            result.warnings.append(prov_error)
            result.provider = None
        else:
            result.provider = provider.lower()

    return result


def check_destructive_commands(playbook_text: str) -> list[str]:
    """Check generated playbook for potentially destructive commands.

    Returns list of warnings for commands that should have safety markers.
    """
    destructive_patterns = [
        (r"\brm\s+-rf\s+/", "Recursive force delete from root"),
        (r"\bshutdown\b", "System shutdown"),
        (r"\breboot\b", "System reboot"),
        (r"\bDROP\s+(TABLE|DATABASE)", "SQL DROP statement"),
        (r"\bDELETE\s+FROM\b", "SQL DELETE without WHERE"),
        (r"\bformat\s+[A-Z]:", "Disk format"),
        (r"\biptables\s+-F\b", "Flush all firewall rules"),
        (r"\bkubectl\s+delete\s+(namespace|deployment|pod)\s+--all",
         "Delete all Kubernetes resources"),
    ]

    warnings = []
    for pattern, description in destructive_patterns:
        matches = re.findall(pattern, playbook_text, re.IGNORECASE)
        if matches:
            # Check if there's a warning marker nearby
            for match in matches:
                if "⚠️" not in playbook_text or "WARNING" not in playbook_text.upper():
                    warnings.append(
                        f"Destructive command detected without warning marker: "
                        f"{description}"
                    )

    return warnings
