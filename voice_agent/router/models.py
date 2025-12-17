from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Ordered list of supported intent IDs for the fast-path router.
INTENT_IDS = [
    "resistance_biomarkers_query",
    "sensitivity_biomarkers_query",
    "therapy_targets_query",
    "gene_targeting_therapies_query",
    "gene_variants_query",
    "variant_response_query",
    "gene_overview_query",
    "therapy_overview_query",
    "disease_biomarkers_query",
    "disease_therapies_query",
    "conversational",
    "complex",
    "unclear",
]

IntentLiteral = Literal[
    "resistance_biomarkers_query",
    "sensitivity_biomarkers_query",
    "therapy_targets_query",
    "gene_targeting_therapies_query",
    "gene_variants_query",
    "variant_response_query",
    "gene_overview_query",
    "therapy_overview_query",
    "disease_biomarkers_query",
    "disease_therapies_query",
    "conversational",
    "complex",
    "unclear",
]

# Mapping of required entities per intent (used for prompt clarity and later validation).
INTENT_REQUIRED_ENTITIES: dict[IntentLiteral, list[str]] = {
    "resistance_biomarkers_query": ["therapy"],
    "sensitivity_biomarkers_query": ["therapy"],
    "therapy_targets_query": ["therapy"],
    "gene_targeting_therapies_query": ["gene"],
    "gene_variants_query": ["gene"],
    "variant_response_query": ["variant", "therapy"],
    "gene_overview_query": ["gene"],
    "therapy_overview_query": ["therapy"],
    "disease_biomarkers_query": ["disease"],
    "disease_therapies_query": ["disease"],
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
