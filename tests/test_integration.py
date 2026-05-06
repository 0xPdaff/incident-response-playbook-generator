"""Integration tests — end-to-end playbook generation flow."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.agent.chains.playbook_generator import (
    generate_playbook,
    build_playbook_prompt,
)
from src.guardrails.input_validation import validate_playbook_request
from src.inference.engine import InferenceEngine
from src.utils.output import render_markdown


MOCK_PLAYBOOK_RESPONSE = """# Incident Response Playbook: Ransomware

## Phase 1: Detection & Analysis

### Objective
Confirm the ransomware infection and determine scope.

### Actions
1. Isolate affected systems from the network
2. Collect and preserve evidence
3. Identify the ransomware variant

### Commands
```bash
# Check for encryption activity
find / -name "*.locked" -mtime -1 | head -20

# Network connections from affected host
netstat -antp | grep ESTABLISHED
```

### Timeline
- Immediate: 0-2 hours

### Escalation Triggers
- Multiple systems affected → Escalate to Incident Commander

## Phase 2: Containment

### Objective
Stop the spread of ransomware.

### Actions
1. Disconnect affected systems from network
2. Disable SMB sharing
3. Block known C2 IPs at firewall

## Phase 3: Eradication

### Objective
Remove the ransomware from all systems.

## Phase 4: Recovery

### Objective
Restore systems from clean backups.

## Phase 5: Lessons Learned

### Objective
Improve defenses based on findings.
"""


class TestEndToEndPlaybookGeneration:
    """Integration tests for the full playbook generation pipeline."""

    @patch.object(InferenceEngine, "generate")
    def test_full_pipeline_with_mock(self, mock_generate, sample_incident_description):
        """Test the complete pipeline from input to output with mocked LLM."""
        # Mock the two LLM calls: classification and playbook generation
        mock_generate.side_effect = [
            # First call: classification
            {
                "text": '{"incident_type": "malware", "severity": "critical", '
                         '"mitre_tactics": ["Execution", "Impact"], '
                         '"mitre_techniques": ["T1059"], '
                         '"affected_assets_estimate": "Finance servers", '
                         '"confidence": 0.9}',
                "provider_used": "openai",
                "success": True,
                "error": None,
            },
            # Second call: playbook generation (or severity inference)
            {
                "text": MOCK_PLAYBOOK_RESPONSE,
                "provider_used": "openai",
                "success": True,
                "error": None,
            },
        ]

        # Validate input
        validation = validate_playbook_request(
            description=sample_incident_description,
            severity="critical",
        )
        assert validation.is_valid is True

        # Generate playbook
        engine = InferenceEngine()
        result = generate_playbook(
            engine=engine,
            description=validation.sanitized_description,
            severity=validation.severity,
        )

        assert result["success"] is True
        assert result["playbook"] is not None
        assert len(result["playbook"]) > 100
        assert result["provider_used"] == "openai"

    @patch.object(InferenceEngine, "generate")
    def test_playbook_includes_nist_phases(self, mock_generate, sample_incident_description):
        """Generated playbook includes all 5 NIST phases."""
        mock_generate.side_effect = [
            {
                "text": '{"incident_type": "malware", "severity": "high", '
                         '"mitre_tactics": [], "mitre_techniques": [], '
                         '"affected_assets_estimate": "Unknown", "confidence": 0.8}',
                "provider_used": "openai",
                "success": True,
                "error": None,
            },
            {
                "text": MOCK_PLAYBOOK_RESPONSE,
                "provider_used": "openai",
                "success": True,
                "error": None,
            },
        ]

        engine = InferenceEngine()
        result = generate_playbook(
            engine=engine,
            description=sample_incident_description,
        )

        assert result["success"] is True
        playbook = result["playbook"]

        # Check all 5 NIST phases are present
        assert "Detection" in playbook
        assert "Containment" in playbook
        assert "Eradication" in playbook
        assert "Recovery" in playbook
        assert "Lessons Learned" in playbook

    @patch.object(InferenceEngine, "generate")
    def test_playbook_includes_metadata(self, mock_generate, sample_incident_description):
        """Generated playbook includes metadata header."""
        mock_generate.side_effect = [
            {
                "text": '{"incident_type": "malware", "severity": "critical", '
                         '"mitre_tactics": ["Impact"], "mitre_techniques": [], '
                         '"affected_assets_estimate": "Servers", "confidence": 0.9}',
                "provider_used": "anthropic",
                "success": True,
                "error": None,
            },
            {
                "text": "## Phase 1: Detection",
                "provider_used": "anthropic",
                "success": True,
                "error": None,
            },
        ]

        engine = InferenceEngine()
        result = generate_playbook(
            engine=engine,
            description=sample_incident_description,
            severity="critical",
        )

        assert result["success"] is True
        assert "Generated:" in result["playbook"]
        assert "malware" in result["playbook"]
        assert "CRITICAL" in result["playbook"]
        assert "Disclaimer" in result["playbook"]

    def test_playbook_includes_severity_override(self, sample_incident_description):
        """User-specified severity is respected in the result."""
        with patch.object(InferenceEngine, "generate") as mock_generate:
            mock_generate.side_effect = [
                {
                    "text": '{"incident_type": "malware", "severity": "low", '
                             '"mitre_tactics": [], "mitre_techniques": [], '
                             '"affected_assets_estimate": "Unknown", "confidence": 0.5}',
                    "provider_used": "openai",
                    "success": True,
                    "error": None,
                },
                {
                    "text": "## Playbook content here",
                    "provider_used": "openai",
                    "success": True,
                    "error": None,
                },
            ]

            engine = InferenceEngine()
            result = generate_playbook(
                engine=engine,
                description=sample_incident_description,
                severity="high",  # Override
            )

            # User severity should override the LLM-inferred one
            assert result["classification"]["severity"] == "high"


class TestMarkdownOutput:
    """Tests for Markdown file output."""

    def test_render_markdown(self):
        """Playbook is saved as a valid Markdown file."""
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_markdown(
                "# Test Playbook\n\nContent here.",
                "test_incident",
                output_dir=tmpdir,
            )
            assert path.exists()
            assert path.suffix == ".md"
            content = path.read_text()
            assert "Test Playbook" in content

    def test_render_creates_directory(self):
        """Output directory is created if it doesn't exist."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "nested" / "dir"
            path = render_markdown(
                "# Test",
                "test",
                output_dir=str(new_dir),
            )
            assert path.exists()


class TestFallbackBehavior:
    """Tests for provider fallback behavior."""

    def test_no_provider_available(self):
        """When no provider is available, a helpful error is returned."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure no API keys
            for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]:
                os.environ.pop(key, None)

            engine = InferenceEngine()
            result = engine.generate("system", "user")

            assert result["success"] is False
            assert "API key" in result["error"] or "provider" in result["error"].lower()


class TestAPIModels:
    """Tests for API request/response models."""

    def test_valid_request(self):
        from src.api.models import PlaybookRequest

        req = PlaybookRequest(
            incident_description="Ransomware detected on server with .locked extension.",
        )
        assert req.severity is None
        assert req.provider is None

    def test_request_with_severity(self):
        from src.api.models import PlaybookRequest

        req = PlaybookRequest(
            incident_description="A" * 100,
            severity="critical",
        )
        assert req.severity == "critical"

    def test_invalid_severity(self):
        from src.api.models import PlaybookRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlaybookRequest(
                incident_description="A" * 100,
                severity="extreme",
            )

    def test_short_description_rejected(self):
        from src.api.models import PlaybookRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlaybookRequest(incident_description="short")
