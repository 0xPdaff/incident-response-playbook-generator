"""Session state management for the agent."""

from dataclasses import dataclass, field
from typing import Any

from src.utils.config import get_org_profile


@dataclass
class SessionState:
    """Maintains state for a playbook generation session."""

    incident_description: str = ""
    severity: str | None = None
    provider: str | None = None
    output_format: str = "markdown"
    org_profile: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    playbook: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def load_org_profile(self) -> None:
        """Load the organization profile from config."""
        profile = get_org_profile()
        if profile:
            self.org_profile = profile
        else:
            self.warnings.append("No org profile found, using defaults")

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state to dictionary."""
        return {
            "incident_description": self.incident_description[:100] + "...",
            "severity": self.severity,
            "provider": self.provider,
            "output_format": self.output_format,
            "org_name": self.org_profile.get("org", {}).get("name", "Unknown"),
            "has_playbook": self.playbook is not None,
            "errors": self.errors,
            "warnings": self.warnings,
        }
