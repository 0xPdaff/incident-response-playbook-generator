"""Playbook generation chain — generates the full NIST playbook."""

import logging
from datetime import datetime, timezone
from typing import Any

from src.agent.chains.classifier import classify_incident, infer_severity
from src.inference.engine import InferenceEngine
from src.utils.config import get_org_profile, get_prompts
from src.utils.helpers import (
    format_org_tech_stack,
    format_escalation_contacts,
)

logger = logging.getLogger(__name__)


def build_playbook_prompt(
    description: str,
    classification: dict[str, Any],
    org_profile: dict[str, Any],
) -> tuple[str, str]:
    """Build the system and user prompts for playbook generation.

    Args:
        description: Sanitized incident description.
        classification: Classification result from the classifier.
        org_profile: Organization profile dict.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    prompts = get_prompts()
    gen_prompts = prompts.get("playbook_generation", {})

    system_template = gen_prompts.get("system", "")
    user_template = gen_prompts.get("user", "")

    org = org_profile.get("org", {})
    tech = org_profile.get("tech_stack", {})
    compliance = org_profile.get("compliance", {})

    system_prompt = system_template.format(
        org_name=org.get("name", "Unknown Organization"),
        org_industry=org.get("industry", "unknown"),
        org_size=org.get("size", "unknown"),
        tech_stack=format_org_tech_stack(org_profile),
        siem=tech.get("siem", "Not configured"),
        edr=tech.get("edr", "Not configured"),
        firewall=tech.get("firewall", "Not configured"),
        identity_provider=tech.get("identity_provider", "Not configured"),
        incident_type=classification.get("incident_type", "unknown"),
        severity=classification.get("severity", "medium"),
        mitre_tactics=", ".join(classification.get("mitre_tactics", [])),
        mitre_techniques=", ".join(classification.get("mitre_techniques", [])),
        compliance_frameworks=", ".join(compliance.get("frameworks", [])),
        breach_notification_hours=compliance.get("data_breach_notification_hours", 72),
        requires_le_notification=compliance.get("requires_law_enforcement_notification", False),
        escalation_contacts=format_escalation_contacts(org_profile),
    )

    user_prompt = user_template.format(
        incident_description=description,
        incident_type=classification.get("incident_type", "unknown"),
        severity=classification.get("severity", "medium"),
    )

    return system_prompt, user_prompt


def _is_demo_profile(profile: dict[str, Any]) -> bool:
    """Check if the org profile is a demo/placeholder profile."""
    if not profile:
        return True
    if profile.get("demo", False):
        return True
    # Also check if key fields are empty
    tech = profile.get("tech_stack", {})
    has_any_stack = any([
        tech.get("os"),
        tech.get("siem"),
        tech.get("edr"),
        tech.get("firewall"),
        tech.get("primary_database"),
    ])
    return not has_any_stack


def _ask_relevant_stack(
    incident_type: str,
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Ask the user for stack info relevant to the incident type.

    Args:
        incident_type: Classified incident type.
        classification: Full classification result.

    Returns:
        Minimal org profile with user-provided info.
    """
    import click

    click.echo("\n🔧 No organization profile configured. I need some context for the playbook.\n")

    profile: dict[str, Any] = {
        "org": {"name": "Your Organization", "industry": "unknown", "size": "unknown"},
        "tech_stack": {},
        "compliance": {},
        "teams": {},
        "channels": {},
    }

    # Ask for org name
    org_name = click.prompt("   Organization name", default="Your Organization", show_default=True)
    profile["org"]["name"] = org_name

    # Determine which fields are relevant based on incident type
    mitre_tactics = [t.lower() for t in classification.get("mitre_tactics", [])]

    # OS is almost always relevant
    os_input = click.prompt("   Operating systems (comma-separated)", default="windows", show_default=True)
    profile["tech_stack"]["os"] = [o.strip() for o in os_input.split(",")]

    # Incident-specific questions
    if incident_type in ("malware", "ransomware"):
        profile["tech_stack"]["edr"] = click.prompt("   EDR tool", default="", show_default=False)
        profile["tech_stack"]["siem"] = click.prompt("   SIEM platform", default="", show_default=False)
        profile["tech_stack"]["firewall"] = click.prompt("   Firewall vendor", default="", show_default=False)
    elif incident_type in ("phishing", "social_engineering"):
        profile["tech_stack"]["identity_provider"] = click.prompt("   Email/identity provider", default="", show_default=False)
        profile["tech_stack"]["siem"] = click.prompt("   SIEM platform", default="", show_default=False)
    elif incident_type in ("data_breach", "data_exfiltration"):
        profile["tech_stack"]["primary_database"] = click.prompt("   Primary database", default="", show_default=False)
        profile["tech_stack"]["siem"] = click.prompt("   SIEM platform", default="", show_default=False)
    elif incident_type in ("lateral_movement", "network_intrusion"):
        profile["tech_stack"]["firewall"] = click.prompt("   Firewall vendor", default="", show_default=False)
        profile["tech_stack"]["edr"] = click.prompt("   EDR tool", default="", show_default=False)
        profile["tech_stack"]["siem"] = click.prompt("   SIEM platform", default="", show_default=False)
    elif incident_type in ("ddos", "denial_of_service"):
        profile["tech_stack"]["firewall"] = click.prompt("   Firewall/CDN vendor", default="", show_default=False)
    elif "initial_access" in mitre_tactics:
        profile["tech_stack"]["edr"] = click.prompt("   EDR tool", default="", show_default=False)
        profile["tech_stack"]["identity_provider"] = click.prompt("   Identity provider", default="", show_default=False)
    else:
        # Generic — ask the basics
        profile["tech_stack"]["edr"] = click.prompt("   EDR tool (leave empty if none)", default="", show_default=False)
        profile["tech_stack"]["siem"] = click.prompt("   SIEM platform (leave empty if none)", default="", show_default=False)

    click.echo("")

    # Fill defaults for empty fields so the prompt doesn't break
    if not profile["tech_stack"].get("siem"):
        profile["tech_stack"]["siem"] = "Not specified"
    if not profile["tech_stack"].get("edr"):
        profile["tech_stack"]["edr"] = "Not specified"
    if not profile["tech_stack"].get("firewall"):
        profile["tech_stack"]["firewall"] = "Not specified"
    if not profile["tech_stack"].get("identity_provider"):
        profile["tech_stack"]["identity_provider"] = "Not specified"
    if not profile["tech_stack"].get("primary_database"):
        profile["tech_stack"]["primary_database"] = "Not specified"

    return profile


