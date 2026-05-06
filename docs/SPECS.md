# Specs: Incident Response Playbook Generator

## Functional Summary

An AI-powered agent that generates customized incident response playbooks for cybersecurity incidents. Given a free-text description of an incident, it produces a structured, actionable playbook following the 5 NIST phases: Detection → Containment → Eradication → Recovery → Lessons Learned. Each phase includes executable commands (bash, PowerShell, SQL depending on the org's tech stack), estimated timelines, and clear escalation criteria. The agent does NOT execute any real commands — it only generates documentation.

## Assumptions

1. Primary input is free-form text describing the incident
2. Organization profile lives in `config/org_profile.yaml` — read automatically; only ask for info relevant to the incident; if critical info is missing, prompt the user
3. Severity: user can specify it (low/medium/high/critical) or the agent infers it from the description
4. Playbook is structured in 5 NIST phases: Detection → Containment → Eradication → Recovery → Lessons Learned
5. Each phase includes executable commands (bash, PowerShell, SQL depending on stack)
6. Automated containment scripts are generated
7. Clear escalation criteria (leadership, legal, law enforcement)
8. Output in Markdown + optional PDF via WeasyPrint
9. Knowledge base: NIST SP 800-61 Rev. 3, SANS, MITRE ATT&CK — embedded, not real-time search
10. Agent does NOT execute real commands — only generates documentation
11. This is a playbook generator, not an incident management system
12. **Full multi-provider:** OpenAI, Anthropic, Deepseek, Minimax, Kimi, Qwen, GLM, Ollama local — with configurable fallback
13. API keys in `.env`, never hardcoded
14. 4 input modes: CLI argument, interactive CLI, REST API, file input
15. User can switch provider at runtime via CLI flag or API request body
16. **`--extended-help` / `-H`:** Shows a comprehensive usage guide with examples, provider table, config file explanations, and troubleshooting tips
17. **`--list-providers`:** Shows all supported providers with model names, API key status (✓/✗), and endpoint URLs
18. **`--show-stack`:** Displays the current organization profile, tech stack, compliance frameworks, and escalation contacts in formatted tables
19. **`--setup-stack`:** Interactive wizard that guides users through configuring their org profile (name, industry, size, tech stack, compliance, escalation contacts, channels); saved to `config/org_profile.yaml`
20. **`--version`:** Shows the package version (reads from `pyproject.toml` via `importlib.metadata`)
21. **Demo profile detection:** When `demo: true` in `org_profile.yaml`, the agent avoids treating demo data as real. In interactive mode it asks for relevant stack info; in non-interactive mode it generates generic playbooks
22. **Interactive stack questions:** In interactive mode with a demo/missing profile, the agent asks incident-type-specific questions (e.g., EDR/SIEM for malware, identity provider for phishing)
23. **CLI package installation:** `pip install .` installs the `ir-playbook` command globally via `pyproject.toml` entry point. Config files are stored in `~/.ir-playbook/config/` when running as installed package
24. **NIST SP 800-61 Rev. 3:** All references and playbook structure follow Rev. 3 (not Rev. 2)
25. **Anthropic SDK for compatible providers:** Providers with `api_type: anthropic` in model_config.yaml use the Anthropic Python SDK directly instead of litellm
26. **Generic profile fallback:** When no profile exists, the agent generates playbooks with generic commands instead of assuming any specific org (like ACME demo data)

## Happy Path

1. User provides incident description via one of 4 input modes
2. Agent loads org profile from `config/org_profile.yaml`
3. Agent classifies incident type and infers severity (or uses specified)
4. Agent generates structured playbook with 5 NIST phases
5. Each phase includes: description, commands, timeline, escalation criteria
6. Playbook rendered as Markdown (and optionally PDF)
7. Output saved to `data/processed/` with timestamp

## Sad Paths

- **No API key configured:** Clear error message listing required keys per provider
- **Invalid provider specified:** Falls back to default provider with warning
- **Empty incident description:** Rejects with validation error and example
- **Org profile missing:** Uses minimal defaults, warns user
- **LLM rate limit hit:** Retries with exponential backoff up to 3 times, then falls back to next provider
- **LLM returns malformed response:** Validates structure, retries once, then returns error with raw output
- **File input not found:** Clear file-not-found error with path guidance
- **API server port in use:** Reports port conflict with suggestion to use `--port`
- **PDF generation fails (WeasyPrint missing):** Falls back to Markdown-only with warning

## Validations

| Input | Validation | Error if Fails |
|-------|-----------|---------------|
| Incident description | Non-empty string, min 10 chars | `"Incident description too short. Provide at least 10 characters."` |
| Severity | One of: low, medium, high, critical | `"Invalid severity. Use: low, medium, high, critical"` |
| Provider | One of supported providers | `"Unsupported provider. Falling back to default."` |
| Org profile YAML | Valid YAML, required fields present | `"Invalid org profile. Using defaults."` |
| Output format | markdown or pdf | `"Unsupported format. Using markdown."` |
| API request body | Valid JSON with required fields | HTTP 422 with field-level errors |
| Setup stack inputs | Non-empty strings where required; breach hours must be numeric | Wizard prompts again with defaults |
| Setup stack action | One of: overwrite, edit, cancel | Prompt repeats on invalid input |

## Edge Cases

- Empty string input → validation error
- Very long incident description (>10000 chars) → truncated with warning
- Special characters in description → sanitized for shell command generation
- Concurrent API requests → handled by FastAPI async
- Missing optional config → sensible defaults applied
- Provider API key present but invalid → authentication error with provider-specific guidance

## BDD Scenarios

```gherkin
Feature: Incident Response Playbook Generation

  Scenario: Generate playbook from CLI argument
    Given the user provides an incident description as a CLI argument
    And the org profile is configured
    And a valid API key is set for the default provider
    When the agent runs
    Then a playbook is generated with all 5 NIST phases
    And the playbook is saved as a Markdown file
    And the file path is printed to stdout

  Scenario: Generate playbook interactively
    Given the user runs the CLI in interactive mode
    When the user is prompted for incident details
    And the user provides a valid description
    Then a playbook is generated and displayed

  Scenario: Generate playbook via API
    Given the API server is running
    And a valid API key is configured
    When a POST request is sent to /api/v1/playbook with a valid incident description
    Then the response contains the generated playbook
    And the HTTP status is 200

  Scenario: Generate playbook from file
    Given a file exists with an incident description
    And a valid API key is configured
    When the CLI is run with --file flag pointing to that file
    Then a playbook is generated from the file contents

  Scenario: Inferred severity
    Given the user does not specify severity
    And the incident description mentions "ransomware" and "all systems encrypted"
    When the playbook is generated
    Then the severity is set to "critical"
    And the playbook includes law enforcement escalation steps

  Scenario: Multi-provider fallback
    Given the primary provider is "openai"
    And the OpenAI API key is invalid
    And a valid Anthropic key is configured as fallback
    When the agent attempts generation
    Then it falls back to Anthropic
    And a warning is logged about the primary provider failure
    And the playbook is generated successfully

  Scenario: Provider switch at runtime via CLI
    Given the default provider is "openai"
    When the user runs the CLI with --provider anthropic
    Then Anthropic is used for this generation
    And the default provider is not changed

  Scenario: Provider switch at runtime via API
    Given the API server is running
    When a POST request includes "provider": "deepseek" in the body
    Then Deepseek is used for this request only

  Scenario: Empty incident description
    Given the user provides an empty string as incident description
    When the agent validates the input
    Then a validation error is returned
    And the error message includes an example valid description

  Scenario: Missing API key
    Given no API key is configured for any provider
    When the user attempts to generate a playbook
    Then a clear error lists which providers need which keys
    And the ENV variable names are shown

  Scenario: PDF output
    Given WeasyPrint is installed
    And the user specifies --format pdf
    When the playbook is generated
    Then both Markdown and PDF files are created

  Scenario: PDF fallback when WeasyPrint missing
    Given WeasyPrint is not installed
    And the user specifies --format pdf
    When the playbook is generated
    Then only Markdown is generated
    And a warning explains how to install WeasyPrint

  Scenario: Org profile auto-load
    Given config/org_profile.yaml exists with org tech stack
    When the playbook is generated
    Then commands are generated for the correct stack (e.g., PowerShell for Windows)

  Scenario: Missing org profile
    Given config/org_profile.yaml does not exist
    When the playbook is generated
    Then a minimal default profile is used
    And a warning is logged about the missing profile

  Scenario: Concurrent API requests
    Given the API server is running
    When multiple POST requests arrive simultaneously
    Then each request is processed independently
    And no race conditions occur in output files

  Scenario: Large incident description
    Given the incident description is over 10000 characters
    When the agent processes it
    Then the description is truncated to 10000 characters
    And a warning is logged about truncation
```

---

## Additional BDD Scenarios (post-initial specs)

The following scenarios cover features added after the initial spec was written.

```gherkin
Feature: Extended Help

  Scenario: Show extended help with -H flag
    Given the user runs "python src/app.py -H"
    Then the banner is displayed
    And an extended usage guide is printed
    And the guide includes sections for input modes, all flags, supported providers, common examples, configuration files, troubleshooting, and installed CLI mode

  Scenario: Show extended help with --extended-help flag
    Given the user runs "python src/app.py --extended-help"
    Then the output is identical to running with -H

  Scenario: Extended help shows all 8 providers
    Given the user runs "python src/app.py -H"
    Then the provider table lists openai, anthropic, deepseek, minimax, kimi, qwen, glm, and ollama
    And each provider shows its model name and API key env var

  Scenario: Extended help does not trigger playbook generation
    Given the user runs "python src/app.py -H -d 'ransomware detected'"
    Then only the extended help is shown
    And no playbook generation is attempted

Feature: List Providers

  Scenario: List providers with mixed API key status
    Given OPENAI_API_KEY is set in the environment
    And ANTHROPIC_API_KEY is not set
    When the user runs "python src/app.py --list-providers"
    Then the banner is displayed
    And a provider status table is printed
    And OpenAI shows "✓" for key status
    And Anthropic shows "✗" for key status
    And Ollama shows "N/A" for key status
    And the default provider is marked
    And the fallback chain is displayed

  Scenario: List providers shows model names and endpoints
    Given the user runs "python src/app.py --list-providers"
    Then each provider row shows the model name, key status, local flag, and endpoint URL

  Scenario: List providers does not trigger playbook generation
    Given the user runs "python src/app.py --list-providers -d 'incident'"
    Then only the provider status table is shown
    And no LLM calls are made

Feature: Show Organization Stack

  Scenario: Show existing demo profile
    Given config/org_profile.yaml exists with demo: true and org name "ACME Corp"
    When the user runs "python src/app.py --show-stack"
    Then the organization profile is displayed in formatted tables
    And the profile status shows "📋 Demo (replace with your real data)"
    And tech stack shows all configured values (OS, SIEM, EDR, etc.)
    And compliance frameworks are listed
    And escalation contacts are shown

  Scenario: Show active profile
    Given config/org_profile.yaml exists with demo: false
    When the user runs "python src/app.py --show-stack"
    Then the profile status shows "✅ Active"

  Scenario: Show when no profile exists
    Given config/org_profile.yaml does not exist
    When the user runs "python src/app.py --show-stack"
    Then a warning is shown: "No organization profile found"
    And a tip suggests running --setup-stack

  Scenario: Show stack does not print banner
    Given the user runs "python src/app.py --show-stack"
    Then no banner is printed before the profile display

Feature: Setup Organization Stack

  Scenario: Setup fresh profile (no existing)
    Given config/org_profile.yaml does not exist
    When the user runs "python src/app.py --setup-stack"
    Then the setup wizard starts
    And the user is prompted for org name, industry, size, and region
    And the user is prompted for tech stack (OS, cloud, database, SIEM, EDR, firewall, identity provider)
    And the user is prompted for compliance frameworks and breach notification hours
    And the user is prompted for escalation contacts (SOC, IC, legal, CISO, comms)
    And the user is prompted for communication channels
    And the profile is saved to config/org_profile.yaml with demo: false
    And a success message confirms the save

  Scenario: Edit existing profile
    Given config/org_profile.yaml exists with org name "My Company"
    When the user runs "python src/app.py --setup-stack"
    Then the wizard detects the existing profile
    And prompts the user to choose: overwrite, edit, or cancel
    When the user chooses "edit"
    Then existing values are used as defaults for prompts
    And the updated profile is saved

  Scenario: Overwrite existing profile
    Given config/org_profile.yaml exists
    When the user chooses "overwrite" in the setup wizard
    Then all prompts use example defaults
    And the new profile overwrites the old one

  Scenario: Cancel setup
    Given config/org_profile.yaml exists
    When the user chooses "cancel" in the setup wizard
    Then a cancellation message is shown
    And the existing profile is unchanged

  Scenario: Setup saves YAML with correct structure
    Given the user completes the setup wizard
    Then the saved YAML file is valid and parseable
    And it contains org, tech_stack, teams, compliance, and channels sections
    And demo is set to false
    And list fields (os, cloud_providers, frameworks) are parsed from comma-separated input
    And breach_notification_hours is stored as an integer

Feature: Version Flag

  Scenario: Show version
    Given the user runs "python src/app.py --version"
    Then the version string is displayed (e.g., "ir-playbook, version 1.0.0")
    And the program exits without error

  Scenario: Version matches pyproject.toml
    Given pyproject.toml defines version "1.0.0"
    When the user runs "python src/app.py --version"
    Then the output contains "1.0.0"

Feature: Demo Profile Detection

  Scenario: Profile with demo: true is detected as demo
    Given config/org_profile.yaml has demo: true
    When the playbook generator checks the profile
    Then _is_demo_profile() returns True
    And demo data is not used as real organization context

  Scenario: Profile with demo: false is not demo
    Given config/org_profile.yaml has demo: false and valid tech_stack
    When the playbook generator checks the profile
    Then _is_demo_profile() returns False
    And the profile is used as-is for playbook generation

  Scenario: Empty profile is treated as demo
    Given config/org_profile.yaml does not exist
    When the playbook generator checks the profile
    Then _is_demo_profile() returns True

  Scenario: Profile with no tech stack is treated as demo
    Given config/org_profile.yaml exists but has empty tech_stack
    When the playbook generator checks the profile
    Then _is_demo_profile() returns True

Feature: Interactive Stack Questions

  Scenario: Malware incident asks for EDR, SIEM, firewall
    Given the user is in interactive mode with a demo profile
    And the classified incident type is "malware"
    When _ask_relevant_stack() is called
    Then the user is prompted for EDR tool, SIEM platform, and firewall vendor

  Scenario: Phishing incident asks for identity provider
    Given the user is in interactive mode with a demo profile
    And the classified incident type is "phishing"
    When _ask_relevant_stack() is called
    Then the user is prompted for email/identity provider and SIEM platform

  Scenario: DDoS incident asks for firewall/CDN
    Given the user is in interactive mode with a demo profile
    And the classified incident type is "ddos"
    When _ask_relevant_stack() is called
    Then the user is prompted for firewall/CDN vendor only

  Scenario: Generic incident asks for basic tools
    Given the user is in interactive mode with a demo profile
    And the classified incident type is "unknown"
    When _ask_relevant_stack() is called
    Then the user is prompted for EDR and SIEM with optional defaults

  Scenario: Empty answers are filled with "Not specified" defaults
    Given the user leaves EDR prompt empty
    When _ask_relevant_stack() builds the profile
    Then the EDR field is set to "Not specified"
    And the playbook generation proceeds without error

Feature: CLI Package Installation

  Scenario: Use ir-playbook after pip install
    Given the project is installed with "pip install ."
    When the user runs "ir-playbook --version"
    Then the version is displayed successfully

  Scenario: Falls back to ~/.ir-playbook/ for config
    Given the project is installed as a package
    And the user runs "ir-playbook" from any directory
    Then config files are read from ~/.ir-playbook/config/
    And if no config exists, defaults are copied from package data on first run

  Scenario: pyproject.toml defines correct entry point
    Given pyproject.toml exists
    Then it contains [project.scripts] with "ir-playbook = src.app:main"
    And the package name is "ir-playbook"
    And it lists all required dependencies

  Scenario: Installed mode creates data directories
    Given the project is installed as a package
    And ~/.ir-playbook/ does not exist
    When the application starts for the first time
    Then ~/.ir-playbook/config/ is created with default config files
    And ~/.ir-playbook/data/cache/, data/processed/, data/raw/ are created

Feature: Anthropic SDK for Compatible Providers

  Scenario: Provider with api_type anthropic uses Anthropic SDK
    Given model_config.yaml has a provider with api_type: anthropic
    When the inference engine calls that provider
    Then it uses the Anthropic Python SDK directly
    And messages are converted from OpenAI format to Anthropic format
    And system messages are extracted into the system parameter

  Scenario: Anthropic call handles thinking blocks
    Given the Anthropic API returns content with thinking blocks
    When the response is parsed
    Then only text blocks are included in the output
    And thinking blocks are filtered out

Feature: Generic Profile Fallback

  Scenario: No profile in non-interactive mode generates generic playbook
    Given config/org_profile.yaml does not exist
    And the user runs in CLI argument mode (non-interactive)
    When the playbook is generated
    Then the org name is "[Your Organization]"
    And tech stack fields show "Not configured"
    And the playbook includes generic commands without assuming any specific vendor

  Scenario: Demo profile in non-interactive mode uses generic data
    Given config/org_profile.yaml has demo: true with ACME Corp data
    And the user runs in CLI argument mode (non-interactive)
    When the playbook is generated
    Then ACME-specific data is NOT used
    And the org name is "[Your Organization]"
    And the playbook uses generic commands
```
