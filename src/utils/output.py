"""Output rendering — Markdown and PDF generation."""

import logging
from pathlib import Path

from src.utils.config import PROJECT_ROOT
from src.utils.helpers import ensure_directory, generate_timestamp, sanitize_filename

logger = logging.getLogger(__name__)


def render_markdown(
    playbook: str,
    incident_type: str,
    output_dir: str | None = None,
) -> Path:
    """Save the playbook as a Markdown file.

    Args:
        playbook: The playbook text content.
        incident_type: Type of incident for filename.
        output_dir: Optional output directory override.

    Returns:
        Path to the saved Markdown file.
    """
    out_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "data" / "processed"
    ensure_directory(out_dir)

    timestamp = generate_timestamp()
    safe_type = sanitize_filename(incident_type)
    filename = f"playbook_{safe_type}_{timestamp}.md"
    filepath = out_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(playbook)

    logger.info("Playbook saved: %s", filepath)
    return filepath


def render_pdf(
    playbook: str,
    incident_type: str,
    output_dir: str | None = None,
) -> Path | None:
    """Convert the playbook Markdown to PDF via WeasyPrint.

    Falls back gracefully if WeasyPrint is not installed.

    Args:
        playbook: The playbook text content.
        incident_type: Type of incident for filename.
        output_dir: Optional output directory override.

    Returns:
        Path to the saved PDF file, or None if WeasyPrint unavailable.
    """
    try:
        from weasyprint import HTML
        import markdown
    except ImportError:
        logger.warning(
            "WeasyPrint or markdown not installed. Install with: "
            "pip install weasyprint markdown"
        )
        return None

    out_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "data" / "processed"
    ensure_directory(out_dir)

    timestamp = generate_timestamp()
    safe_type = sanitize_filename(incident_type)
    filename = f"playbook_{safe_type}_{timestamp}.pdf"
    filepath = out_dir / filename

    # Convert Markdown to HTML
    try:
        html_content = markdown.markdown(
            playbook,
            extensions=["tables", "fenced_code", "codehilite"],
        )
    except Exception as e:
        logger.warning("Markdown to HTML conversion failed: %s", e)
        html_content = f"<pre>{playbook}</pre>"

    # Wrap in basic HTML with styling
    styled_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        color: #333;
    }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 10px; }}
    h2 {{ color: #16213e; border-bottom: 1px solid #0f3460; padding-bottom: 5px; }}
    h3 {{ color: #0f3460; }}
    code {{
        background: #f4f4f4;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Fira Code', 'Consolas', monospace;
        font-size: 0.9em;
    }}
    pre {{
        background: #1a1a2e;
        color: #e0e0e0;
        padding: 15px;
        border-radius: 5px;
        overflow-x: auto;
    }}
    pre code {{
        background: none;
        color: inherit;
    }}
    blockquote {{
        border-left: 4px solid #e94560;
        margin-left: 0;
        padding-left: 15px;
        color: #555;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin: 15px 0;
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 8px 12px;
        text-align: left;
    }}
    th {{
        background: #1a1a2e;
        color: white;
    }}
    tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""

    try:
        HTML(string=styled_html).write_pdf(filepath)
        logger.info("PDF playbook saved: %s", filepath)
        return filepath
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        return None