def generate_playbook(
    engine: InferenceEngine,
    description: str,
    severity: str | None = None,
    provider: str | None = None,
    interactive: bool = False,
) -> dict[str, Any]:
    """Generate a complete incident response playbook.

    This is the main orchestration function that:
    1. Classifies the incident
    2. Infers severity if not provided
    3. Loads or asks for org profile
    4. Generates the full playbook
    5. Adds metadata and disclaimer

    Args:
        engine: The inference engine to use.
        description: Sanitized incident description.
        severity: Optional user-specified severity.
        provider: Optional provider override.
        interactive: Whether we're in interactive mode (allows prompting).

    Returns:
        Complete playbook result dict.
    """
    # Load org profile
    org_profile = get_org_profile()
    is_demo = _is_demo_profile(org_profile)

    if not org_profile:
        logger.warning("No org profile found, using minimal defaults")
        org_profile = {"org": {"name": "Unknown", "industry": "unknown", "size": "unknown"}}

    # Step 1: Classify the incident
    logger.info("Classifying incident...")
    classification = classify_incident(
        engine,
        description,
        user_severity=severity,
    )

    # Step 2: If no user severity and classification didn't determine it,
    # use dedicated severity inference
    if not severity and classification.get("confidence", 0) < 0.5:
        logger.info("Low classification confidence, running dedicated severity inference")
        sev_result = infer_severity(engine, description)
        if sev_result.get("severity"):
            classification["severity"] = sev_result["severity"]
            classification["severity_reasoning"] = sev_result.get("reasoning", "")

    # Step 3: If demo/empty profile and interactive mode, ask relevant questions
    if is_demo and interactive:
        logger.info("Demo profile detected in interactive mode, asking user for stack info")
        org_profile = _ask_relevant_stack(
            classification.get("incident_type", "unknown"),
            classification,
        )
    elif is_demo:
        logger.info("Demo/empty profile detected — playbook will use generic commands")
        # Don't use ACME demo data — use a clearly generic profile
        org_profile = {
            "org": {"name": "[Your Organization]", "industry": "unknown", "size": "unknown"},
            "tech_stack": {
                "os": org_profile.get("tech_stack", {}).get("os", ["unknown"]),
                "siem": "Not configured",
                "edr": "Not configured",
                "firewall": "Not configured",
                "identity_provider": "Not configured",
                "primary_database": "Not configured",
            },
            "compliance": {"frameworks": [], "data_breach_notification_hours": 72},
            "teams": {},
            "channels": {},
        }

    # Step 4: Build prompts
    system_prompt, user_prompt = build_playbook_prompt(
        description, classification, org_profile
    )

    # Step 5: Generate playbook
    logger.info("Generating playbook...")
    result = engine.generate(
        system_prompt,
        user_prompt,
        provider=provider,
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result["error"],
            "classification": classification,
        }

    # Step 6: Add metadata
    playbook_text = result["text"]
    playbook_with_meta = _add_metadata(
        playbook_text,
        description,
        classification,
        org_profile,
        result.get("provider_used"),
    )

    return {
        "success": True,
        "playbook": playbook_with_meta,
        "classification": classification,
        "provider_used": result.get("provider_used"),
        "org_profile_used": org_profile.get("org", {}).get("name", "Unknown"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _add_metadata(
    playbook: str,
    description: str,
    classification: dict[str, Any],
    org_profile: dict[str, Any],
    provider_used: str | None,
) -> str:
    """Add metadata header and disclaimer to the playbook.

    Args:
        playbook: The generated playbook text.
        description: Original incident description (truncated for display).
        classification: Classification results.
        org_profile: Organization profile.
        provider_used: Name of the LLM provider used.

    Returns:
        Playbook with metadata prepended.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    org_name = org_profile.get("org", {}).get("name", "Unknown Organization")
    incident_type = classification.get("incident_type", "unknown")
    severity = classification.get("severity", "unknown")
    tactics = ", ".join(classification.get("mitre_tactics", []))
    desc_preview = description[:200] + ("..." if len(description) > 200 else "")

    header = f"""# Incident Response Playbook

> **Generated:** {now}
> **Organization:** {org_name}
> **Incident Type:** {incident_type}
> **Severity:** {severity.upper()}
> **MITRE ATT&CK Tactics:** {tactics or 'Not determined'}
> **LLM Provider:** {provider_used or 'Unknown'}

## Incident Description

> {desc_preview}

---

"""

    disclaimer = """

---

## ⚠️ Disclaimer

This playbook was generated by an AI-powered incident response tool. It is intended
as a **starting point** for your incident response process and should be reviewed by
qualified security professionals before execution. The commands and procedures
suggested have not been validated against your specific environment.

**Do NOT execute any commands from this playbook without:**
1. Reviewing them in the context of your environment
2. Testing in a non-production environment first
3. Getting approval from your incident commander

*Generated by [Incident Response Playbook Generator](https://github.com/0xPdaff/incident-response-playbook-generator)*
"""

    return header + playbook + disclaimer
