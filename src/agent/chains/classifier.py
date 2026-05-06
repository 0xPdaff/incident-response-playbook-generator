"""Incident classifier chain — classifies incident type and severity."""

import logging
from typing import Any

from src.inference.engine import InferenceEngine
from src.utils.config import get_prompts
from src.utils.helpers import parse_llm_json

logger = logging.getLogger(__name__)


def classify_incident(
    engine: InferenceEngine,
    description: str,
    user_severity: str | None = None,
) -> dict[str, Any]:
    """Classify an incident by type and severity.

    Args:
        engine: The inference engine to use.
        description: Incident description text.
        user_severity: User-specified severity (overrides inference).

    Returns:
        Classification dict with incident_type, severity, mitre_tactics, etc.
    """
    prompts = get_prompts()
    classification_prompts = prompts.get("classification", {})

    system_prompt = classification_prompts.get("system", "")
    user_prompt_template = classification_prompts.get("user", "")

    user_prompt = user_prompt_template.format(
        incident_description=description,
    )

    result = engine.generate(system_prompt, user_prompt)

    if not result["success"]:
        logger.warning("Classification LLM call failed: %s", result["error"])
        # Return sensible defaults
        return {
            "incident_type": "unknown",
            "severity": user_severity or "medium",
            "mitre_tactics": [],
            "mitre_techniques": [],
            "affected_assets_estimate": "Unknown",
            "confidence": 0.0,
            "classification_method": "fallback",
        }

    # Parse the LLM response
    parsed = parse_llm_json(result["text"])
    if not parsed:
        logger.warning("Failed to parse classification response")
        parsed = {
            "incident_type": "unknown",
            "severity": "medium",
            "mitre_tactics": [],
            "mitre_techniques": [],
            "affected_assets_estimate": "Unknown",
            "confidence": 0.0,
        }

    # Override severity if user specified it
    if user_severity:
        parsed["severity"] = user_severity

    parsed["classification_method"] = "llm"
    parsed["provider_used"] = result.get("provider_used")

    logger.info(
        "Incident classified: type=%s, severity=%s, confidence=%.2f",
        parsed.get("incident_type"),
        parsed.get("severity"),
        parsed.get("confidence", 0),
    )

    return parsed


def infer_severity(
    engine: InferenceEngine,
    description: str,
) -> dict[str, Any]:
    """Infer severity from incident description.

    Used when the user hasn't specified severity and we want a dedicated
    severity assessment instead of relying on the classification step.

    Args:
        engine: The inference engine to use.
        description: Incident description text.

    Returns:
        Severity assessment dict.
    """
    prompts = get_prompts()
    severity_prompts = prompts.get("severity_inference", {})

    system_prompt = severity_prompts.get("system", "")
    user_prompt_template = severity_prompts.get("user", "")

    user_prompt = user_prompt_template.format(
        incident_description=description,
    )

    result = engine.generate(system_prompt, user_prompt)

    if not result["success"]:
        return {
            "severity": "medium",
            "reasoning": "Failed to infer severity, using default.",
            "recommended_escalation": "soc",
            "urgency": "within_4h",
        }

    parsed = parse_llm_json(result["text"])
    if not parsed:
        return {
            "severity": "medium",
            "reasoning": "Could not parse severity assessment.",
            "recommended_escalation": "soc",
            "urgency": "within_4h",
        }

    return parsed
