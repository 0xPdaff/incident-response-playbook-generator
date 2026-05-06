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
9. Knowledge base: NIST SP 800-61 Rev. 3 (full CSF 2.0 Community Profile extracted from official PDF) — stored in `config/knowledge_base/nist_800_61r3.md`, injected into LLM prompts at runtime
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

---

## Global Happy Path

This is the main flow of the application. Each feature below has its own specific happy/sad paths.

1. User provides incident description via one of 4 input modes
2. Agent loads org profile from `config/org_profile.yaml`
3. Agent classifies incident type and infers severity (or uses specified)
4. Agent generates structured playbook with 5 NIST phases
5. Each phase includes: description, commands, timeline, escalation criteria
6. Playbook rendered as Markdown (and optionally PDF)
7. Output saved to `data/processed/` with timestamp

## Global Sad Paths

These apply across the entire application regardless of feature:

- **No API key configured for any provider:** Clear error message listing required keys per provider with ENV variable names
- **LLM rate limit hit (429):** Retries with exponential backoff up to 3 times (2s, 4s, 8s), then falls back to next provider in fallback chain
- **All providers exhausted:** Returns error to user with list of attempted providers and failure reasons
- **LLM returns malformed JSON:** `parse_llm_json()` strips markdown fences, extracts embedded JSON object; if still invalid, returns empty dict and generation continues with defaults
- **API server port in use:** Reports port conflict with suggestion to use `--port`

---

## Feature: Playbook Generation — CLI Argument Mode

### Description
User provides an incident description directly via the `-d` / `--description` flag. This is the fastest one-liner mode.

### Happy Path
1. User runs `python src/app.py -d "Ransomware detected on finance server"`
2. Banner is printed
3. Input is sanitized (strip whitespace, remove null bytes, normalize line endings)
4. Input is validated (non-empty, ≥10 chars, ≤10000 chars)
5. PII detection runs — warnings shown if SSN/email/phone/credit card patterns found
6. Org profile loaded from `config/org_profile.yaml`
7. If profile missing or `demo: true` → generic fallback (assumption 26)
8. InferenceEngine initialized with default or `--provider` override
9. First LLM call: classify incident type, severity, MITRE tactics
10. Second LLM call: generate 5-phase NIST playbook with stack-specific commands
11. Playbook saved as Markdown in `data/processed/playbook_{type}_{timestamp}.md`
12. If `--format pdf` → also render PDF via WeasyPrint
13. File path(s) printed to stdout
14. Full playbook content printed to stdout

### Sad Paths
- **Empty description (`-d ""`):** Validation fails → `❌ Incident description is empty.` with example + `sys.exit(1)`
- **Description < 10 chars (`-d "hack"`):** Validation fails → `❌ Incident description too short (4 chars).` with example + `sys.exit(1)`
- **Description > 10000 chars:** Truncated silently to 10000 chars, warning logged
- **Invalid `--severity` value:** Click `Choice` validator rejects before reaching validation logic — CLI shows valid options
- **Invalid `--provider` value:** Click `Choice` validator rejects — CLI shows valid options
- **`--provider` valid but no API key for it:** Falls back to default provider with warning
- **No API key for ANY provider:** InferenceEngine returns `success: false` → `❌ Generation failed: [error]` + `sys.exit(1)`
- **Org profile YAML malformed:** `get_org_profile()` catches exception → uses empty dict, warns "Invalid org profile. Using defaults."
- **File output directory not writable:** `render_markdown()` creates dir via `ensure_directory()`; if OS denies → OSError propagated
- **PDF requested but WeasyPrint not installed:** `render_pdf()` returns None → `⚠️ PDF generation skipped (WeasyPrint not installed)`

---

## Feature: Playbook Generation — Interactive Mode

### Description
User runs `-i` / `--interactive` and is guided through prompts for description, severity, and provider. After generation, user can generate another playbook.

### Happy Path
1. User runs `python src/app.py -i`
2. Banner is printed
3. Prompt: "📝 Describe the security incident" → user enters description
4. Prompt: "🎯 Severity" (empty = auto-infer) → user presses Enter
5. Prompt: "🤖 Provider" (empty = default) → user presses Enter
6. Input validated and sanitized (same as CLI mode)
7. If demo/missing profile + interactive=True → `_ask_relevant_stack()` asks incident-type-specific questions
8. Playbook generated via InferenceEngine
9. Displayed in terminal with separator line
10. Saved as Markdown (and PDF if requested)
11. Prompt: "🔄 Generate another playbook?" → if yes, restart wizard

### Sad Paths
- **Description entered but < 10 chars:** `❌ Description too short.` → returns to prompt (no exit, stays in interactive)
- **Empty description (just Enter):** Same — too short error
- **Severity entered but invalid:** Value passed to `validate_severity()` → validation fails → `❌ Invalid severity.` + returns (no exit)
- **Provider entered but invalid:** Value passed to `validate_provider()` → warning added → falls back to default
- **LLM generation fails:** `❌ Generation failed: [error]` → returns (no exit, stays in interactive loop)
- **User presses Ctrl+C during prompt:** Click raises `KeyboardInterrupt` / `Abort` → application exits gracefully

---

## Feature: Playbook Generation — API Server Mode

### Description
User starts a REST API server with `--serve`. Swagger UI available at `/docs`. Playbooks generated via `POST /api/v1/playbook`.

### Happy Path
1. User runs `python src/app.py --serve --port 8080`
2. Banner is printed
3. Uvicorn starts on specified port (default 8000 from config)
4. Swagger UI available at `http://localhost:8080/docs`
5. `POST /api/v1/playbook` with JSON body: `{"incident_description": "...", "severity": "high", "provider": "anthropic"}`
6. Pydantic `PlaybookRequest` model validates input:
   - `incident_description`: required, min 10 chars
   - `severity`: optional, must be one of low/medium/high/critical
   - `provider`: optional, must be string
7. Input sanitized, PII detected, playbook generated
8. Response: `{playbook, classification, provider_used, output_path}` with HTTP 200

