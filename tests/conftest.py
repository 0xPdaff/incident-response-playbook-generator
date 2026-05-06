"""Test configuration and shared fixtures."""

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_incident_description():
    """Sample incident description for testing."""
    return (
        "We detected ransomware on the finance server. Files are being encrypted "
        "with a .locked extension. The infection started from a phishing email "
        "received by an employee in the accounting department."
    )


@pytest.fixture
def sample_phishing_description():
    """Sample phishing incident description."""
    return (
        "Multiple employees reported receiving suspicious emails claiming to be "
        "from the IT department, asking them to reset their passwords via a "
        "fake portal at password-reset.acme-security.com. Three employees "
        "reportedly clicked the link and entered their credentials."
    )


@pytest.fixture
def sample_org_profile():
    """Sample organization profile for testing."""
    return {
        "org": {
            "name": "Test Corp",
            "industry": "technology",
            "size": "medium",
        },
        "tech_stack": {
            "os": ["linux", "windows"],
            "cloud_providers": ["aws"],
            "primary_database": "postgresql",
            "siem": "splunk",
            "edr": "crowdstrike",
            "firewall": "palo-alto",
            "identity_provider": "okta",
        },
        "teams": {
            "soc": {"contact": "soc@test.com", "escalation_threshold": "medium"},
            "legal": {"contact": "legal@test.com", "escalation_threshold": "critical"},
        },
        "compliance": {
            "frameworks": ["NIST CSF"],
            "data_breach_notification_hours": 72,
            "requires_law_enforcement_notification": True,
        },
    }
