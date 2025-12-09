from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Ordered list of supported intent IDs for the fast-path router.
INTENT_IDS = [
    "resistance_biomarkers",
    "sensitivity_biomarkers",
    "therapy_targets",
    "gene_targeting_therapies",
    "gene_variants",
    "variant_response",
    "gene_overview",
    "therapy_overview",
    "disease_biomarkers",
    "disease_therapies",
    "conversational",
    "complex",
    "unclear",
]

IntentLiteral = Literal[
    "resistance_biomarkers",
    "sensitivity_biomarkers",
    "therapy_targets",
    "gene_targeting_therapies",
    "gene_variants",
    "variant_response",
    "gene_overview",
    "therapy_overview",
    "disease_biomarkers",
    "disease_therapies",
    "conversational",
    "complex",
    "unclear",
]

# Mapping of required entities per intent (used for prompt clarity and later validation).
INTENT_REQUIRED_ENTITIES: dict[IntentLiteral, list[str]] = {
    "resistance_biomarkers": ["therapy"],
    "sensitivity_biomarkers": ["therapy"],
    "therapy_targets": ["therapy"],
    "gene_targeting_therapies": ["gene"],
    "gene_variants": ["gene"],
    "variant_response": ["variant", "therapy"],
    "gene_overview": ["gene"],
    "therapy_overview": ["therapy"],
    "disease_biomarkers": ["disease"],
    "disease_therapies": ["disease"],
    "conversational": [],
    "complex": [],
    "unclear": [],
}


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
    # Optional raw payload for debugging when explicitly requested.
    # raw_model_output: dict[str, object] | None = None
