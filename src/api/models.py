"""Pydantic models for the API request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PlaybookRequest(BaseModel):
    """Request model for playbook generation."""

    incident_description: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Free-text description of the security incident.",
        examples=[
            "We detected ransomware on the finance server. Files are being encrypted "
            "with a .locked extension. The infection appears to have started from a "
            "phishing email received by an employee in the accounting department."
        ],
    )
    severity: str | None = Field(
        None,
        description="Severity level: low, medium, high, critical. Inferred if not provided.",
    )
    provider: str | None = Field(
        None,
        description="LLM provider to use for this request. Uses default if not specified.",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        """Validate severity level."""
        if v is None:
            return v
        valid = {"low", "medium", "high", "critical"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid severity '{v}'. Use: {', '.join(sorted(valid))}")
        return v.lower()


class PlaybookResponse(BaseModel):
    """Response model for playbook generation."""

    success: bool
    playbook: str | None = None
    classification: dict[str, Any] | None = None
    provider_used: str | None = None
    generated_at: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent_enabled: bool
    providers: dict[str, bool]


class ProviderHealthResponse(BaseModel):
    """Provider health check response."""

    providers: dict[str, bool]
    default_provider: str
