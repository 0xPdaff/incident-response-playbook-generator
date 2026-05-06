#!/usr/bin/env python3
"""
Incident Response Playbook Generator

AI-powered agent that generates customized incident response playbooks
following NIST SP 800-61. Supports 4 input modes and 8+ LLM providers.

Usage:
    # CLI argument mode
    python src/app.py --description "Ransomware detected on finance server"

    # Interactive mode
    python src/app.py --interactive

    # File input mode
    python src/app.py --file incident_description.txt

    # API server mode
    python src/app.py --serve

    # With options
    python src/app.py --description "..." --severity critical --provider anthropic --format pdf
"""

import logging
import os
import sys
from pathlib import Path

import click

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import get_api_port, get_default_provider, get_log_level
from src.utils.constants import SUPPORTED_PROVIDERS


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def print_banner() -> None:
    """Print the application banner."""
    click.echo("""
╔══════════════════════════════════════════════════════════════╗
║     🛡️  Incident Response Playbook Generator               ║
║     AI-powered • NIST SP 800-61 • Multi-provider            ║
╚══════════════════════════════════════════════════════════════╝
""")


@click.group(invoke_without_command=True)
@click.option("--description", "-d", type=str, help="Incident description (CLI argument mode).")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Path to file with incident description.")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive CLI mode.")
@click.option("--serve", "-s", is_flag=True, help="Start the REST API server.")
@click.option("--severity", type=click.Choice(["low", "medium", "high", "critical"]), help="Severity level (inferred if not specified).")
@click.option("--provider", type=click.Choice(SUPPORTED_PROVIDERS), help="LLM provider to use.")
@click.option("--format", "output_format", type=click.Choice(["markdown", "pdf"]), default="markdown", help="Output format.")
@click.option("--output-dir", type=click.Path(), help="Output directory for generated files.")
@click.option("--port", type=int, default=None, help="API server port (default: from config or 8000).")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose (DEBUG) logging.")
@click.option("--extended-help", "-H", is_flag=True, help="Show extended usage guide with examples and provider info.")
@click.option("--list-providers", is_flag=True, help="List all supported providers and their API key status.")
@click.pass_context
def main(
    ctx: click.Context,
    description: str | None,
    file_path: str | None,
    interactive: bool,
    serve: bool,
    severity: str | None,
    provider: str | None,
    output_format: str,
    output_dir: str | None,
    port: int | None,
    verbose: bool,
    extended_help: bool,
    list_providers: bool,
) -> None:
    """Incident Response Playbook Generator — AI-powered NIST playbooks."""
    ctx.ensure_object(dict)

    # Setup
    log_level = "DEBUG" if verbose else get_log_level()
    setup_logging(log_level)

    # Handle meta-commands before banner
    if extended_help:
        print_banner()
        _show_extended_help()
        return

    if list_providers:
        print_banner()
        _show_provider_status()
        return

    print_banner()

    ctx.obj["severity"] = severity
    ctx.obj["provider"] = provider
    ctx.obj["output_format"] = output_format
    ctx.obj["output_dir"] = output_dir

    # Determine input mode
    if serve:
        _start_api_server(port)
        return

    if file_path:
        _run_file_mode(file_path, ctx.obj)
        return

    if interactive:
        _run_interactive_mode(ctx.obj)
        return

    if description:
        _run_cli_mode(description, ctx.obj)
        return

    # No mode specified — default to help
    click.echo(ctx.get_help())


