"""Unit tests for utility functions."""

import pytest

from src.utils.helpers import (
    validate_description,
    validate_severity,
    validate_provider,
    sanitize_filename,
    truncate_description,
    parse_llm_json,
    format_org_tech_stack,
    format_escalation_contacts,
    compute_cache_key,
)


class TestValidateDescription:
    """Tests for description validation helper."""

    def test_valid(self):
        is_valid, error = validate_description("A valid incident description here")
        assert is_valid is True
        assert error == ""

    def test_empty(self):
        is_valid, error = validate_description("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_whitespace(self):
        is_valid, error = validate_description("   ")
        assert is_valid is False

    def test_too_short(self):
        is_valid, error = validate_description("short")
        assert is_valid is False
        assert "short" in error.lower()


class TestValidateSeverity:
    """Tests for severity validation helper."""

    def test_valid_levels(self):
        for level in ["low", "medium", "high", "critical"]:
            is_valid, _ = validate_severity(level)
            assert is_valid is True

    def test_invalid(self):
        is_valid, error = validate_severity("extreme")
        assert is_valid is False

    def test_none(self):
        is_valid, _ = validate_severity(None)
        assert is_valid is True


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_simple(self):
        assert sanitize_filename("Malware Incident") == "malware_incident"

    def test_special_chars(self):
        result = sanitize_filename("SQL Injection (Critical!)")
        assert "!" not in result
        assert "(" not in result

    def test_long_name(self):
        result = sanitize_filename("A" * 100)
        assert len(result) <= 64


class TestTruncateDescription:
    """Tests for description truncation."""

    def test_short_text(self):
        text, truncated = truncate_description("Short description")
        assert truncated is False
        assert text == "Short description"

    def test_long_text(self):
        long_text = "A" * 15000
        text, truncated = truncate_description(long_text)
        assert truncated is True
        assert len(text) == 10000


class TestParseLLMJson:
    """Tests for LLM JSON parsing."""

    def test_clean_json(self):
        text = '{"key": "value", "num": 42}'
        result = parse_llm_json(text)
        assert result == {"key": "value", "num": 42}

    def test_json_with_markdown_fences(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'Here is the result:\n{"type": "malware"}\nEnd of result.'
        result = parse_llm_json(text)
        assert result.get("type") == "malware"

    def test_invalid_json(self):
        text = "This is not JSON at all"
        result = parse_llm_json(text)
        assert result == {}


class TestFormatOrgTechStack:
    """Tests for tech stack formatting."""

    def test_full_profile(self, sample_org_profile):
        result = format_org_tech_stack(sample_org_profile)
        assert "linux" in result
        assert "windows" in result
        assert "splunk" in result
        assert "crowdstrike" in result

    def test_empty_profile(self):
        result = format_org_tech_stack({})
        assert result == "Not configured"


class TestFormatEscalationContacts:
    """Tests for escalation contacts formatting."""

    def test_full_profile(self, sample_org_profile):
        result = format_escalation_contacts(sample_org_profile)
        assert "soc@test.com" in result
        assert "legal@test.com" in result

    def test_empty_profile(self):
        result = format_escalation_contacts({})
        assert "No escalation" in result


class TestComputeCacheKey:
    """Tests for cache key computation."""

    def test_deterministic(self):
        key1 = compute_cache_key("system", "user")
        key2 = compute_cache_key("system", "user")
        assert key1 == key2

    def test_different_inputs(self):
        key1 = compute_cache_key("system1", "user")
        key2 = compute_cache_key("system2", "user")
        assert key1 != key2

    def test_length(self):
        key = compute_cache_key("test")
        assert len(key) == 16
