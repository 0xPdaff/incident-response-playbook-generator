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


def generate_playbook(
    engine: InferenceEngine,
    description: str,
    severity: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Generate a complete incident response playbook.

    This is the main orchestration function that:
    1. Classifies the incident
    2. Infers severity if not provided
    3. Generates the full playbook
    4. Adds metadata and disclaimer

    Args:
        engine: The inference engine to use.
        description: Sanitized incident description.
        severity: Optional user-specified severity.
        provider: Optional provider override.

    Returns:
        Complete playbook result dict.
    """
    # Load org profile
    org_profile = get_org_profile()
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

    # Step 3: Build prompts
    system_prompt, user_prompt = build_playbook_prompt(
        description, classification, org_profile
    )

    # Step 4: Generate playbook
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

    # Step 5: Add metadata
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

*Generated by [Incident Response Playbook Generator](https://github.com/0xPdaff/01-incident-response-playbook)*
"""

    return header + playbook + disclaimer