def _run_cli_mode(description: str, options: dict) -> None:
    """Run in CLI argument mode."""
    from src.agent.chains.playbook_generator import generate_playbook
    from src.guardrails.input_validation import validate_playbook_request
    from src.inference.engine import InferenceEngine
    from src.utils.output import render_markdown, render_pdf

    click.echo(f"📋 Processing incident description ({len(description)} chars)...\n")

    # Validate
    validation = validate_playbook_request(
        description=description,
        severity=options.get("severity"),
        provider=options.get("provider"),
    )

    if not validation.is_valid:
        for error in validation.errors:
            click.echo(f"❌ {error}", err=True)
        sys.exit(1)

    for warning in validation.warnings:
        click.echo(f"⚠️  {warning}")

    # Generate
    engine = InferenceEngine(provider_override=validation.provider)
    result = generate_playbook(
        engine=engine,
        description=validation.sanitized_description,
        severity=validation.severity,
        provider=validation.provider,
        interactive=False,
    )

    if not result["success"]:
        click.echo(f"\n❌ Generation failed: {result['error']}", err=True)
        sys.exit(1)

    # Output
    click.echo(f"✅ Playbook generated using {result['provider_used']}")
    click.echo(f"   Type: {result['classification'].get('incident_type', 'unknown')}")
    click.echo(f"   Severity: {result['classification'].get('severity', 'unknown')}\n")

    # Save
    md_path = render_markdown(
        result["playbook"],
        result["classification"].get("incident_type", "incident"),
        options.get("output_dir"),
    )
    click.echo(f"📄 Saved: {md_path}")

    if options.get("output_format") == "pdf":
        pdf_path = render_pdf(
            result["playbook"],
            result["classification"].get("incident_type", "incident"),
            options.get("output_dir"),
        )
        if pdf_path:
            click.echo(f"📑 PDF:   {pdf_path}")
        else:
            click.echo("⚠️  PDF generation skipped (WeasyPrint not installed)")

    click.echo(f"\n{result['playbook']}")


def _run_interactive_mode(options: dict) -> None:
    """Run in interactive CLI mode."""
    from src.agent.chains.playbook_generator import generate_playbook
    from src.guardrails.input_validation import validate_playbook_request
    from src.inference.engine import InferenceEngine
    from src.utils.output import render_markdown, render_pdf

    click.echo("🚀 Interactive Mode — Describe your incident\n")

    # Get incident description
    description = click.prompt(
        "📝 Describe the security incident",
        type=str,
    )

    if not description or len(description.strip()) < 10:
        click.echo("❌ Description too short. Please provide at least 10 characters.")
        return

    # Get optional severity
    click.echo("\nSeverity levels: low, medium, high, critical")
    click.echo("(Leave empty to auto-infer)")
    severity_input = click.prompt("🎯 Severity", default="", show_default=False)
    severity = severity_input if severity_input else None

    # Get optional provider
    default_prov = get_default_provider()
    click.echo(f"\nAvailable providers: {', '.join(SUPPORTED_PROVIDERS)}")
    click.echo(f"(Default: {default_prov})")
    provider_input = click.prompt("🤖 Provider", default="", show_default=False)
    provider = provider_input if provider_input else None

    click.echo("\n⏳ Generating playbook...\n")

    # Validate
    validation = validate_playbook_request(
        description=description,
        severity=severity,
        provider=provider,
    )

    if not validation.is_valid:
        for error in validation.errors:
            click.echo(f"❌ {error}", err=True)
        return

    for warning in validation.warnings:
        click.echo(f"⚠️  {warning}")

    # Generate
    engine = InferenceEngine(provider_override=validation.provider)
    result = generate_playbook(
        engine=engine,
        description=validation.sanitized_description,
        severity=validation.severity,
        provider=validation.provider,
        interactive=True,
    )

    if not result["success"]:
        click.echo(f"\n❌ Generation failed: {result['error']}", err=True)
        return

    # Display
    click.echo(f"✅ Playbook generated using {result['provider_used']}")
    click.echo(f"   Type: {result['classification'].get('incident_type', 'unknown')}")
    click.echo(f"   Severity: {result['classification'].get('severity', 'unknown')}\n")

    # Save
    md_path = render_markdown(
        result["playbook"],
        result["classification"].get("incident_type", "incident"),
        options.get("output_dir"),
    )
    click.echo(f"📄 Saved: {md_path}")

    if options.get("output_format") == "pdf":
        pdf_path = render_pdf(
            result["playbook"],
            result["classification"].get("incident_type", "incident"),
            options.get("output_dir"),
        )
        if pdf_path:
            click.echo(f"📑 PDF:   {pdf_path}")
        else:
            click.echo("⚠️  PDF generation skipped (WeasyPrint not installed)")

    # Print playbook
    click.echo(f"\n{'='*60}")
    click.echo(result["playbook"])

    # Offer to generate another
    if click.confirm("\n🔄 Generate another playbook?"):
        _run_interactive_mode(options)


