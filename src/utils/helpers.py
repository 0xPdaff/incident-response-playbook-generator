"""Helper functions for the application."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import MAX_DESCRIPTION_LENGTH, MIN_DESCRIPTION_LENGTH


def generate_timestamp() -> str:
    """Generate a filesystem-safe timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S%z")


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    sanitized = re.sub(r"[^\w\s-]", "", name.lower())
    sanitized = re.sub(r"[\s]+", "_", sanitized)
    return sanitized[:64]


def truncate_description(description: str) -> tuple[str, bool]:
    """Truncate description if too long. Returns (text, was_truncated)."""
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return description[:MAX_DESCRIPTION_LENGTH], True
    return description, False


def validate_description(description: str) -> tuple[bool, str]:
    """Validate an incident description.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not description or not description.strip():
        return False, (
            "Incident description is empty. Provide a description of the security "
            "incident.\nExample: 'We detected unusual outbound traffic from the "
            "finance server at 2 AM UTC.'"
        )
    cleaned = description.strip()
    if len(cleaned) < MIN_DESCRIPTION_LENGTH:
        return False, (
            f"Incident description too short ({len(cleaned)} chars). "
            f"Provide at least {MIN_DESCRIPTION_LENGTH} characters.\n"
            "Example: 'We detected unusual outbound traffic from the finance "
            "server at 2 AM UTC.'"
        )
    return True, ""


def validate_severity(severity: str | None) -> tuple[bool, str]:
    """Validate a severity level."""
    if severity is None:
        return True, ""
    valid = {"low", "medium", "high", "critical"}
    if severity.lower() not in valid:
        return False, f"Invalid severity '{severity}'. Use: {', '.join(sorted(valid))}"
    return True, ""


def validate_provider(provider: str | None) -> tuple[bool, str]:
    """Validate a provider name."""
    if provider is None:
        return True, ""
    from .constants import SUPPORTED_PROVIDERS
    if provider.lower() not in SUPPORTED_PROVIDERS:
        return False, (
            f"Unsupported provider '{provider}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    return True, ""


def compute_cache_key(*args: Any) -> str:
    """Compute a deterministic cache key from arguments."""
    serialized = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def ensure_directory(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_llm_json(text: str) -> dict[str, Any]:
    """Try to parse JSON from LLM output, handling markdown fences."""
    # Remove markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


def format_org_tech_stack(org_profile: dict[str, Any]) -> str:
    """Format the org tech stack as a readable string."""
    tech = org_profile.get("tech_stack", {})
    if not tech:
        return "Not configured"

    parts = []
    if "os" in tech:
        parts.append(f"OS: {', '.join(tech['os'])}")
    if "cloud_providers" in tech:
        parts.append(f"Cloud: {', '.join(tech['cloud_providers'])}")
    if "primary_database" in tech:
        parts.append(f"DB: {tech['primary_database']}")
    if "siem" in tech:
        parts.append(f"SIEM: {tech['siem']}")
    if "edr" in tech:
        parts.append(f"EDR: {tech['edr']}")
    if "firewall" in tech:
        parts.append(f"Firewall: {tech['firewall']}")
    if "identity_provider" in tech:
        parts.append(f"IdP: {tech['identity_provider']}")

    return " | ".join(parts) if parts else "Not configured"


def format_escalation_contacts(org_profile: dict[str, Any]) -> str:
    """Format escalation contacts from org profile."""
    teams = org_profile.get("teams", {})
    if not teams:
        return "No escalation contacts configured"

    lines = []
    for team_name, info in teams.items():
        contact = info.get("contact", "N/A")
        threshold = info.get("escalation_threshold", "N/A")
        lines.append(f"  - {team_name}: {contact} (escalate at: {threshold})")

    return "\n".join(lines)