### Sad Paths
- **Missing `incident_description` field:** Pydantic ValidationError → HTTP 422 with field-level error details
- **`incident_description` < 10 chars:** Pydantic ValidationError → HTTP 422
- **Invalid `severity` value (e.g., "extreme"):** Pydantic ValidationError → HTTP 422
- **JSON body malformed (not valid JSON):** FastAPI returns HTTP 422 `{"detail": [{"loc": [...], "msg": "..."}]}`
- **No API key configured:** InferenceEngine returns error → HTTP 503 with error message
- **Provider override invalid:** Falls back to default with warning in response
- **Port already in use:** Uvicorn throws `OSError: [Errno 98] Address already in use` → user must use `--port` to change
- **Concurrent requests:** Handled by FastAPI async — each request processed independently, no race conditions on output files (each gets unique timestamp)

---

## Feature: Playbook Generation — File Input Mode

### Description
User provides a text file containing the incident description via `-f` / `--file`.

### Happy Path
1. User runs `python src/app.py -f incident_description.txt`
2. Banner is printed
3. Click validates `--file` path exists (`type=click.Path(exists=True)`)
4. File read with UTF-8 encoding, content stripped
5. Content passed to `_run_cli_mode()` — same validation and generation pipeline
6. Playbook generated and saved

### Sad Paths
- **File doesn't exist:** Click `Path(exists=True)` rejects before reaching app logic → CLI error with path
- **File exists but empty:** Content = `""` after strip → `❌ File is empty.` + `sys.exit(1)`
- **File has < 10 chars of content:** Passes to `_run_cli_mode()` → validation fails → `❌ Incident description too short.` + `sys.exit(1)`
- **File has > 10000 chars:** Truncated with warning (handled by sanitization)
- **File encoding not UTF-8:** `open()` with `encoding="utf-8"` → `UnicodeDecodeError` caught by OSError handler → `❌ Failed to read file: [error]` + `sys.exit(1)`
- **File contains binary/null bytes:** Null bytes removed by `sanitize_input()`

---

## Feature: Playbook Generation — Package Installed Mode

### Description
After `pip install .`, the `ir-playbook` command is available globally. Config stored in `~/.ir-playbook/config/`.

### Happy Path
1. User runs `pip install .` (or `pip install -e .` for development)
2. `ir-playbook` command registered via `pyproject.toml` `[project.scripts]` entry point
3. User runs `ir-playbook -d "ransomware detected"` from any directory
4. On first run, if `~/.ir-playbook/config/` doesn't exist → default configs copied
5. Same pipeline as CLI argument mode, reading config from `~/.ir-playbook/config/`
6. Output saved to `~/.ir-playbook/data/processed/` (or `--output-dir` override)

### Sad Paths
- **`pip install .` fails (missing deps):** Standard pip error → user must `pip install -r requirements.txt` first
- **`~/.ir-playbook/config/` not writable:** Config copy fails → falls back to package defaults
- **Running `ir-playbook` from directory with local `config/`:** Local config takes precedence over `~/.ir-playbook/config/`
- **`pyproject.toml` missing or malformed:** `pip install` fails with build error

---

## Feature: Multi-Provider Fallback

### Description
The application supports 8 LLM providers with a configurable fallback chain. If the primary provider fails, the next in chain is tried.

### Happy Path
1. `model_config.yaml` defines `default_provider` and `fallback_chain` ordered list
2. InferenceEngine tries default provider first
3. On success → returns result with `provider_used` field
4. Provider with `api_type: anthropic` (e.g., minimax) uses Anthropic SDK directly

### Sad Paths
- **Default provider API key missing:** Engine logs warning, skips to next in fallback chain
- **Default provider returns 429 (rate limit):** Retries with exponential backoff (2s, 4s, 8s), then falls back to next provider
- **Default provider returns 500/502/503/504:** Same retry logic, then fallback
- **Provider returns malformed response:** `parse_llm_json()` attempts extraction; if empty → generation continues with defaults
- **All providers in chain fail:** Returns `success: false` with error listing all attempted providers
- **`--provider` override specified:** Only that provider is tried (no fallback chain) — if it fails, generation fails
- **Ollama not running:** Connection refused on localhost:11434 → falls back to next provider in chain

---

## Feature: Extended Help (`-H` / `--extended-help`)

### Description
Shows a comprehensive usage guide with examples, provider table, config explanations, and troubleshooting tips.

### Happy Path
1. User runs `python src/app.py -H` (or `--extended-help`)
2. Banner is printed
3. Extended guide displayed with sections: Input Modes, All Flags, Supported Providers, Common Examples, Configuration Files, Troubleshooting, Installed CLI Mode
4. All 8 providers listed with model names and API key env vars
5. Program exits cleanly — no playbook generation

### Sad Paths
- **`-H` combined with `-d` flag:** Extended help takes priority — no generation attempted
- **`-H` combined with `--list-providers`:** Extended help takes priority (first `if` check in `main()`)

---

## Feature: List Providers (`--list-providers`)

### Description
Shows all supported providers with model names, API key status, local flag, and endpoint URLs.

### Happy Path
1. User runs `python src/app.py --list-providers`
2. Banner is printed
3. Provider status table displayed: Provider, Model, Key Status (✓/✗/N/A), Local, Endpoint
4. Default provider marked with `(default)`
5. Fallback chain displayed as ordered list
6. Legend shown: ✓ = key set, ✗ = missing, N/A = local provider
7. Program exits — no LLM calls made

### Sad Paths
- **`--list-providers` combined with `-d`:** List providers takes priority — no generation attempted
- **`model_config.yaml` missing or malformed:** `get_model_config()` falls back to hardcoded defaults — table shows "unknown" for models

---

## Feature: Show Organization Stack (`--show-stack`)

### Description
Displays the current organization profile, tech stack, compliance, and escalation contacts.

### Happy Path — With Active Profile
1. User runs `python src/app.py --show-stack`
2. No banner printed (unlike other commands)
3. Profile loaded from `config/org_profile.yaml`
4. Organization section: name, industry, size, profile status ("✅ Active")
5. Tech Stack section: OS, Cloud, Database, Container, SIEM, EDR, Firewall, IdP
6. Compliance section: Frameworks, Breach notification hours, Law enforcement flag
7. Escalation contacts section: SOC, IC, Legal, CISO, Comms with escalation thresholds

### Happy Path — With Demo Profile
1. Same as above but profile status shows "📋 Demo (replace with your real data)"

### Happy Path — No Profile
1. Profile is None or empty → `⚠️ No organization profile found.`
2. Tip shown: `💡 Run 'python src/app.py --setup-stack' to create one.`

### Sad Paths
- **Profile YAML is malformed (not valid YAML):** `get_org_profile()` catches exception → treated as no profile → shows "No organization profile found" warning
- **Profile missing required sections (no `org` key):** Treated as no profile