def _run_file_mode(file_path: str, options: dict) -> None:
    """Run in file input mode."""
    click.echo(f"📂 Reading incident from: {file_path}\n")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            description = f.read().strip()
    except OSError as e:
        click.echo(f"❌ Failed to read file: {e}", err=True)
        sys.exit(1)

    if not description:
        click.echo("❌ File is empty.", err=True)
        sys.exit(1)

    click.echo(f"📋 Incident description loaded ({len(description)} chars)")
    _run_cli_mode(description, options)


def _start_api_server(port: int | None) -> None:
    """Start the FastAPI server."""
    import uvicorn
    from src.api.app import app

    api_port = port or get_api_port()
    click.echo(f"🌐 Starting API server on port {api_port}")
    click.echo(f"   Swagger UI: http://localhost:{api_port}/docs")
    click.echo(f"   ReDoc:       http://localhost:{api_port}/redoc")
    click.echo(f"   Health:      http://localhost:{api_port}/api/v1/health")
    click.echo()

    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=api_port,
        reload=False,
        log_level="info",
    )


def _show_extended_help() -> None:
    """Display the extended help guide with examples, providers, and tips."""
    click.echo("""
╔══════════════════════════════════════════════════════════════════════════╗
║                     EXTENDED USAGE GUIDE                                ║
╚══════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INPUT MODES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. CLI ARGUMENT MODE  (fastest — one-liner)
     $ python src/app.py -d "Ransomware detected on finance server"

  2. INTERACTIVE MODE   (guided prompts for description, severity, provider)
     $ python src/app.py -i

  3. FILE INPUT MODE    (load description from a text file)
     $ python src/app.py -f incident_description.txt

  4. API SERVER MODE    (REST API with Swagger UI)
     $ python src/app.py --serve --port 8080
     Swagger UI → http://localhost:8080/docs
     POST /api/v1/playbook with JSON body

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ALL FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Flag              Short   Description                          Default
  ─────────────────────────────────────────────────────────────────────────
  --description     -d      Incident description (CLI mode)       —
  --file            -f      Path to incident description file     —
  --interactive     -i      Start interactive CLI mode            off
  --serve           -s      Start REST API server                 off
  --severity                low | medium | high | critical        auto
  --provider                LLM provider (see table below)        config
  --format                  markdown | pdf                        markdown
  --output-dir              Directory for generated files         data/processed
  --port                    API server port                       8000
  --verbose         -v      Enable DEBUG logging                  off
  --extended-help   -H      Show this extended guide              off
  --list-providers          Show providers & API key status       off

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUPPORTED PROVIDERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Provider    Model              API Key Env Var        Local?
  ─────────────────────────────────────────────────────────────────────────
  openai      gpt-4o             OPENAI_API_KEY          No
  anthropic   claude-sonnet-4    ANTHROPIC_API_KEY       No
  deepseek    deepseek-chat      DEEPSEEK_API_KEY        No
  minimax     MiniMax-M2.7       MINIMAX_API_KEY         No
  kimi        moonshot-v1-128k   KIMI_API_KEY            No
  qwen        qwen-max           QWEN_API_KEY            No
  glm         glm-4-plus         GLM_API_KEY             No
  ollama      llama3             (none — runs locally)   Yes

  Run  python src/app.py --list-providers  to check which keys are configured.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMMON EXAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Quick playbook with auto-detected severity
  python src/app.py -d "Phishing email targeting HR department"

  # Critical incident with specific provider + PDF output
  python src/app.py -d "Data exfiltration from DB server" \\
      --severity critical --provider anthropic --format pdf

  # Interactive mode with verbose logging
  python src/app.py -i -v

  # Read from file, save to custom directory
  python src/app.py -f incidents/ransomware.txt --output-dir ./reports

  # Start API server on custom port
  python src/app.py --serve --port 9000

  # Use local Ollama (no API key needed)
  python src/app.py -d "Suspicious login from foreign IP" --provider ollama

  # Override default provider via environment
  DEFAULT_PROVIDER=deepseek python src/app.py -d "Malware on workstation"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURATION FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  .env                          API keys and app settings
                                cp .env.example .env  then fill in keys

  config/model_config.yaml      Provider models, fallback chain, retry
                                and rate-limit settings.

  config/org_profile.yaml       Your org tech stack, SIEM, EDR, teams,
                                and compliance frameworks. Set demo: false
                                after filling in your real data.

  config/prompts.yaml           Prompt templates for playbook generation.

  Example .env:
    OPENAI_API_KEY=sk-...
    ANTHROPIC_API_KEY=sk-ant-...
    DEFAULT_PROVIDER=openai
    LOG_LEVEL=INFO
    API_PORT=8000

  Example org_profile.yaml (minimal):
    demo: false
    org:
      name: "My Company"
      industry: "technology"
      size: "small"
    tech_stack:
      os: ["linux"]
      cloud_providers: ["aws"]
      siem: "splunk"
      edr: "crowdstrike"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Issue                          Fix
  ────────────────────────────────────────────────────────────────────────
  "No provider available"         Set at least one API key in .env
                                  or use --provider ollama (local)

  "Description too short"         Provide at least 10 characters

  Rate limit / 429 errors        Reduce request frequency or switch
                                  to a different provider with --provider

  PDF generation skipped         Install WeasyPrint:
                                    pip install weasyprint

  Ollama connection refused       Start Ollama first:
                                    ollama serve && ollama pull llama3

  ModuleNotFoundError             Install dependencies:
                                    pip install -r requirements.txt

  Fallback chain not working      Check config/model_config.yaml →
                                  fallback_chain section is ordered
""")


