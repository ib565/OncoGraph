from __future__ import annotations

from voice_agent.contracts import (
    DiseaseBiomarkersPayload,
    DiseaseTherapiesPayload,
    GeneOverviewPayload,
    GeneTargetingTherapiesPayload,
    GeneVariantsPayload,
    ResistanceBiomarkersPayload,
    SensitivityBiomarkersPayload,
    TherapyOverviewPayload,
    TherapyTargetsPayload,
    VariantResponsePayload,
)
from voice_agent.templates.formatters import (
    build_disease_biomarkers_payload,
    build_disease_therapies_payload,
    build_gene_overview_payload,
    build_gene_targeting_therapies_payload,
    build_gene_variants_payload,
    build_resistance_biomarkers_payload,
    build_sensitivity_biomarkers_payload,
    build_therapy_overview_payload,
    build_therapy_targets_payload,
    build_variant_response_payload,
)


class TestResistanceBiomarkersPayload:
    """Tests for build_resistance_biomarkers_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_resistance_biomarkers_payload([], {"therapy": "cetuximab"}, 3)
        assert payload is None

    def test_builds_payload_with_genes(self) -> None:
        results = [
            {"gene_symbol": "KRAS", "best_evidence_level": "A", "evidence_count": 5},
            {"gene_symbol": "BRAF", "best_evidence_level": "B", "evidence_count": 3},
        ]
        payload = build_resistance_biomarkers_payload(results, {"therapy": "cetuximab"}, 3)
        assert isinstance(payload, ResistanceBiomarkersPayload)
        assert payload.intent == "resistance_biomarkers_query"
        assert payload.therapy == "cetuximab"
        assert payload.total_genes == 2
        assert len(payload.top_genes) == 2

    def test_respects_speak_top_n_cap(self) -> None:
        results = [{"gene_symbol": f"GENE{i}", "best_evidence_level": "A", "evidence_count": i} for i in range(1, 10)]
        payload = build_resistance_biomarkers_payload(results, {"therapy": "cetuximab"}, speak_top_n=2)
        assert payload is not None
        assert payload.total_genes == len(results)
        assert len(payload.top_genes) == 2


class TestSensitivityBiomarkersPayload:
    """Tests for build_sensitivity_biomarkers_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_sensitivity_biomarkers_payload([], {"therapy": "imatinib"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"gene_symbol": "BCR", "best_evidence_level": "A", "evidence_count": 10}]
        payload = build_sensitivity_biomarkers_payload(results, {"therapy": "imatinib"}, 3)
        assert isinstance(payload, SensitivityBiomarkersPayload)
        assert payload.therapy == "imatinib"
        assert payload.total_genes == 1
        assert payload.top_genes[0]["gene"] == "BCR"


class TestTherapyTargetsPayload:
    """Tests for build_therapy_targets_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_therapy_targets_payload([], {"therapy": "vemurafenib"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"gene_symbol": "BRAF", "targets_moa": "inhibitor"}]
        payload = build_therapy_targets_payload(results, {"therapy": "vemurafenib"}, 3)
        assert isinstance(payload, TherapyTargetsPayload)
        assert payload.total_targets == 1
        assert payload.targets[0]["gene"] == "BRAF"


class TestGeneTargetingTherapiesPayload:
    """Tests for build_gene_targeting_therapies_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_gene_targeting_therapies_payload([], {"gene": "BRAF"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"therapy_name": "vemurafenib", "targets_moa": "inhibitor"}]
        payload = build_gene_targeting_therapies_payload(results, {"gene": "BRAF"}, 3)
        assert isinstance(payload, GeneTargetingTherapiesPayload)
        assert payload.gene == "BRAF"
        assert payload.total_therapies == 1
        assert payload.therapies[0]["therapy"] == "vemurafenib"