---

## Feature: Setup Organization Stack (`--setup-stack`)

### Description
Interactive wizard that guides users through configuring their org profile. Saved to `config/org_profile.yaml`.

### Happy Path — Fresh Setup (No Existing Profile)
1. User runs `python src/app.py --setup-stack`
2. Setup banner displayed
3. Wizard prompts for:
   - **Organization:** name, industry, size, region
   - **Tech Stack:** OS (comma-separated), cloud providers, database, container platform, SIEM, EDR, firewall, identity provider
   - **Compliance:** frameworks (comma-separated), breach notification hours, law enforcement notification (yes/no)
   - **Escalation Contacts:** SOC, IC, Legal, CISO, Comms emails
   - **Communication Channels:** primary channel, incident channel
4. Comma-separated inputs parsed into lists
5. `breach_notification_hours` stored as integer
6. `demo` set to `false`
7. Profile saved to `config/org_profile.yaml`
8. Success message: `✅ Organization profile saved to config/org_profile.yaml`

### Happy Path — Edit Existing Profile
1. Existing profile detected → warning shown
2. Prompt: Choose action (overwrite/edit/cancel) — default "edit"
3. User chooses "edit" → existing values used as defaults in prompts
4. User modifies desired fields
5. Updated profile saved

### Happy Path — Overwrite Existing Profile
1. User chooses "overwrite" → all prompts use example defaults (from `org_profile.example.yaml`)
2. New profile overwrites old one

### Sad Paths
- **User chooses "cancel":** `Setup cancelled.` message → existing profile unchanged
- **User enters non-numeric `breach_notification_hours`:** Code checks `.isdigit()` → falls back to 72 with no explicit warning
- **User enters empty string for org name:** `strip()` applied → saved as empty string (no validation on required fields in wizard)
- **User enters empty string for OS/cloud:** Parsed as empty list `[]` → saved with empty lists
- **User enters empty string for all fields:** All values empty or default → saved as mostly-empty profile with `demo: false`
- **Config directory not writable:** `config_path.parent.mkdir(parents=True, exist_ok=True)` → if OS denies → `PermissionError` propagated
- **YAML dump fails:** Should not happen with `yaml.dump()` but if it does → Python exception propagated
- **`org_profile.example.yaml` missing:** `load_yaml_config()` returns None → `existing = {}` → wizard uses hardcoded string defaults

---

## Feature: Version Flag (`--version`)

### Description
Shows the package version and exits. No generation attempted.

### Happy Path
1. User runs `python src/app.py --version`
2. Output: `ir-playbook, version X.Y.Z`
3. Version read from `pyproject.toml` via `importlib.metadata`
4. Exit code 0

### Sad Paths
- **`--version` combined with `-d`:** Click `--version` is a built-in flag — it takes priority and exits before reaching any other logic
- **`pyproject.toml` not found (running outside project dir without package install):** `importlib.metadata` may return "unknown" or raise `PackageNotFoundError`

---

## Feature: Demo Profile Detection

### Description
When `demo: true` in `org_profile.yaml`, the agent avoids using demo data as real context. Behavior differs between interactive and non-interactive modes.

### Happy Path — Non-Interactive with Demo Profile
1. `demo: true` detected → `_is_demo_profile()` returns True
2. Org name set to "[Your Organization]"
3. Tech stack fields set to "Not configured"
4. Playbook generated with generic commands (no vendor-specific assumptions)

### Happy Path — Interactive with Demo Profile
1. `demo: true` detected
2. After classification, `_ask_relevant_stack()` prompts for incident-type-specific tools:
   - Malware → EDR, SIEM, Firewall
   - Phishing → Identity provider, SIEM
   - DDoS → Firewall/CDN
   - Data breach → Database, SIEM
   - Other → EDR, SIEM with optional defaults
3. Empty answers filled with "Not specified"
4. Responses used as temporary tech stack for playbook generation

### Sad Paths
- **Profile has `demo: true` but empty tech_stack:** Treated as demo → generic playbook
- **Profile has `demo: false` but empty tech_stack:** `_is_demo_profile()` returns True (empty stack = not configured)
- **Profile has valid tech_stack but `demo: true`:** `_is_demo_profile()` returns True — demo flag takes priority
- **No profile at all:** `_is_demo_profile()` returns True → generic fallback

---

## Feature: PDF Output (`--format pdf`)

### Description
Generates PDF output alongside Markdown using WeasyPrint.

### Happy Path
1. User runs `python src/app.py -d "..." --format pdf`
2. WeasyPrint is installed and importable
3. Markdown playbook generated first
4. `render_pdf()` converts Markdown to HTML → PDF via WeasyPrint
5. Both `.md` and `.pdf` files saved
6. Both paths printed to stdout

### Sad Paths
- **WeasyPrint not installed:** `render_pdf()` returns None → `⚠️ PDF generation skipped (WeasyPrint not installed)` — only Markdown saved
- **WeasyPrint import fails (missing OS deps like `libpango`):** Same as not installed — returns None
- **PDF generation takes too long:** No timeout on `render_pdf()` — WeasyPrint runs until completion or crash

---

## Feature: Provider Switch at Runtime

### Description
User can override the default provider per-request via CLI flag or API body.

### Happy Path — CLI
1. Default provider is "minimax" (from `model_config.yaml`)
2. User runs `python src/app.py -d "..." --provider anthropic`
3. Anthropic used for this generation only
4. `model_config.yaml` default_provider NOT changed

### Happy Path — API
1. POST `/api/v1/playbook` with `{"incident_description": "...", "provider": "deepseek"}`
2. Deepseek used for this request only
3. Next request without `provider` field uses default

### Sad Paths
- **`--provider` value not in SUPPORTED_PROVIDERS:** Click `Choice` validator rejects before reaching app logic
- **Provider specified but no API key for it:** InferenceEngine tries it → fails → falls back to next in chain (NOT just default)
- **`provider` field in API request is null/empty:** Ignored → default provider used

---

## Feature: Anthropic SDK for Compatible Providers

### Description
Providers with `api_type: anthropic` in `model_config.yaml` use the Anthropic Python SDK directly.

### Happy Path
1. Provider config has `api_type: "anthropic"` (e.g., minimax)
2. InferenceEngine detects api_type → uses `anthropic.Anthropic()` client
3. Messages converted from OpenAI format to Anthropic format
4. System messages extracted into the `system` parameter
5. Response parsed — text blocks extracted, thinking blocks filtered out

