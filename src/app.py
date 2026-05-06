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
) -> None:
    """Incident Response Playbook Generator — AI-powered NIST playbooks."""
    ctx.ensure_object(dict)

    # Setup
    log_level = "DEBUG" if verbose else get_log_level()
    setup_logging(log_level)
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


if __name__ == "__main__":
    main()