class TestGeneVariantsPayload:
    """Tests for build_gene_variants_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_gene_variants_payload([], {"gene": "KRAS"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"variant_name": "G12C", "best_evidence_level": "A", "evidence_count": 4}]
        payload = build_gene_variants_payload(results, {"gene": "KRAS"}, 3)
        assert isinstance(payload, GeneVariantsPayload)
        assert payload.gene == "KRAS"
        assert payload.total_variants == 1
        assert payload.top_variants[0]["variant"] == "G12C"


class TestVariantResponsePayload:
    """Tests for build_variant_response_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_variant_response_payload([], {"variant": "V600E", "therapy": "dabrafenib"}, 3)
        assert payload is None

    def test_builds_payload_with_effects(self) -> None:
        results = [
            {
                "effect": "sensitivity",
                "disease_name": "Melanoma",
                "best_evidence_level": "A",
                "evidence_count": 10,
            },
            {
                "effect": "resistance",
                "disease_name": "Colorectal Cancer",
                "best_evidence_level": "B",
                "evidence_count": 5,
            },
        ]
        payload = build_variant_response_payload(results, {"variant": "V600E", "therapy": "dabrafenib"}, 3)
        assert isinstance(payload, VariantResponsePayload)
        assert payload.variant == "V600E"
        assert payload.therapy == "dabrafenib"
        effects = {item["effect"] for item in payload.results}
        assert "sensitivity" in effects
        assert "resistance" in effects


class TestGeneOverviewPayload:
    """Tests for build_gene_overview_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_gene_overview_payload([], {"gene": "KRAS"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"gene_symbol": "KRAS", "variant_count": 10, "therapy_count": 5}]
        payload = build_gene_overview_payload(results, {"gene": "KRAS"}, 3)
        assert isinstance(payload, GeneOverviewPayload)
        assert payload.gene == "KRAS"
        assert payload.variant_count == 10
        assert payload.therapy_count == 5


class TestTherapyOverviewPayload:
    """Tests for build_therapy_overview_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_therapy_overview_payload([], {"therapy": "cetuximab"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [
            {
                "therapy_name": "cetuximab",
                "target_count": 2,
                "biomarker_count": 20,
                "gene_symbol": "EGFR",
                "targets_moa": "inhibitor",
            },
            {
                "therapy_name": "cetuximab",
                "target_count": 2,
                "biomarker_count": 20,
                "gene_symbol": "KRAS",
                "targets_moa": "inhibitor",
            },
        ]
        payload = build_therapy_overview_payload(results, {"therapy": "cetuximab"}, 3)
        assert isinstance(payload, TherapyOverviewPayload)
        assert payload.therapy == "cetuximab"
        assert payload.target_count == 2
        assert payload.biomarker_count == 20
        assert len(payload.targets) <= 3


class TestDiseaseBiomarkersPayload:
    """Tests for build_disease_biomarkers_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_disease_biomarkers_payload([], {"disease": "lung cancer"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"gene_symbol": "EGFR", "best_evidence_level": "A", "evidence_count": 10}]
        payload = build_disease_biomarkers_payload(results, {"disease": "lung cancer"}, 3)
        assert isinstance(payload, DiseaseBiomarkersPayload)
        assert payload.disease == "lung cancer"
        assert payload.total_genes == 1
        assert payload.top_genes[0]["gene"] == "EGFR"


class TestDiseaseTherapiesPayload:
    """Tests for build_disease_therapies_payload."""

    def test_empty_results_returns_none(self) -> None:
        payload = build_disease_therapies_payload([], {"disease": "colorectal cancer"}, 3)
        assert payload is None

    def test_builds_payload(self) -> None:
        results = [{"therapy_name": "cetuximab", "evidence_count": 10}]
        payload = build_disease_therapies_payload(results, {"disease": "colorectal cancer"}, 3)
        assert isinstance(payload, DiseaseTherapiesPayload)
        assert payload.disease == "colorectal cancer"
        assert payload.total_therapies == 1
        assert payload.therapies[0]["therapy"] == "cetuximab"
