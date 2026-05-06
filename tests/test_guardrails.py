"""Unit tests for input validation guardrails."""

import pytest

from src.guardrails.input_validation import (
    detect_pii,
    sanitize_input,
    validate_playbook_request,
    check_destructive_commands,
)


class TestValidateDescription:
    """Tests for incident description validation."""

    def test_valid_description(self, sample_incident_description):
        """Given a valid description, validation passes."""
        result = validate_playbook_request(sample_incident_description)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.sanitized_description == sample_incident_description

    def test_empty_description(self):
        """Given an empty description, validation fails."""
        result = validate_playbook_request("")
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "empty" in result.errors[0].lower() or "short" in result.errors[0].lower()

    def test_whitespace_only_description(self):
        """Given whitespace-only description, validation fails."""
        result = validate_playbook_request("   \n\t  ")
        assert result.is_valid is False

    def test_too_short_description(self):
        """Given description under minimum length, validation fails."""
        result = validate_playbook_request("Too short")
        assert result.is_valid is False
        assert "short" in result.errors[0].lower()

    def test_exact_minimum_length(self):
        """Given description at exactly minimum length, validation passes."""
        desc = "A" * 10  # MIN_DESCRIPTION_LENGTH = 10
        result = validate_playbook_request(desc)
        assert result.is_valid is True

    def test_very_long_description(self):
        """Given description over max length, it gets truncated."""
        desc = "A" * 15000
        result = validate_playbook_request(desc)
        assert result.is_valid is True
        assert len(result.sanitized_description) <= 10000


class TestValidateSeverity:
    """Tests for severity validation."""

    def test_valid_severity_levels(self, sample_incident_description):
        """All valid severity levels pass validation."""
        for severity in ["low", "medium", "high", "critical"]:
            result = validate_playbook_request(
                sample_incident_description, severity=severity
            )
            assert result.is_valid is True
            assert result.severity == severity

    def test_invalid_severity(self, sample_incident_description):
        """Invalid severity fails validation."""
        result = validate_playbook_request(
            sample_incident_description, severity="extreme"
        )
        assert result.is_valid is False

    def test_no_severity(self, sample_incident_description):
        """No severity passes validation (will be inferred)."""
        result = validate_playbook_request(sample_incident_description)
        assert result.is_valid is True
        assert result.severity is None

    def test_severity_case_insensitive(self, sample_incident_description):
        """Severity is normalized to lowercase."""
        result = validate_playbook_request(
            sample_incident_description, severity="CRITICAL"
        )
        assert result.is_valid is True
        assert result.severity == "critical"


class TestValidateProvider:
    """Tests for provider validation."""

    def test_valid_provider(self, sample_incident_description):
        """Valid provider passes validation."""
        for provider in ["openai", "anthropic", "deepseek", "ollama"]:
            result = validate_playbook_request(
                sample_incident_description, provider=provider
            )
            assert result.is_valid is True
            assert result.provider == provider

    def test_invalid_provider(self, sample_incident_description):
        """Invalid provider gets a warning but doesn't fail."""
        result = validate_playbook_request(
            sample_incident_description, provider="nonexistent"
        )
        assert result.provider is None
        assert len(result.warnings) > 0


class TestSanitizeInput:
    """Tests for input sanitization."""

    def test_strip_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert sanitize_input("  hello  ") == "hello"

    def test_null_bytes_removed(self):
        """Null bytes are removed."""
        assert sanitize_input("hello\x00world") == "helloworld"

    def test_line_endings_normalized(self):
        """CRLF is normalized to LF."""
        assert sanitize_input("line1\r\nline2") == "line1\nline2"

    def test_empty_input(self):
        """Empty string returns empty string."""
        assert sanitize_input("") == ""

    def test_truncation(self):
        """Long input is truncated."""
        long_text = "A" * 15000
        result = sanitize_input(long_text)
        assert len(result) <= 10000


class TestDetectPII:
    """Tests for PII detection."""

    def test_detect_email(self):
        """Email addresses are detected as potential PII."""
        text = "Contact john.doe@company.com for details"
        warnings = detect_pii(text)
        assert any("Email" in w for w in warnings)

    def test_detect_phone(self):
        """Phone numbers are detected as potential PII."""
        text = "Call 555-123-4567 for support"
        warnings = detect_pii(text)
        assert any("Phone" in w for w in warnings)

    def test_no_pii(self):
        """Clean text produces no PII warnings."""
        text = "The server was compromised via SMB exploit"
        warnings = detect_pii(text)
        assert len(warnings) == 0


class TestDestructiveCommandCheck:
    """Tests for destructive command detection."""

    def test_detect_rm_rf(self):
        """rm -rf / commands are flagged."""
        text = "Run `rm -rf /` to clean up"
        warnings = check_destructive_commands(text)
        assert len(warnings) > 0

    def test_safe_commands_pass(self):
        """Safe commands are not flagged."""
        text = "Run `ls -la /var/log` to check logs"
        warnings = check_destructive_commands(text)
        assert len(warnings) == 0

    def test_destructive_with_warning_passes(self):
        """Destructive commands with warning marker are not flagged."""
        text = "⚠️ WARNING: Do NOT run `rm -rf /` on production"
        warnings = check_destructive_commands(text)
        assert len(warnings) == 0
