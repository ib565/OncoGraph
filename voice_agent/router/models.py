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

# Descriptions of what each intent represents (used in router prompts).
INTENT_DESCRIPTIONS: dict[IntentLiteral, str] = {
    "resistance_biomarkers_query": "Find genes whose variants predict resistance to a specific therapy",
    "sensitivity_biomarkers_query": "Find genes whose variants predict sensitivity to a specific therapy",
    "therapy_targets_query": "What genes does a therapy target via TARGETS relationship",
    "gene_targeting_therapies_query": "What therapies target a specific gene",
    "gene_variants_query": "List variants of a gene that have clinical evidence in the database",
    "variant_response_query": "How does a specific variant affect response to a specific therapy",
    "gene_overview_query": ("General summary statistics about a gene (variant count, therapies targeting it)"),
    "therapy_overview_query": (
        "General summary statistics about a therapy " "(modality, target genes, biomarker associations)"
    ),
    "disease_biomarkers_query": "Top biomarker genes for a specific disease",
    "disease_therapies_query": "Therapies with biomarker evidence in a specific disease",
    "conversational": ("Greetings, thanks, goodbyes, or off-topic chat that doesn't require database queries"),
    "complex": (
        "Multi-entity comparisons, exclusions, or queries requiring " "complex analysis beyond simple template matching"
    ),
    "unclear": "Cannot determine intent from the query - too vague, gibberish, or unclassifiable",
}

# Example queries for each intent (used in router prompts for clarity).
INTENT_EXAMPLES: dict[IntentLiteral, str] = {
    "resistance_biomarkers_query": "Which genes cause resistance to cetuximab?",
    "sensitivity_biomarkers_query": "What predicts sensitivity to imatinib?",
    "therapy_targets_query": "What does vemurafenib target?",
    "gene_targeting_therapies_query": "What therapies target BRAF?",
    "gene_variants_query": "What variants of KRAS have evidence?",
    "variant_response_query": "Does BRAF V600E respond to dabrafenib?",
    "gene_overview_query": "Tell me about EGFR",
    "therapy_overview_query": "Tell me about cetuximab",
    "disease_biomarkers_query": "What biomarkers matter in lung cancer?",
    "disease_therapies_query": "What therapies have evidence in colorectal cancer?",
    "conversational": "Hello",
    "complex": "Compare resistance profiles for cetuximab and panitumumab",
    "unclear": "asdfghjkl",
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