### Sad Paths
- **Anthropic SDK not installed:** ImportError when trying to create client → falls back to litellm or returns error
- **API returns thinking blocks in content:** Filtered out by response parser — only text blocks included in output

---

## Feature: Generic Profile Fallback

### Description
When no profile exists, the agent generates playbooks with generic commands instead of assuming any specific org.

### Happy Path — No Profile in Non-Interactive Mode
1. `config/org_profile.yaml` does not exist
2. `get_org_profile()` returns empty dict
3. `_is_demo_profile()` returns True
4. Org name → "[Your Organization]"
5. Tech stack fields → "Not configured"
6. Playbook generated with generic commands (no vendor assumptions)

### Happy Path — Demo Profile in Non-Interactive Mode
1. `config/org_profile.yaml` has `demo: true` with ACME Corp data
2. ACME-specific data NOT used
3. Same generic fallback as no-profile case

### Sad Paths
- **Profile exists but `demo: true` AND user runs interactive mode:** Interactive stack questions asked → user provides real answers → those override demo data for this session
- **Profile YAML has correct structure but garbage values (e.g., `siem: "xyz123"`):** Used as-is — no validation on tech stack vendor names

---

## Validations

| Input | Validation | Error if Fails |
|-------|-----------|---------------|
| Incident description | Non-empty string, min 10 chars, max 10000 chars | `"Incident description too short. Provide at least 10 characters."` or `"Incident description is empty."` |
| Severity | One of: low, medium, high, critical | `"Invalid severity 'X'. Use: critical, high, low, medium"` |
| Provider | One of: openai, anthropic, deepseek, minimax, kimi, qwen, glm, ollama | `"Unsupported provider 'X'. Supported: ..."` |
| Org profile YAML | Valid YAML, required fields present | `"Invalid org profile. Using defaults."` |
| Output format | markdown or pdf | `"Unsupported format. Using markdown."` (Click Choice handles this) |
| API request body | Valid JSON with required fields | HTTP 422 with field-level errors |
| Setup stack inputs | Non-empty strings where required; breach hours must be numeric | Falls back to default (72 for hours, example defaults for strings) |
| Setup stack action | One of: overwrite, edit, cancel | Click Choice prompts again on invalid input |
| PII detection | Pattern matching for SSN, email, phone, credit card | Warning shown (not blocking) |

## Edge Cases

