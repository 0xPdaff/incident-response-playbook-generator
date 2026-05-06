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
