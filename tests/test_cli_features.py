"""Tests for CLI features added after initial specs.

Covers:
- --version flag
- --list-providers output
- --show-stack output (with and without profile)
- _is_demo_profile() function
- _ask_relevant_stack() function (mocked click.prompt)
- Extended help output (-H / --extended-help)
- pyproject.toml correctness
- --setup-stack wizard (basic validation)
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

# Add project root to path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.app import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    """Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_model_config():
    """Sample model_config.yaml content for testing."""
    return {
        "enabled": True,
        "default_provider": "openai",
        "providers": {
            "openai": {
                "model": "gpt-4o",
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 60,
            },
            "anthropic": {
                "model": "claude-sonnet-4",
                "api_base": "https://api.anthropic.com",
                "api_key_env": "ANTHROPIC_API_KEY",
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 60,
            },
            "deepseek": {
                "model": "deepseek-chat",
                "api_base": "https://api.deepseek.com",
                "api_key_env": "DEEPSEEK_API_KEY",
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 60,
            },
            "ollama": {
                "model": "llama3",
                "api_base": "http://localhost:11434",
                "api_key_env": "",
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 120,
            },
        },
        "fallback_chain": ["openai", "anthropic", "deepseek", "ollama"],
        "retry": {"max_retries": 3, "backoff_factor": 2},
    }


@pytest.fixture
def sample_active_profile():
    """A fully configured org profile with demo: false."""
    return {
        "demo": False,
        "org": {
            "name": "Test Corp",
            "industry": "technology",
            "size": "medium",
            "region": "north-america",
        },
        "tech_stack": {
            "os": ["linux", "windows"],
            "cloud_providers": ["aws"],
            "primary_database": "postgresql",
            "container_platform": "kubernetes",
            "siem": "splunk",
            "edr": "crowdstrike",
            "firewall": "palo-alto",
            "identity_provider": "okta",
        },
        "teams": {
            "soc": {"contact": "soc@test.com", "escalation_threshold": "medium"},
            "incident_commander": {"contact": "ic@test.com", "escalation_threshold": "high"},
            "legal": {"contact": "legal@test.com", "escalation_threshold": "critical"},
            "executive": {"contact": "ciso@test.com", "escalation_threshold": "critical"},
            "communications": {"contact": "comms@test.com", "escalation_threshold": "high"},
        },
        "compliance": {
            "frameworks": ["NIST CSF", "SOC 2"],
            "data_breach_notification_hours": 72,
            "requires_law_enforcement_notification": True,
        },
        "channels": {
            "primary": "slack",
            "incident_channel": "#incident-response",
            "bridge_number": "+1-555-0199",
        },
    }


@pytest.fixture
def sample_demo_profile():
    """A demo profile with demo: true."""
    return {
        "demo": True,
        "org": {
            "name": "ACME Corp",
            "industry": "technology",
            "size": "medium",
            "region": "north-america",
        },
        "tech_stack": {
            "os": ["linux", "windows"],
            "cloud_providers": ["aws", "azure"],
            "primary_database": "postgresql",
            "container_platform": "kubernetes",
            "siem": "splunk",
            "edr": "crowdstrike",
            "firewall": "palo-alto",
            "identity_provider": "okta",
        },
        "teams": {
            "soc": {"contact": "soc@acme.com", "escalation_threshold": "medium"},
            "incident_commander": {"contact": "ic@acme.com", "escalation_threshold": "high"},
            "legal": {"contact": "legal@acme.com", "escalation_threshold": "critical"},
            "executive": {"contact": "ciso@acme.com", "escalation_threshold": "critical"},
            "communications": {"contact": "comms@acme.com", "escalation_threshold": "high"},
        },
        "compliance": {
            "frameworks": ["NIST CSF", "SOC 2", "GDPR"],
            "data_breach_notification_hours": 72,
            "requires_law_enforcement_notification": True,
        },
        "channels": {
            "primary": "slack",
            "incident_channel": "#incident-response",
            "bridge_number": "+1-555-0199",
        },
    }


# ---------------------------------------------------------------------------
# Version Flag Tests
# ---------------------------------------------------------------------------