- Empty string input → validation error with example description
- Exact 10 chars → passes validation (boundary)
- 9 chars → fails validation (boundary)
- Very long incident description (>10000 chars) → truncated with warning logged
- Special characters in description (unicode, emojis, `<>$\`) → sanitized (null bytes removed, line endings normalized)
- Concurrent API requests → handled by FastAPI async; each gets unique timestamp filename
- Missing optional config → sensible defaults applied (default_provider from model_config.yaml)
- Provider API key present but invalid (expired/wrong) → authentication error with provider-specific guidance
- File with only whitespace → stripped to empty → validation error
- File with binary content → null bytes removed, rest processed
- YAML profile with extra/unknown keys → silently ignored by `get_org_profile()`
- YAML profile with correct keys but wrong types (e.g., `os: "linux"` instead of list) → `format_org_tech_stack()` handles both string and list

---

## BDD Scenarios

### Feature: Playbook Generation — CLI Argument Mode

```gherkin
  # Happy Path
  Scenario: Generate playbook from CLI argument with default settings
    Given the user runs "python src/app.py -d 'Ransomware detected on finance server'"
    And config/org_profile.yaml exists with demo: false
    And a valid API key is set for the default provider
    When the agent runs
    Then a playbook is generated with all 5 NIST phases
    And the playbook is saved as a Markdown file in data/processed/
    And the file path is printed to stdout
    And the playbook content is displayed

  Scenario: Generate playbook with explicit severity and provider
    Given the user runs with --severity critical --provider anthropic
    And a valid ANTHROPIC_API_KEY is configured
    When the playbook is generated
    Then the severity is "critical"
    And Anthropic is used as the provider
    And the default provider in model_config.yaml is unchanged

  Scenario: Generate playbook with PDF output
    Given WeasyPrint is installed
    And the user specifies --format pdf
    When the playbook is generated
    Then both Markdown and PDF files are created
    And both file paths are printed to stdout

  # Sad Paths
  Scenario: Empty description via CLI
    Given the user runs "python src/app.py -d ''"
    When the agent validates the input
    Then a validation error is returned
    And the error message includes an example valid description
    And the exit code is 1

  Scenario: Description too short
    Given the user runs "python src/app.py -d 'hack'"
    When the agent validates the input
    Then the error states "too short (4 chars)"
    And the exit code is 1

  Scenario: Description exceeds max length
    Given the user provides a description of 15000 characters
    When the agent processes it
    Then the description is truncated to 10000 characters
    And a warning is logged about truncation
    And the playbook is generated successfully

  Scenario: No API key for any provider
    Given no API key is configured for any provider in .env
    When the user attempts to generate a playbook
    Then a clear error lists which providers need which keys
    And the ENV variable names are shown
    And the exit code is 1

  Scenario: Invalid severity via CLI
    Given the user runs "python src/app.py -d 'incident' --severity extreme"
    When Click validates the --severity choice
    Then the CLI shows valid options: low, medium, high, critical
    And the command is rejected before reaching app logic

  Scenario: PDF requested but WeasyPrint not installed
    Given WeasyPrint is not installed
    And the user specifies --format pdf
    When the playbook is generated
    Then only Markdown is generated
    And a warning explains how to install WeasyPrint
```

### Feature: Playbook Generation — Interactive Mode

```gherkin
  # Happy Path
  Scenario: Generate playbook interactively with all prompts answered
    Given the user runs "python src/app.py -i"
    When the user provides a valid description at the prompt
    And leaves severity empty (auto-infer)
    And leaves provider empty (use default)
    Then a playbook is generated and displayed
    And saved as Markdown

  Scenario: Interactive mode offers to generate another playbook
    Given a playbook was generated in interactive mode
    When the user is asked "Generate another playbook?"
    And the user confirms
    Then the wizard restarts from the description prompt

  Scenario: Interactive mode with demo profile asks stack questions
    Given config/org_profile.yaml has demo: true
    And the user runs "python src/app.py -i"
    And the classified incident type is "malware"
    When the interactive mode reaches stack questions
    Then the user is prompted for EDR, SIEM, and firewall

  # Sad Paths
  Scenario: Interactive description too short — recoverable
    Given the user runs "python src/app.py -i"
    When the user enters "hack" at the description prompt
    Then "Description too short" is displayed
    And the description prompt is shown again
    When the user enters "Ransomware detected on finance server with encryption"
    Then the wizard continues to the severity prompt

  Scenario: Interactive invalid severity — recoverable
    Given the user is at the severity prompt
    When the user enters "extreme"
    Then "Invalid severity" is displayed with valid options
    And the severity prompt is shown again
    When the user enters "critical"
    Then the wizard continues to the provider prompt

  Scenario: Interactive invalid provider — recoverable with default fallback
    Given the user is at the provider prompt
    When the user enters "fakeprovider"
    Then "Provider 'fakeprovider' not found" is displayed
    And the user is asked "Use default (openai)?"
    When the user confirms
    Then the wizard uses the default provider

  Scenario: Interactive invalid provider — retry
    Given the user is at the provider prompt
    When the user enters "fakeprovider"
    And declines the default fallback
    Then the provider prompt is shown again
    When the user enters "openai"
    Then the wizard continues
```

### Feature: Playbook Generation — API Server Mode

```gherkin
  # Happy Path
  Scenario: Generate playbook via API
    Given the API server is running on port 8000
    And a valid API key is configured
    When a POST request is sent to /api/v1/playbook with:
      | field                 | value                              |
      | incident_description  | "Ransomware detected on server"    |
      | severity              | "critical"                          |
    Then the response HTTP status is 200
    And the response contains "playbook", "classification", "provider_used"

  Scenario: API request with provider override
    Given the API server is running
    When a POST request includes "provider": "deepseek"
    Then Deepseek is used for this request only

  # Sad Paths
  Scenario: API request with missing description
    Given the API server is running
    When a POST request is sent without "incident_description"
    Then the response HTTP status is 422
    And the error details reference the missing field

  Scenario: API request with description too short
    Given the API server is running
    When a POST request has "incident_description": "short"
    Then the response HTTP status is 422
    And the error mentions minimum length requirement

  Scenario: API request with invalid severity
    Given the API server is running
    When a POST request has "severity": "extreme"
    Then the response HTTP status is 422

  Scenario: API request with malformed JSON
    Given the API server is running
    When a POST request has invalid JSON body
    Then the response HTTP status is 422

  Scenario: Concurrent API requests
    Given the API server is running
    When multiple POST requests arrive simultaneously
    Then each request is processed independently
    And no race conditions occur in output files
```

### Feature: Playbook Generation — File Input Mode

```gherkin
  # Happy Path
  Scenario: Generate playbook from file
    Given a file exists at "incidents/ransomware.txt" with a valid description
    And a valid API key is configured
    When the user runs "python src/app.py -f incidents/ransomware.txt"
    Then a playbook is generated from the file contents
    And the file length is reported

  # Sad Paths
  Scenario: File does not exist
    Given no file exists at "nonexistent.txt"
    When the user runs "python src/app.py -f nonexistent.txt"
    Then Click rejects the path with "does not exist"

  Scenario: File is empty — recoverable
    Given a file exists but is empty
    When the user runs with --file pointing to that file
    Then "File is empty" error is shown
    And the user is asked "Try another file?"
    When the user confirms and provides a valid file path
    Then the wizard loads the valid file and continues

  Scenario: File is empty — user declines retry
    Given a file exists but is empty
    When the user runs with --file pointing to that file
    And declines "Try another file?"
    Then the exit code is 1

  Scenario: File content too short
    Given a file exists with content "hack"
    When the user runs with --file pointing to that file
    Then "Incident description too short" error is shown
    And the exit code is 1
```

### Feature: Playbook Generation — Package Installed Mode

```gherkin
  # Happy Path
  Scenario: Use ir-playbook after pip install
    Given the project is installed with "pip install ."
    When the user runs "ir-playbook --version"
    Then the version is displayed successfully

  Scenario: Package mode uses ~/.ir-playbook/ for config
    Given the project is installed as a package
    And the user runs "ir-playbook" from any directory
    Then config files are read from ~/.ir-playbook/config/
    And if no config exists, defaults are copied on first run

  # Sad Paths
  Scenario: pyproject.toml missing entry point
    Given pyproject.toml exists but has no [project.scripts]
    When the user runs "pip install ."
    Then the "ir-playbook" command is not registered
    And only "python src/app.py" works
```

### Feature: Multi-Provider Fallback

```gherkin
  # Happy Path
  Scenario: Fallback from failed primary to working secondary
    Given the primary provider is "minimax"
    And the Minimax API key is invalid
    And a valid OpenAI key is configured as next in fallback chain
    When the agent attempts generation
    Then it falls back to OpenAI
    And a warning is logged about the primary provider failure
    And the playbook is generated successfully

  Scenario: Provider with api_type anthropic uses Anthropic SDK
    Given model_config.yaml has a provider with api_type: anthropic
    When the inference engine calls that provider
    Then it uses the Anthropic Python SDK directly
    And system messages are extracted into the system parameter

  # Sad Paths
  Scenario: All providers in chain fail
    Given all providers in the fallback chain have invalid or missing API keys
    When the agent attempts generation
    Then "success" is false in the result
    And the error lists all attempted providers

  Scenario: Ollama not running
    Given the fallback chain includes "ollama"
    And Ollama is not running on localhost:11434
    When the engine tries Ollama
    Then it fails and falls back to the next provider in chain
```

### Feature: Extended Help

```gherkin
  # Happy Path
  Scenario: Show extended help with -H flag
    Given the user runs "python src/app.py -H"
    Then the banner is displayed
    And the guide includes sections for input modes, all flags, providers, examples, config, troubleshooting, and installed mode

  Scenario: Extended help shows all 8 providers
    Given the user runs "python src/app.py -H"
    Then the provider table lists all 8 providers with model names and API key env vars

  # Sad Paths
  Scenario: Extended help with description flag
    Given the user runs "python src/app.py -H -d 'ransomware'"
    Then only the extended help is shown
    And no playbook generation is attempted
```

### Feature: List Providers

```gherkin
  # Happy Path
  Scenario: List providers with mixed API key status
    Given OPENAI_API_KEY is set and ANTHROPIC_API_KEY is not set
    When the user runs "python src/app.py --list-providers"
    Then OpenAI shows "✓" for key status
    And Anthropic shows "✗" for key status
    And Ollama shows "N/A" for key status
    And the default provider is marked
    And the fallback chain is displayed

  # Sad Paths
  Scenario: List providers does not trigger generation
    Given the user runs "python src/app.py --list-providers -d 'incident'"
    Then only the provider status table is shown
    And no LLM calls are made
```

### Feature: Show Organization Stack

```gherkin
  # Happy Path
  Scenario: Show active profile
    Given config/org_profile.yaml exists with demo: false and valid data
    When the user runs "python src/app.py --show-stack"
    Then the profile status shows "✅ Active"
    And tech stack, compliance, and escalation contacts are displayed

  Scenario: Show demo profile
    Given config/org_profile.yaml has demo: true
    When the user runs "python src/app.py --show-stack"
    Then the profile status shows "📋 Demo"

  Scenario: Show when no profile exists
    Given config/org_profile.yaml does not exist
    When the user runs "python src/app.py --show-stack"
    Then "No organization profile found" is shown
    And a tip suggests running --setup-stack

  # Sad Paths
  Scenario: Profile YAML is malformed
    Given config/org_profile.yaml contains invalid YAML
    When the user runs "python src/app.py --show-stack"
    Then it is treated as no profile
    And "No organization profile found" is shown
```

### Feature: Setup Organization Stack

```gherkin
  # Happy Path
  Scenario: Fresh setup creates profile
    Given config/org_profile.yaml does not exist
    When the user runs "python src/app.py --setup-stack"
    And completes all prompts
    Then the profile is saved with demo: false
    And contains org, tech_stack, teams, compliance, and channels sections
    And breach_notification_hours is stored as an integer

  Scenario: Edit existing profile
    Given config/org_profile.yaml exists with org name "My Company"
    When the user runs "python src/app.py --setup-stack"
    And chooses "edit"
    Then existing values are used as defaults
    And the updated profile is saved

  Scenario: Overwrite existing profile
    Given config/org_profile.yaml exists
    When the user chooses "overwrite" in the setup wizard
    Then all prompts use example defaults
    And the new profile overwrites the old one

  # Sad Paths
  Scenario: Cancel setup
    Given config/org_profile.yaml exists
    When the user chooses "cancel" in the setup wizard
    Then "Setup cancelled" is shown
    And the existing profile is unchanged

  Scenario: Non-numeric breach notification hours — recoverable
    Given the user enters "abc" for breach notification hours
    Then "not a valid number" is displayed
    And the breach hours prompt is shown again
    When the user enters "48"
    Then the profile is saved with data_breach_notification_hours: 48

  Scenario: Empty organization name — recoverable
    Given the user enters nothing for organization name
    Then "Organization name is required" is displayed
    And the organization name prompt is shown again
    When the user enters "Valid Corp"
    Then the wizard continues

  Scenario: Invalid law enforcement notification — recoverable
    Given the user enters "maybe" for law enforcement notification
    Then "Please enter 'yes' or 'no'" is displayed
    And the prompt is shown again
    When the user enters "yes"
    Then the wizard continues

  Scenario: Empty comma-separated list (OS field)
    Given the user enters nothing for Operating systems
    When the wizard processes the input
    Then os is saved as an empty list []
```

### Feature: Version Flag

```gherkin
  # Happy Path
  Scenario: Show version
    Given the user runs "python src/app.py --version"
    Then the version string is displayed (e.g., "ir-playbook, version 1.0.0")
    And the program exits with code 0

  Scenario: Version matches pyproject.toml
    Given pyproject.toml defines version "1.0.0"
    When the user runs "python src/app.py --version"
    Then the output contains "1.0.0"

  # Sad Paths
  Scenario: Version flag combined with description
    Given the user runs "python src/app.py --version -d 'incident'"
    Then only the version is shown
    And no playbook generation is attempted
```

### Feature: Demo Profile Detection

```gherkin
  # Happy Path
  Scenario: Non-interactive with demo profile uses generic data
    Given config/org_profile.yaml has demo: true with ACME Corp data
    And the user runs in CLI argument mode
    When the playbook is generated
    Then ACME-specific data is NOT used
    And org name is "[Your Organization]"
    And generic commands are generated

  Scenario: Interactive with demo profile asks stack questions
    Given config/org_profile.yaml has demo: true
    And the user runs "python src/app.py -i"
    And the classified incident type is "malware"
    When stack questions are asked
    Then the user is prompted for EDR, SIEM, and firewall

  # Sad Paths
  Scenario: Profile with valid tech_stack but demo: true
    Given config/org_profile.yaml has demo: true and full tech_stack
    When _is_demo_profile() is called
    Then it returns True (demo flag takes priority over valid stack)

  Scenario: No profile at all
    Given config/org_profile.yaml does not exist
    When _is_demo_profile() is called
    Then it returns True
    And generic fallback is used
```

### Feature: Anthropic SDK for Compatible Providers

```gherkin
  # Happy Path
  Scenario: Provider with api_type anthropic uses Anthropic SDK
    Given model_config.yaml has a provider with api_type: anthropic
    When the inference engine calls that provider
    Then it uses the Anthropic Python SDK directly
    And messages are converted from OpenAI format to Anthropic format

  # Sad Paths
  Scenario: Anthropic response with thinking blocks
    Given the Anthropic API returns content with thinking blocks
    When the response is parsed
    Then only text blocks are included in the output
    And thinking blocks are filtered out
```

---

## Test Coverage Map

Legend: ✅ = test exists | ❌ = test missing | ⚠️ = partial coverage

### Feature: CLI Argument Mode

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Generate playbook from CLI arg | test_integration.py | test_full_pipeline_with_mock | happy | ✅ |
| Playbook includes NIST phases | test_integration.py | test_playbook_includes_nist_phases | happy | ✅ |
| Playbook includes metadata | test_integration.py | test_playbook_includes_metadata | happy | ✅ |
| Severity override respected | test_integration.py | test_playbook_includes_severity_override | happy | ✅ |
| Empty description | test_guardrails.py | test_empty_description | sad | ✅ |
| Too short description | test_guardrails.py | test_too_short_description | sad | ✅ |
| Exact minimum length | test_guardrails.py | test_exact_minimum_length | edge | ✅ |
| Very long description | test_guardrails.py | test_very_long_description | edge | ✅ |
| Whitespace-only description | test_guardrails.py | test_whitespace_only_description | sad | ✅ |
| No provider available | test_integration.py | test_no_provider_available | sad | ✅ |
| Invalid severity via API model | test_integration.py | test_invalid_severity | sad | ✅ |
| Short desc via API model | test_integration.py | test_short_description_rejected | sad | ✅ |
| PII detection (email) | test_additional_coverage.py | test_pii_detection_in_description | sad | ✅ |
| PII detection (SSN) | test_additional_coverage.py | test_pii_detection_ssn | sad | ✅ |
| PII detection (credit card) | test_additional_coverage.py | test_pii_detection_credit_card | sad | ✅ |
| PII detection (phone) | test_additional_coverage.py | test_pii_detection_phone | sad | ✅ |
| Description 10 chars (boundary) | test_additional_coverage.py | test_description_exactly_10_chars_passes | edge | ✅ |
| Description 9 chars (boundary) | test_additional_coverage.py | test_description_9_chars_fails | edge | ✅ |
| 10000 chars not truncated | test_additional_coverage.py | test_description_10000_chars_not_truncated | edge | ✅ |
| 10001 chars truncated | test_additional_coverage.py | test_description_10001_chars_truncated | edge | ✅ |
| Special characters / unicode | test_additional_coverage.py | test_special_characters_in_description | edge | ✅ |
| Null bytes removed | test_additional_coverage.py | test_null_bytes_removed_from_description | edge | ✅ |
| Invalid provider CLI rejection | — | — | sad | ❌ |

### Feature: Interactive Mode

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Interactive valid then decline another | test_additional_coverage.py | test_interactive_valid_then_generate_another_no | happy | ✅ |
| Interactive too-short description | test_additional_coverage.py | test_interactive_too_short_description | sad (recoverable) | ✅ |
| Interactive empty description | test_additional_coverage.py | test_interactive_empty_description | sad (recoverable) | ✅ |
| Generate another playbook loop | test_additional_coverage.py | test_interactive_valid_then_generate_another_no | happy | ✅ |
| Ctrl+C handling | test_additional_coverage.py | test_interactive_ctrl_c_exits_gracefully | sad | ✅ |
| Description retry then valid | test_additional_coverage.py | test_interactive_description_retry_then_valid | recoverable | ✅ |
| Severity retry then valid | test_additional_coverage.py | test_interactive_severity_retry_then_valid | recoverable | ✅ |
| Provider retry accept default | test_additional_coverage.py | test_interactive_provider_retry_accept_default | recoverable | ✅ |

### Feature: API Server Mode

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Valid API request | test_integration.py | test_valid_request | happy | ✅ |
| Request with severity | test_integration.py | test_request_with_severity | happy | ✅ |
| Missing description → 422 | test_additional_coverage.py | test_api_missing_description_returns_422 | sad | ✅ |
| Invalid severity | test_integration.py | test_invalid_severity | sad | ✅ |
| Malformed JSON → 422 | test_additional_coverage.py | test_api_malformed_json_returns_422 | sad | ✅ |
| Concurrent requests | — | — | edge | ❌ |
| Port conflict | — | — | sad | ❌ |

### Feature: File Input Mode

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Valid file input | test_additional_coverage.py | test_file_input_valid_content | happy | ✅ |
| File not found (Click rejects) | test_additional_coverage.py | test_file_not_found_rejected_by_click | sad | ✅ |
| Empty file retry with valid file | test_additional_coverage.py | test_file_empty_retry_with_valid_file | recoverable | ✅ |
| Empty file decline retry exits | test_additional_coverage.py | test_file_empty_decline_retry_exits | sad | ✅ |
| File content too short | test_additional_coverage.py | test_file_content_too_short | sad | ✅ |
| File with non-UTF8 encoding | — | — | sad | ❌ |

### Feature: Package Installed Mode

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| pyproject.toml entry point | test_cli_features.py | test_entry_point_defined | happy | ✅ |
| Package name correct | test_cli_features.py | test_package_name | happy | ✅ |
| Version in pyproject.toml | test_cli_features.py | test_version_defined | happy | ✅ |
| Dependencies listed | test_cli_features.py | test_dependencies_include_click | happy | ✅ |
| Python version minimum | test_cli_features.py | test_python_version_minimum | happy | ✅ |
| Config dir creation on first run | — | — | happy | ❌ |

### Feature: Multi-Provider Fallback

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| No provider available error | test_additional_coverage.py | test_no_api_keys_returns_error | sad | ✅ |
| Fallback chain order | test_additional_coverage.py | test_fallback_chain_order | happy | ✅ |
| Provider override chain | test_additional_coverage.py | test_provider_override_creates_single_provider_chain | happy | ✅ |
| Ollama not running | — | — | sad | ❌ |

### Feature: Extended Help

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Show with -H | test_cli_features.py | test_extended_help_shows_guide | happy | ✅ |
| Show with --extended-help | test_cli_features.py | test_extended_help_long_flag | happy | ✅ |
| Includes all sections | test_cli_features.py | test_extended_help_includes_* (7 tests) | happy | ✅ |
| Does not trigger generation | test_cli_features.py | test_extended_help_does_not_generate | sad | ✅ |

### Feature: List Providers

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Shows provider table | test_cli_features.py | test_list_providers_shows_table | happy | ✅ |
| Shows all providers | test_cli_features.py | test_list_providers_shows_all_providers | happy | ✅ |
| Key status (✓/✗/N/A) | test_cli_features.py | test_list_providers_shows_key_status | happy | ✅ |
| Ollama as local | test_cli_features.py | test_list_providers_shows_ollama_as_local | happy | ✅ |
| Fallback chain displayed | test_cli_features.py | test_list_providers_shows_fallback_chain | happy | ✅ |
| Does not trigger generation | test_cli_features.py | test_list_providers_does_not_generate | sad | ✅ |

### Feature: Show Organization Stack

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Active profile display | test_cli_features.py | test_show_stack_with_active_profile | happy | ✅ |
| Demo profile display | test_cli_features.py | test_show_stack_with_demo_profile | happy | ✅ |
| No profile warning | test_cli_features.py | test_show_stack_no_profile | sad | ✅ |
| Compliance displayed | test_cli_features.py | test_show_stack_displays_compliance | happy | ✅ |
| Escalation contacts | test_cli_features.py | test_show_stack_displays_escalation_contacts | happy | ✅ |
| Tech stack fields | test_cli_features.py | test_show_stack_displays_tech_stack_fields | happy | ✅ |
| Malformed YAML handling | test_additional_coverage.py | test_show_stack_malformed_yaml | sad | ✅ |

### Feature: Setup Organization Stack

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Fresh setup creates profile | test_cli_features.py | test_setup_stack_creates_profile | happy | ✅ |
| Cancel setup | test_cli_features.py | test_setup_stack_cancel | sad | ✅ |
| Edit existing profile | test_additional_coverage.py | test_setup_stack_edit_existing_profile | happy | ✅ |
| Overwrite existing profile | test_additional_coverage.py | test_setup_stack_overwrite_existing_profile | happy | ✅ |
| Non-numeric breach hours (retry) | test_additional_coverage.py | test_setup_stack_non_numeric_breach_hours | recoverable | ✅ |
| Empty org name (retry) | test_additional_coverage.py | test_setup_stack_empty_org_name_retries | recoverable | ✅ |
| Invalid breach hours retry then valid | test_additional_coverage.py | test_setup_stack_breach_hours_non_numeric_retries | recoverable | ✅ |
| Invalid law enf retry then valid | test_additional_coverage.py | test_setup_stack_law_enf_invalid_retries | recoverable | ✅ |
| Empty comma-separated fields | test_additional_coverage.py | test_setup_stack_empty_comma_separated_fields | edge | ✅ |
| Config dir not writable | — | — | sad | ❌ |

### Feature: Version Flag

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Shows version string | test_cli_features.py | test_version_output | happy | ✅ |
| Contains actual version | test_cli_features.py | test_version_contains_actual_version | happy | ✅ |
| Does not trigger generation | test_cli_features.py | test_version_exits_without_generation | sad | ✅ |

### Feature: Demo Profile Detection

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| demo: true detected | test_cli_features.py | test_demo_flag_true | happy | ✅ |
| demo: false with stack | test_cli_features.py | test_demo_flag_false_with_stack | happy | ✅ |
| Empty profile = demo | test_cli_features.py | test_empty_profile | sad | ✅ |
| None profile = demo | test_cli_features.py | test_none_profile | sad | ✅ |
| Empty tech_stack = demo | test_cli_features.py | test_profile_with_empty_tech_stack | sad | ✅ |
| Partial stack = demo | test_cli_features.py | test_profile_with_partial_stack | sad | ✅ |
| demo: true even with valid stack | test_cli_features.py | test_demo_true_even_with_valid_stack | sad | ✅ |
| Non-interactive generic fallback | test_cli_features.py | test_demo_profile_non_interactive_uses_generic | happy | ✅ |

### Feature: Interactive Stack Questions

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Malware asks EDR/SIEM/Firewall | test_cli_features.py | test_malware_asks_edr_siem_firewall | happy | ✅ |
| Phishing asks identity provider | test_cli_features.py | test_phishing_asks_identity_provider | happy | ✅ |
| DDoS asks firewall only | test_cli_features.py | test_ddos_asks_firewall_only | happy | ✅ |
| Empty answers get defaults | test_cli_features.py | test_empty_answers_get_default_values | sad | ✅ |
| Data breach asks DB/SIEM | test_cli_features.py | test_data_breach_asks_database_and_siem | happy | ✅ |

### Feature: PDF Output

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Markdown output | test_additional_coverage.py | test_render_markdown_creates_file | happy | ✅ |
| Creates directory | test_integration.py | test_render_creates_directory | happy | ✅ |
| Timestamp in filename | test_additional_coverage.py | test_render_markdown_with_timestamp_in_filename | happy | ✅ |
| PDF fallback when WeasyPrint missing | test_additional_coverage.py | test_render_pdf_returns_none_when_weasyprint_missing | sad | ✅ |

### Feature: Anthropic SDK

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| api_type: anthropic uses SDK | test_additional_coverage.py | test_anthropic_api_type_routes_to_sdk | happy | ✅ |
| Thinking blocks filtered | test_additional_coverage.py | test_anthropic_thinking_blocks_filtered | sad | ✅ |

### Feature: Generic Profile Fallback

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| Non-interactive no profile = generic | test_cli_features.py | test_demo_profile_non_interactive_uses_generic | happy | ✅ |
| Org name shows generic | test_additional_coverage.py | test_no_profile_non_interactive_generic_org_name | happy | ✅ |
| OS parsed from comma-separated | test_cli_features.py | test_os_parsed_from_comma_separated | happy | ✅ |
| String OS instead of list | test_additional_coverage.py | test_profile_with_string_os_instead_of_list | edge | ✅ |
| Garbage vendor names accepted | test_additional_coverage.py | test_profile_with_garbage_vendor_names | edge | ✅ |

### Feature: NIST SP 800-61r3 Knowledge Base

| Scenario | Test File | Test Function | Type | Status |
|----------|-----------|---------------|------|--------|
| KB file exists | test_additional_coverage.py | test_knowledge_base_file_exists | happy | ✅ |
| KB loads content | test_additional_coverage.py | test_knowledge_base_loads_content | happy | ✅ |
| KB contains CSF IDs | test_additional_coverage.py | test_knowledge_base_contains_csf_ids | happy | ✅ |
| KB contains recommendations | test_additional_coverage.py | test_knowledge_base_contains_recommendations | happy | ✅ |
| KB injected in prompt | test_additional_coverage.py | test_knowledge_base_injected_in_prompt | happy | ✅ |
| KB respects context limit | test_additional_coverage.py | test_knowledge_base_respects_context_limit | edge | ✅ |

---

## Test Gap Summary

### Remaining Gaps (❌)
1. Invalid provider CLI rejection (Click Choice validator)
2. File with non-UTF8 encoding
3. Config dir creation on first run (package mode)
4. Config dir not writable
5. Concurrent API requests
6. API port conflict
7. Ollama not running → fallback

**Total remaining gaps: 7**
**Current tests: 168 (107 original + 61 new)**
**Coverage: ~97%**

### Recoverable Error Tests Added
- Interactive: description retry, severity retry, provider retry (3 tests)
- Setup Stack: empty org name, breach hours retry, law enf retry (3 tests)
- File Input: empty file retry with valid file, decline retry (2 tests)
**Total recoverable tests: 8**

### NIST Knowledge Base Tests Added
- Knowledge base file, loading, CSF IDs, recommendations, prompt injection, context limit (6 tests)
**Total KB tests: 6**