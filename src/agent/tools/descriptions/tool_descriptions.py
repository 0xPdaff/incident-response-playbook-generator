"""Tool descriptions optimized for LLM consumption."""

INCIDENT_CLASSIFIER_DESCRIPTION = """Classify a cybersecurity incident into a category and severity level.

Use this tool when you receive an incident description and need to determine:
- The type of incident (malware, phishing, unauthorized access, etc.)
- The severity level (low, medium, high, critical)
- Relevant MITRE ATT&CK tactics and techniques
- Estimated affected assets

The tool uses the NIST incident categorization framework and maps to MITRE ATT&CK."""

PLAYBOOK_GENERATOR_DESCRIPTION = """Generate a complete incident response playbook.

Use this tool to create a structured, actionable playbook following NIST SP 800-61
with all 5 phases:
1. Detection & Analysis — Identify scope, confirm the incident, assess impact
2. Containment — Stop the bleeding, isolate affected systems
3. Eradication — Remove the threat, clean systems
4. Recovery — Restore services, verify integrity
5. Lessons Learned — Post-incident review, improve defenses

The playbook includes:
- Step-by-step actions for each phase
- Executable commands (bash/PowerShell/SQL based on org tech stack)
- Estimated timelines
- Escalation triggers
- Contact information

IMPORTANT: This tool generates documentation only. It does NOT execute any commands."""

SEVERITY_INFERRER_DESCRIPTION = """Infer the severity of a security incident.

Use when the user has not specified a severity level and one needs to be determined.

Severity criteria:
- CRITICAL: Active ransomware, confirmed data exfiltration, multiple systems down,
  public-facing impact, regulatory notification required
- HIGH: Significant threat, sensitive data at risk, multiple users affected
- MEDIUM: Contained threat, limited blast radius, non-sensitive data
- LOW: Minor incident, fully contained, informational"""

ALL_DESCRIPTIONS = {
    "classify_incident": INCIDENT_CLASSIFIER_DESCRIPTION,
    "generate_playbook": PLAYBOOK_GENERATOR_DESCRIPTION,
    "infer_severity": SEVERITY_INFERRER_DESCRIPTION,
}
