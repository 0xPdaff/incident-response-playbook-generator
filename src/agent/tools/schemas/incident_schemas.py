"""JSON schemas for agent tools."""

INCIDENT_CLASSIFIER_SCHEMA = {
    "name": "classify_incident",
    "description": (
        "Classify a cybersecurity incident by type and severity based on "
        "the incident description."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "incident_description": {
                "type": "string",
                "description": "Free-text description of the security incident.",
            },
            "context": {
                "type": "object",
                "description": "Additional context (org profile, known IOCs, etc.).",
                "properties": {
                    "org_industry": {"type": "string"},
                    "affected_systems": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "known_iocs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "required": ["incident_description"],
    },
}

PLAYBOOK_GENERATOR_SCHEMA = {
    "name": "generate_playbook",
    "description": (
        "Generate a complete incident response playbook following NIST SP 800-61 "
        "with 5 phases: Detection, Containment, Eradication, Recovery, Lessons Learned."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "incident_type": {
                "type": "string",
                "enum": [
                    "malware", "phishing", "unauthorized_access",
                    "data_breach", "ddos", "insider_threat",
                    "supply_chain", "misconfiguration", "web_attack",
                    "physical", "unknown",
                ],
                "description": "Type of incident.",
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Incident severity level.",
            },
            "incident_description": {
                "type": "string",
                "description": "Description of the incident.",
            },
            "org_profile": {
                "type": "object",
                "description": "Organization profile with tech stack and contacts.",
            },
            "mitre_tactics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "MITRE ATT&CK tactics identified.",
            },
        },
        "required": ["incident_type", "severity", "incident_description"],
    },
}

SEVERITY_INFERRER_SCHEMA = {
    "name": "infer_severity",
    "description": (
        "Infer the severity level of a security incident from its description."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "incident_description": {
                "type": "string",
                "description": "Description of the incident.",
            },
        },
        "required": ["incident_description"],
    },
}

# All schemas for registration
ALL_SCHEMAS = [
    INCIDENT_CLASSIFIER_SCHEMA,
    PLAYBOOK_GENERATOR_SCHEMA,
    SEVERITY_INFERRER_SCHEMA,
]
