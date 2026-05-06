# Technical Decisions

## Decision: Language
- **Chosen:** Python 3.13
- **Alternatives considered:** Node.js, Go
- **Justification:** Python has the strongest LLM ecosystem (litellm, langchain, openai SDK), best Markdown/PDF libraries, and is the standard language for security tooling.

## Decision: Framework
- **Chosen:** FastAPI (API) + Click (CLI)
- **Alternatives considered:** Flask, Streamlit, pure CLI
- **Justification:** FastAPI provides async support, auto-generated Swagger docs, and type-safe request/response models. Click provides a clean CLI experience with subcommands and interactive prompts.

## Decision: UI/Demo
- **Chosen:** REST API + Swagger UI + CLI interactive mode
- **Alternatives considered:** Streamlit dashboard, Gradio
- **Justification:** API-first approach demonstrates production-readiness. Swagger gives instant documentation. CLI mode is essential for security teams who work in terminals.

## Decision: Persistence
- **Chosen:** YAML files (config) + Markdown/PDF output
- **Alternatives considered:** SQLite, PostgreSQL, ChromaDB
- **Justification:** No database complexity needed. Config in YAML is human-readable and versionable. Output as Markdown/PDF is the natural format for playbooks.

## Decision: LLM Provider Integration
- **Chosen:** litellm as unified provider interface
- **Alternatives considered:** Direct SDK per provider, langchain
- **Justification:** litellm provides a single interface for 100+ providers with built-in fallback, streaming, and cost tracking. Avoids vendor lock-in and reduces code complexity.

## Decision: PDF Generation
- **Chosen:** WeasyPrint
- **Alternatives considered:** reportlab, pdfkit, fpdf
- **Justification:** WeasyPrint converts HTML/CSS to PDF with the best typography support. Markdown → HTML → PDF pipeline is clean and customizable. Falls back gracefully if not installed.

## Decision: Testing
- **Chosen:** pytest + pytest-asyncio
- **Alternatives considered:** unittest, nose
- **Justification:** pytest is the Python standard with better assertions, fixtures, and plugin ecosystem. pytest-asyncio handles async FastAPI tests.

## Decision: CI/CD
- **Chosen:** None (for now)
- **Alternatives considered:** GitHub Actions
- **Justification:** Portfolio project, not production service. Tests run locally. CI can be added later.