def _show_provider_status() -> None:
    """Display provider configuration status with API key availability check."""
    from src.utils.config import get_model_config

    config = get_model_config()
    providers_cfg = config.get("providers", {})
    default_provider = config.get("default_provider", "openai")
    fallback_chain = config.get("fallback_chain", [])

    click.echo("\n  Provider Status Check")
    click.echo("  ══════════════════════════════════════════════════════════════")
    click.echo(f"  Default provider : {default_provider}")
    click.echo(f"  Fallback chain   : {' → '.join(fallback_chain)}")
    click.echo()
    click.echo("  {:<12} {:<20} {:<10} {:<6} {}".format(
        "Provider", "Model", "Key Status", "Local", "Endpoint"
    ))
    click.echo("  {} {} {} {} {}".format(
        "─" * 12, "─" * 20, "─" * 10, "─" * 6, "─" * 40
    ))

    for name in SUPPORTED_PROVIDERS:
        prov_cfg = providers_cfg.get(name, {})
        model = prov_cfg.get("model", "unknown")
        api_base = prov_cfg.get("api_base", "—")
        api_key_env = prov_cfg.get("api_key_env", "")
        is_local = name == "ollama"

        # Check if API key is set in environment
        if is_local:
            key_status = "N/A"
        elif api_key_env:
            key_val = os.environ.get(api_key_env, "")
            key_status = "  ✓" if key_val.strip() else "  ✗"
        else:
            key_status = "  —"

        local_marker = "Yes" if is_local else "No"
        default_marker = " (default)" if name == default_provider else ""

        click.echo("  {:<12} {:<20} {:<10} {:<6} {}{}".format(
            name, model, key_status, local_marker, api_base, default_marker
        ))

    click.echo()
    click.echo("  Legend:  ✓ = API key set in .env   ✗ = API key missing   N/A = local provider")
    click.echo("  Tip:    Run 'python src/app.py --list-providers' anytime to check status.")
    click.echo()


if __name__ == "__main__":
    main()
