"""FastAPI application for the Incident Response Playbook Generator."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    HealthResponse,
    PlaybookRequest,
    PlaybookResponse,
    ProviderHealthResponse,
)
from src.agent.chains.playbook_generator import generate_playbook
from src.guardrails.input_validation import validate_playbook_request
from src.inference.engine import InferenceEngine
from src.utils.config import is_agent_enabled, get_api_port

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Incident Response Playbook Generator",
    description=(
        "AI-powered agent that generates customized incident response playbooks "
        "following NIST SP 800-61 Rev. 3. Supports multiple LLM providers with automatic "
        "fallback."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Check if the API and LLM providers are healthy."""
    engine = InferenceEngine()
    providers = engine.check_provider_health()

    return HealthResponse(
        status="ok" if is_agent_enabled() else "disabled",
        agent_enabled=is_agent_enabled(),
        providers=providers,
    )


@app.post("/api/v1/playbook", response_model=PlaybookResponse)
async def create_playbook(request: PlaybookRequest):
    """Generate an incident response playbook.

    Accepts an incident description and optional parameters, returns a
    structured NIST playbook with all 5 phases.
    """
    if not is_agent_enabled():
        raise HTTPException(
            status_code=503,
            detail="Agent is currently disabled. Check config/model_config.yaml.",
        )

    # Validate input
    validation = validate_playbook_request(
        description=request.incident_description,
        severity=request.severity,
        provider=request.provider,
    )

    if not validation.is_valid:
        raise HTTPException(status_code=422, detail=validation.errors)

    # Generate playbook
    engine = InferenceEngine(provider_override=validation.provider)
    result = generate_playbook(
        engine=engine,
        description=validation.sanitized_description,
        severity=validation.severity,
        provider=validation.provider,
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return PlaybookResponse(
        success=True,
        playbook=result["playbook"],
        classification=result["classification"],
        provider_used=result["provider_used"],
        generated_at=result["generated_at"],
        warnings=validation.warnings,
    )


@app.get("/api/v1/providers", response_model=ProviderHealthResponse)
async def check_providers():
    """Check which LLM providers are available."""
    engine = InferenceEngine()
    providers = engine.check_provider_health()

    return ProviderHealthResponse(
        providers=providers,
        default_provider=engine.fallback_chain[0] if engine.fallback_chain else "none",
    )