class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_output(self, runner):
        """--version prints version string and exits."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "ir-playbook" in result.output
        assert "version" in result.output.lower()

    def test_version_contains_actual_version(self, runner):
        """Version matches the package version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        import re
        assert re.search(r"\d+\.\d+\.\d+", result.output)

    def test_version_exits_without_generation(self, runner):
        """--version does not trigger playbook generation."""
        result = runner.invoke(main, ["--version", "-d", "ransomware test"])
        assert result.exit_code == 0
        assert "Generating" not in result.output
        assert "Processing" not in result.output


# ---------------------------------------------------------------------------
# List Providers Tests
# ---------------------------------------------------------------------------

class TestListProviders:
    """Tests for --list-providers flag."""

    def test_list_providers_shows_table(self, runner, mock_model_config):
        """--list-providers displays a provider status table."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers"])
        assert result.exit_code == 0
        assert "Provider" in result.output
        assert "Model" in result.output
        assert "Key Status" in result.output

    def test_list_providers_shows_all_providers(self, runner, mock_model_config):
        """All configured providers appear in the table."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers"])
        assert "openai" in result.output
        assert "anthropic" in result.output
        assert "deepseek" in result.output
        assert "ollama" in result.output

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-12345"})
    def test_list_providers_shows_key_status(self, runner, mock_model_config):
        """Configured API keys show check/cross marks."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers"])
        # Either ✓ or ✗ should appear (some keys set, some not)
        assert "✓" in result.output or "✗" in result.output

    def test_list_providers_shows_ollama_as_local(self, runner, mock_model_config):
        """Ollama shows N/A for key status and Yes for local."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers"])
        assert "N/A" in result.output
        assert "Yes" in result.output

    def test_list_providers_shows_fallback_chain(self, runner, mock_model_config):
        """Fallback chain is displayed."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers"])
        assert "Fallback" in result.output or "fallback" in result.output.lower()

    def test_list_providers_does_not_generate(self, runner, mock_model_config):
        """--list-providers does not trigger playbook generation."""
        with patch("src.utils.config.get_model_config", return_value=mock_model_config):
            result = runner.invoke(main, ["--list-providers", "-d", "incident test"])
        assert "Generating" not in result.output
        assert "Processing" not in result.output


# ---------------------------------------------------------------------------
# Show Stack Tests
# ---------------------------------------------------------------------------

class TestShowStack:
    """Tests for --show-stack flag."""

    def test_show_stack_with_active_profile(self, runner, sample_active_profile):
        """--show-stack displays full org profile when configured."""
        with patch("src.utils.config.get_org_profile", return_value=sample_active_profile):
            result = runner.invoke(main, ["--show-stack"])
        assert result.exit_code == 0
        assert "Test Corp" in result.output
        assert "Active" in result.output
        assert "splunk" in result.output
        assert "crowdstrike" in result.output

    def test_show_stack_with_demo_profile(self, runner, sample_demo_profile):
        """--show-stack identifies demo profiles."""
        with patch("src.utils.config.get_org_profile", return_value=sample_demo_profile):
            result = runner.invoke(main, ["--show-stack"])
        assert result.exit_code == 0
        assert "Demo" in result.output
        assert "ACME Corp" in result.output

    def test_show_stack_no_profile(self, runner):
        """--show-stack handles missing profile gracefully."""
        with patch("src.utils.config.get_org_profile", return_value={}):
            result = runner.invoke(main, ["--show-stack"])
        assert result.exit_code == 0
        assert "No organization profile" in result.output or "setup-stack" in result.output

    def test_show_stack_displays_compliance(self, runner, sample_active_profile):
        """--show-stack shows compliance frameworks."""
        with patch("src.utils.config.get_org_profile", return_value=sample_active_profile):
            result = runner.invoke(main, ["--show-stack"])
        assert "NIST CSF" in result.output
        assert "SOC 2" in result.output

    def test_show_stack_displays_escalation_contacts(self, runner, sample_active_profile):
        """--show-stack shows escalation contacts."""
        with patch("src.utils.config.get_org_profile", return_value=sample_active_profile):
            result = runner.invoke(main, ["--show-stack"])
        assert "soc@test.com" in result.output
        assert "ciso@test.com" in result.output

    def test_show_stack_displays_tech_stack_fields(self, runner, sample_active_profile):
        """--show-stack shows all tech stack fields."""
        with patch("src.utils.config.get_org_profile", return_value=sample_active_profile):
            result = runner.invoke(main, ["--show-stack"])
        assert "Operating Systems" in result.output or "linux" in result.output
        assert "Cloud Providers" in result.output or "aws" in result.output
        assert "SIEM" in result.output
        assert "EDR" in result.output
        assert "Firewall" in result.output
        assert "Identity Provider" in result.output


# ---------------------------------------------------------------------------
# Demo Profile Detection Tests
# ---------------------------------------------------------------------------

class TestIsDemoProfile:
    """Tests for _is_demo_profile() function."""

    def test_demo_flag_true(self):
        """Profile with demo: true is detected as demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        assert _is_demo_profile({"demo": True, "org": {"name": "ACME"}, "tech_stack": {"os": ["linux"]}}) is True

    def test_demo_flag_false_with_stack(self):
        """Profile with demo: false and valid stack is not demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        profile = {
            "demo": False,
            "org": {"name": "My Corp"},
            "tech_stack": {"os": ["linux"], "siem": "splunk"},
        }
        assert _is_demo_profile(profile) is False

    def test_empty_profile(self):
        """Empty dict is treated as demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        assert _is_demo_profile({}) is True

    def test_none_profile(self):
        """None is treated as demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        assert _is_demo_profile(None) is True

    def test_profile_with_empty_tech_stack(self):
        """Profile with empty tech stack is treated as demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        profile = {
            "demo": False,
            "org": {"name": "My Corp"},
            "tech_stack": {},
        }
        assert _is_demo_profile(profile) is True

    def test_profile_with_partial_stack(self):
        """Profile with some stack fields is not demo."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        profile = {
            "demo": False,
            "org": {"name": "My Corp"},
            "tech_stack": {"siem": "splunk"},
        }
        assert _is_demo_profile(profile) is False

    def test_demo_true_even_with_valid_stack(self):
        """Profile with demo: true is always demo regardless of stack."""
        from src.agent.chains.playbook_generator import _is_demo_profile
        profile = {
            "demo": True,
            "org": {"name": "My Corp"},
            "tech_stack": {"os": ["linux"], "siem": "splunk", "edr": "crowdstrike"},
        }
        assert _is_demo_profile(profile) is True


# ---------------------------------------------------------------------------
# Interactive Stack Questions Tests
# ---------------------------------------------------------------------------

class TestAskRelevantStack:
    """Tests for _ask_relevant_stack() function."""

    def test_malware_asks_edr_siem_firewall(self):
        """Malware incident type asks for EDR, SIEM, and firewall."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",       # org name
            "windows",        # OS
            "crowdstrike",    # EDR
            "splunk",         # SIEM
            "palo-alto",      # firewall
        ]):
            classification = {"mitre_tactics": ["Execution"]}
            result = _ask_relevant_stack("malware", classification)
        assert result["tech_stack"]["edr"] == "crowdstrike"
        assert result["tech_stack"]["siem"] == "splunk"
        assert result["tech_stack"]["firewall"] == "palo-alto"

    def test_phishing_asks_identity_provider(self):
        """Phishing incident asks for identity provider."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",       # org name
            "windows",        # OS
            "okta",           # identity provider
            "splunk",         # SIEM
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("phishing", classification)
        assert result["tech_stack"]["identity_provider"] == "okta"

    def test_ddos_asks_firewall_only(self):
        """DDoS incident asks for firewall/CDN only."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",       # org name
            "linux",          # OS
            "cloudflare",     # firewall/CDN
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("ddos", classification)
        assert result["tech_stack"]["firewall"] == "cloudflare"

    def test_empty_answers_get_default_values(self):
        """Empty answers are filled with 'Not specified'."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",  # org name
            "linux",     # OS
            "",          # EDR (empty)
            "",          # SIEM (empty)
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("unknown", classification)
        assert result["tech_stack"]["edr"] == "Not specified"
        assert result["tech_stack"]["siem"] == "Not specified"

    def test_returns_org_name(self):
        """Org name from prompt is included in result."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "My Company",  # org name
            "linux",       # OS
            "crowdstrike", # EDR
            "splunk",      # SIEM
            "palo-alto",   # firewall
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("malware", classification)
        assert result["org"]["name"] == "My Company"

    def test_os_parsed_from_comma_separated(self):
        """OS field is parsed from comma-separated input."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",              # org name
            "linux, windows, macos", # OS
            "crowdstrike",           # EDR
            "splunk",                # SIEM
            "palo-alto",             # firewall
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("malware", classification)
        assert result["tech_stack"]["os"] == ["linux", "windows", "macos"]

    def test_data_breach_asks_database_and_siem(self):
        """Data breach incident asks for primary database and SIEM."""
        from src.agent.chains.playbook_generator import _ask_relevant_stack

        with patch("click.prompt", side_effect=[
            "Test Org",       # org name
            "linux",          # OS
            "postgresql",     # primary database
            "splunk",         # SIEM
        ]):
            classification = {"mitre_tactics": []}
            result = _ask_relevant_stack("data_breach", classification)
        assert result["tech_stack"]["primary_database"] == "postgresql"


# ---------------------------------------------------------------------------
# Extended Help Tests
# ---------------------------------------------------------------------------

class TestExtendedHelp:
    """Tests for --extended-help / -H flag."""

    def test_extended_help_shows_guide(self, runner):
        """-H displays the extended usage guide."""
        result = runner.invoke(main, ["-H"])
        assert result.exit_code == 0
        assert "EXTENDED USAGE GUIDE" in result.output

    def test_extended_help_long_flag(self, runner):
        """--extended-help produces same output as -H."""
        result = runner.invoke(main, ["--extended-help"])
        assert result.exit_code == 0
        assert "EXTENDED USAGE GUIDE" in result.output

    def test_extended_help_includes_input_modes(self, runner):
        """Extended help describes all 4 input modes."""
        result = runner.invoke(main, ["-H"])
        assert "INPUT MODES" in result.output
        assert "CLI ARGUMENT" in result.output or "CLI Argument" in result.output
        assert "INTERACTIVE" in result.output or "Interactive" in result.output
        assert "FILE INPUT" in result.output or "File Input" in result.output
        assert "API SERVER" in result.output or "API Server" in result.output

    def test_extended_help_includes_all_flags(self, runner):
        """Extended help lists all CLI flags."""
        result = runner.invoke(main, ["-H"])
        assert "--description" in result.output
        assert "--interactive" in result.output
        assert "--serve" in result.output
        assert "--severity" in result.output
        assert "--provider" in result.output
        assert "--format" in result.output
        assert "--verbose" in result.output
        assert "--list-providers" in result.output
        assert "--show-stack" in result.output
        assert "--setup-stack" in result.output

    def test_extended_help_includes_providers(self, runner):
        """Extended help lists supported providers."""
        result = runner.invoke(main, ["-H"])
        assert "openai" in result.output.lower()
        assert "anthropic" in result.output.lower()
        assert "ollama" in result.output.lower()

    def test_extended_help_includes_examples(self, runner):
        """Extended help shows usage examples."""
        result = runner.invoke(main, ["-H"])
        assert "COMMON EXAMPLES" in result.output or "Examples" in result.output

    def test_extended_help_includes_troubleshooting(self, runner):
        """Extended help includes troubleshooting section."""
        result = runner.invoke(main, ["-H"])
        assert "TROUBLESHOOTING" in result.output

    def test_extended_help_includes_config_section(self, runner):
        """Extended help describes configuration files."""
        result = runner.invoke(main, ["-H"])
        assert "CONFIGURATION" in result.output
        assert ".env" in result.output

    def test_extended_help_includes_installed_mode(self, runner):
        """Extended help describes pip install / ir-playbook mode."""
        result = runner.invoke(main, ["-H"])
        assert "pip install" in result.output
        assert "ir-playbook" in result.output

    def test_extended_help_does_not_generate(self, runner):
        """-H does not trigger playbook generation."""
        result = runner.invoke(main, ["-H", "-d", "test incident"])
        assert "Processing" not in result.output
        assert "Generating" not in result.output


# ---------------------------------------------------------------------------
# pyproject.toml Tests
# ---------------------------------------------------------------------------

class TestPyprojectToml:
    """Tests for pyproject.toml correctness."""

    def test_pyproject_exists(self):
        """pyproject.toml exists in project root."""
        assert (PROJECT_ROOT / "pyproject.toml").exists()

    def test_entry_point_defined(self):
        """pyproject.toml defines the ir-playbook entry point."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert "ir-playbook" in content
        assert "src.app:main" in content

    def test_package_name(self):
        """Package name is ir-playbook."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert 'name = "ir-playbook"' in content

    def test_version_defined(self):
        """Version is defined in pyproject.toml."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        import re
        assert re.search(r'version\s*=\s*"\d+\.\d+\.\d+"', content)

    def test_dependencies_include_click(self):
        """Click is listed as a dependency."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert "click" in content

    def test_dependencies_include_litellm(self):
        """litellm is listed as a dependency."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert "litellm" in content

    def test_python_version_minimum(self):
        """Python version requirement is at least 3.11."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert ">=3.11" in content

    def test_setuptools_finds_src(self):
        """setuptools is configured to find src package."""
        with open(PROJECT_ROOT / "pyproject.toml") as f:
            content = f.read()
        assert "src" in content


# ---------------------------------------------------------------------------
# Setup Stack Wizard Tests
# ---------------------------------------------------------------------------

class TestSetupStack:
    """Tests for --setup-stack wizard."""

    def test_setup_stack_creates_profile(self, sample_active_profile, mock_model_config, tmp_path):
        """Setup wizard creates a valid profile file."""
        from src.app import _run_setup_stack

        with \
            patch("src.utils.config.get_org_profile", return_value=sample_active_profile), \
            patch("src.app.load_yaml_config", return_value={}), \
            patch("src.utils.config.get_model_config", return_value=mock_model_config), \
            patch("click.prompt", side_effect=[
                "overwrite",         # action choice
                "New Corp",          # org name
                "finance",           # industry
                "large",             # size
                "europe",            # region
                "linux",             # OS
                "aws",               # cloud
                "mysql",             # database
                "docker",            # container
                "elk",               # SIEM
                "sentinelone",       # EDR
                "fortinet",          # firewall
                "azure-ad",          # identity provider
                "PCI-DSS, ISO27001", # frameworks
                "48",                # breach hours
                "no",                # law enforcement
                "soc@new.com",       # SOC email
                "ic@new.com",        # IC email
                "legal@new.com",     # legal email
                "ciso@new.com",      # CISO email
                "comms@new.com",     # comms email
                "teams",             # primary channel
                "#incidents",        # incident channel
            ]), \
            patch("yaml.dump") as mock_yaml_dump, \
            patch("builtins.open", MagicMock()):

            _run_setup_stack()
            assert mock_yaml_dump.called

    def test_setup_stack_cancel(self, sample_active_profile, mock_model_config):
        """Choosing cancel in setup wizard exits without saving."""
        from src.app import _run_setup_stack

        with \
            patch("src.utils.config.get_org_profile", return_value=sample_active_profile), \
            patch("src.app.load_yaml_config", return_value={}), \
            patch("src.utils.config.get_model_config", return_value=mock_model_config), \
            patch("click.prompt", side_effect=["cancel"]), \
            patch("yaml.dump") as mock_yaml_dump:

            _run_setup_stack()
            # yaml.dump should NOT be called if cancelled
            assert not mock_yaml_dump.called


# ---------------------------------------------------------------------------
# Generic Profile Fallback Tests
# ---------------------------------------------------------------------------

class TestGenericProfileFallback:
    """Tests for generic profile fallback behavior."""

    def test_demo_profile_non_interactive_uses_generic(self):
        """In non-interactive mode, demo profile triggers generic fallback."""
        from src.agent.chains.playbook_generator import generate_playbook
        from src.inference.engine import InferenceEngine

        demo_profile = {
            "demo": True,
            "org": {"name": "ACME Corp"},
            "tech_stack": {"os": ["linux"], "siem": "splunk", "edr": "crowdstrike"},
        }

        with \
            patch("src.agent.chains.playbook_generator.get_org_profile", return_value=demo_profile), \
            patch("src.agent.chains.playbook_generator.classify_incident", return_value={
                "incident_type": "malware",
                "severity": "high",
                "confidence": 0.8,
                "mitre_tactics": ["Execution"],
                "mitre_techniques": ["T1059"],
            }), \
            patch.object(InferenceEngine, "generate", return_value={
                "text": "## Phase 1: Detection",
                "provider_used": "openai",
                "success": True,
                "error": None,
            }):

            engine = InferenceEngine()
            result = generate_playbook(
                engine=engine,
                description="Malware detected on workstation",
                interactive=False,
            )

            assert result["success"] is True
            # Should NOT use ACME-specific data
            assert "ACME" not in result.get("playbook", "")
