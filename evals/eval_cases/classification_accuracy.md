# Eval Case: Incident Classification Accuracy

## Purpose
Verify that the agent correctly classifies incidents by type and severity.

## Test Cases

### eval_case_001: Ransomware identification
- **Input:** "Ransomware encrypting files with .locked extension, demanding Bitcoin payment"
- **Expected type:** malware
- **Expected severity:** critical or high
- **Expected MITRE tactics:** Impact, Execution

### eval_case_002: Phishing with credential theft
- **Input:** "Employees received fake password reset emails, 3 clicked and entered credentials"
- **Expected type:** phishing
- **Expected severity:** high
- **Expected MITRE tactics:** Initial Access, Credential Access

### eval_case_003: Cloud misconfiguration
- **Input:** "S3 bucket with customer PII found publicly accessible"
- **Expected type:** misconfiguration
- **Expected severity:** high or critical
- **Expected MITRE tactics:** Discovery, Collection

### eval_case_004: DDoS attack
- **Input:** "Website receiving 50x normal traffic, service degraded for 2 hours"
- **Expected type:** ddos
- **Expected severity:** medium or high
- **Expected MITRE tactics:** Impact

### eval_case_005: Insider threat
- **Input:** "Employee downloaded 10GB of source code to USB drive before resignation"
- **Expected type:** insider_threat
- **Expected severity:** high
- **Expected MITRE tactics:** Exfiltration, Collection

## Scoring
- Type match: 40%
- Severity within 1 level: 30%
- At least 1 correct MITRE tactic: 30%
