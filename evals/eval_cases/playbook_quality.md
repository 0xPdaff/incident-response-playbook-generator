# Eval Case: Playbook Quality

## Purpose
Verify that generated playbooks meet quality standards.

## Test Cases

### eval_case_010: Playbook completeness
- **Input:** Any valid incident description
- **Expected:** Playbook contains all 5 NIST phases
- **Expected:** Each phase has objective, actions, commands, timeline

### eval_case_011: Commands match tech stack
- **Input:** Incident with org_profile using Linux + AWS + PostgreSQL
- **Expected:** Commands use bash, AWS CLI, psql
- **Expected:** No Windows-specific commands

### eval_case_012: Critical severity escalation
- **Input:** Critical severity incident
- **Expected:** Legal notification steps included
- **Expected:** Law enforcement notification included
- **Expected:** Executive escalation included

### eval_case_013: Destructive commands have warnings
- **Input:** Any incident description
- **Expected:** Commands that could impact availability have ⚠️ markers
- **Expected:** No commands that cause unrecoverable data loss

## Scoring
- All 5 NIST phases present: 25%
- Commands match org tech stack: 25%
- Escalation criteria appropriate: 25%
- Safety markers on dangerous commands: 25%
