from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime intent identifier (kept as str to avoid drift with template registry).
IntentLiteral = str


class ExtractedEntities(BaseModel):
    """Entities pulled from the user transcript."""

    gene: str | None = None
    therapy: str | None = None
    disease: str | None = None
    variant: str | None = None


class RouteResult(BaseModel):
    """Structured router output returned by the LLM or fallback."""

    intent: IntentLiteral
    confidence: float = Field(ge=0.0, le=1.0)
    entities: ExtractedEntities
