from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from voice_agent.router.models import ExtractedEntities

# Overall status of a tool invocation
Status = Literal[
    "ok",
    "needs_clarification",
    "no_results",
    "not_supported",
    "error",
]

# Reuse ExtractedEntities from router as the normalized entity container
NormalizedEntities = ExtractedEntities


class VoiceHint(BaseModel):
    """Hints for voice output formatting.

    The conversational LLM can use these to decide how many top items to speak.
    """

    speak_top_n: int = Field(default=3, ge=1, le=10)


class ResistanceBiomarkersPayload(BaseModel):
    intent: Literal["resistance_biomarkers_query"]
    therapy: str
    disease: str | None = None
    total_genes: int
    top_genes: list[dict[str, str | int | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"gene": str, "best_level": str | None, "evidence_count": int}


class SensitivityBiomarkersPayload(BaseModel):
    intent: Literal["sensitivity_biomarkers_query"]
    therapy: str
    disease: str | None = None
    total_genes: int
    top_genes: list[dict[str, str | int | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"gene": str, "best_level": str | None, "evidence_count": int}


class TherapyTargetsPayload(BaseModel):
    intent: Literal["therapy_targets_query"]
    therapy: str
    total_targets: int
    targets: list[dict[str, str | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"gene": str, "moa": str | None}


class GeneTargetingTherapiesPayload(BaseModel):
    intent: Literal["gene_targeting_therapies_query"]
    gene: str
    total_therapies: int
    therapies: list[dict[str, str | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"therapy": str, "moa": str | None}


class GeneVariantsPayload(BaseModel):
    intent: Literal["gene_variants_query"]
    gene: str
    total_variants: int
    top_variants: list[dict[str, str | int | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"variant": str, "best_level": str | None, "evidence_count": int}


class VariantResponsePayload(BaseModel):
    intent: Literal["variant_response_query"]
    variant: str
    therapy: str
    results: list[dict[str, str | int | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"effect": "sensitivity" | "resistance", "disease": str | None,
    #             "best_level": str | None, "evidence_count": int}


class GeneOverviewPayload(BaseModel):
    intent: Literal["gene_overview_query"]
    gene: str
    variant_count: int
    therapy_count: int


class TherapyOverviewPayload(BaseModel):
    intent: Literal["therapy_overview_query"]
    therapy: str
    target_count: int
    biomarker_count: int
    targets: list[dict[str, str | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"gene": str, "moa": str | None}


class DiseaseBiomarkersPayload(BaseModel):
    intent: Literal["disease_biomarkers_query"]
    disease: str
    total_genes: int
    top_genes: list[dict[str, str | int | None]] = Field(default_factory=list, max_length=5)
    # Each item: {"gene": str, "best_level": str | None, "evidence_count": int}


class DiseaseTherapiesPayload(BaseModel):
    intent: Literal["disease_therapies_query"]
    disease: str
    total_therapies: int
    therapies: list[dict[str, int | str]] = Field(default_factory=list, max_length=5)
    # Each item: {"therapy": str, "evidence_count": int}


Payload = Annotated[
    ResistanceBiomarkersPayload | SensitivityBiomarkersPayload | TherapyTargetsPayload | GeneTargetingTherapiesPayload | GeneVariantsPayload | VariantResponsePayload | GeneOverviewPayload | TherapyOverviewPayload | DiseaseBiomarkersPayload | DiseaseTherapiesPayload,
    Field(discriminator="intent"),
]


class OncoGraphToolResult(BaseModel):
    """Structured result from the OncoGraph fast-path query tool."""

    status: Status
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: NormalizedEntities = Field(default_factory=NormalizedEntities)
    message: str | None = None
    voice: VoiceHint = Field(default_factory=VoiceHint)
    payload: Payload | None = None


__all__ = [
    "Status",
    "NormalizedEntities",
    "VoiceHint",
    "ResistanceBiomarkersPayload",
    "SensitivityBiomarkersPayload",
    "TherapyTargetsPayload",
    "GeneTargetingTherapiesPayload",
    "GeneVariantsPayload",
    "VariantResponsePayload",
    "GeneOverviewPayload",
    "TherapyOverviewPayload",
    "DiseaseBiomarkersPayload",
    "DiseaseTherapiesPayload",
    "Payload",
    "OncoGraphToolResult",
]


