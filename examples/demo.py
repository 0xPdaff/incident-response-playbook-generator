#!/usr/bin/env python3
"""
Demo script for the Incident Response Playbook Generator.

Demonstrates all 4 input modes:
1. CLI argument
2. Interactive (simulated)
3. REST API
4. File input

Run with: python examples/demo.py
"""

import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.chains.playbook_generator import generate_playbook
from src.inference.engine import InferenceEngine
from src.utils.output import render_markdown


SAMPLE_INCIDENT = """
We detected ransomware on our primary finance server (FIN-SRV-01) at approximately
2:30 AM UTC on January 15th, 2026. The ransomware is encrypting files with a .locked
extension and leaving ransom notes in each affected directory demanding 5 BTC.

Initial investigation suggests the infection vector was a phishing email received by
an employee in the accounting department (jane.doe@acme.com) approximately 4 hours
before the encryption began. The email contained a malicious macro-enabled Excel
attachment disguised as an invoice.

Currently affected systems:
- FIN-SRV-01 (Windows Server 2022) — fully encrypted
- FIN-SRV-02 (Windows Server 2022) — partial encryption in progress
- ACCT-WS-15 (Windows 11 workstation) — patient zero

The ransomware appears to be spreading laterally via SMB. Our CrowdStrike EDR is
showing alerts but has not auto-contained the threat. No data exfiltration has been
confirmed yet, but the finance server contains PII for approximately 50,000 customers
and PCI-DSS regulated payment data.

We need immediate guidance on containment, eradication, and recovery steps. Our
organization is subject to GDPR and SOC 2 compliance requirements.
"""


def demo_cli_argument():
    """Demo: CLI argument mode (single description)."""
    print("=" * 60)
    print("DEMO 1: CLI Argument Mode")
    print("=" * 60)
    print(f"\nIncident: Ransomware on finance server")
    print(f"Severity: Not specified (will be inferred)")
    print()

    engine = InferenceEngine()
    result = generate_playbook(
        engine=engine,
        description=SAMPLE_INCIDENT,
        severity=None,  # Let the agent infer
    )

    if result["success"]:
        print(f"✅ Playbook generated!")
        print(f"   Provider: {result['provider_used']}")
        print(f"   Type: {result['classification'].get('incident_type')}")
        print(f"   Severity: {result['classification'].get('severity')}")
        print(f"   MITRE Tactics: {result['classification'].get('mitre_tactics')}")

        # Save
        path = render_markdown(
            result["playbook"],
            result["classification"].get("incident_type", "incident"),
        )
        print(f"\n📄 Saved to: {path}")

        # Preview
        print("\n--- Playbook Preview (first 500 chars) ---")
        print(result["playbook"][:500])
        print("...")
    else:
        print(f"❌ Error: {result['error']}")

    return result


def demo_file_input():
    """Demo: File input mode."""
    print("\n" + "=" * 60)
    print("DEMO 2: File Input Mode")
    print("=" * 60)

    # Write sample to temp file
    temp_file = PROJECT_ROOT / "examples" / "sample_incident.txt"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(SAMPLE_INCIDENT)

    print(f"\nIncident loaded from: {temp_file}")

    # Read and process
    with open(temp_file, "r") as f:
        description = f.read()

    engine = InferenceEngine()
    result = generate_playbook(engine=engine, description=description, severity="critical")

    if result["success"]:
        print(f"✅ Playbook generated with severity override: critical")
        print(f"   Provider: {result['provider_used']}")
    else:
        print(f"❌ Error: {result['error']}")

    return result


def demo_api_check():
    """Demo: Check API health (without starting server)."""
    print("\n" + "=" * 60)
    print("DEMO 3: Provider Health Check")
    print("=" * 60)

    engine = InferenceEngine()
    health = engine.check_provider_health()

    print("\nProvider Status:")
    for provider, available in health.items():
        status = "✅ Available" if available else "❌ No API key"
        print(f"  {provider:12s} {status}")

    return health


def main():
    """Run all demos."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     🛡️  Incident Response Playbook Generator               ║
║     DEMO MODE                                               ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Demo 3: Provider health (fastest, no LLM call)
    health = demo_api_check()

    # Only run LLM demos if at least one provider is available
    has_provider = any(health.values())
    if not has_provider:
        print("\n⚠️  No LLM providers available. Configure an API key in .env to run full demos.")
        print("   Copy .env.example to .env and add your API key.")
        return

    # Demo 1: CLI argument
    result = demo_cli_argument()

    # Demo 2: File input with severity override
    demo_file_input()

    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print("\nTo start the API server: python src/app.py --serve")
    print("For interactive mode:    python src/app.py --interactive")


if __name__ == "__main__":
    main()
