from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from pipeline.types import PipelineError
from voice_agent.entities import EntityIndex
from voice_agent.router.models import ExtractedEntities


@dataclass
class FakeExecutor:
    """Minimal Neo4jExecutor-like stub for testing EntityIndex.

    It captures the last executed Cypher query and returns predefined rows.
    """

    rows_by_cypher: dict[str, list[dict[str, Any]]]

    def execute_read(self, cypher: str) -> list[dict[str, Any]]:  # type: ignore[override]
        if cypher not in self.rows_by_cypher:
            raise PipelineError(f"Unexpected Cypher in FakeExecutor: {cypher}", step="test_execute_read")
        return self.rows_by_cypher[cypher]


GENES_CYPHER = """MATCH (g:Gene) RETURN g.symbol AS symbol, g.synonyms AS synonyms""".strip()
THERAPIES_CYPHER = """MATCH (t:Therapy) RETURN t.name AS name, t.synonyms AS synonyms""".strip()
DISEASES_CYPHER = """MATCH (d:Disease) RETURN d.name AS name, d.synonyms AS synonyms""".strip()


def _build_basic_index() -> EntityIndex:
    executor = FakeExecutor(
        rows_by_cypher={
            GENES_CYPHER: [
                {"symbol": "KRAS", "synonyms": ["KRAS2", "RASK2"]},
                {"symbol": "BRAF", "synonyms": None},
            ],
            THERAPIES_CYPHER: [
                {"name": "Cetuximab", "synonyms": ["Erbitux"]},
                {"name": "Imatinib", "synonyms": []},
            ],
            DISEASES_CYPHER: [
                {"name": "Colorectal Carcinoma", "synonyms": ["Colorectal Cancer", "CRC"]},
                {"name": "Lung Cancer", "synonyms": None},
            ],
        }
    )
    return EntityIndex(executor)  # type: ignore[arg-type]


def test_build_indexes_populates_mappings() -> None:
    index = _build_basic_index()

    # Genes
    assert index.genes_index["kras"] == "KRAS"
    assert index.genes_index["kras2"] == "KRAS"
    assert index.genes_index["rask2"] == "KRAS"
    assert index.genes_index["braf"] == "BRAF"

    # Therapies
    assert index.therapies_index["cetuximab"] == "cetuximab"
    assert index.therapies_index["erbitux"] == "cetuximab"
    assert index.therapies_index["imatinib"] == "imatinib"

    # Diseases
    assert index.diseases_index["colorectal carcinoma"] == "Colorectal Carcinoma"
    assert index.diseases_index["colorectal cancer"] == "Colorectal Carcinoma"
    assert index.diseases_index["crc"] == "Colorectal Carcinoma"
    assert index.diseases_index["lung cancer"] == "Lung Cancer"


def test_normalize_entity_gene_and_therapy() -> None:
    index = _build_basic_index()

    assert index.normalize_entity("gene", "KRAS") == "KRAS"
    assert index.normalize_entity("gene", "kras2") == "KRAS"
    assert index.normalize_entity("gene", "unknown") is None

    assert index.normalize_entity("therapy", "Cetuximab") == "cetuximab"
    assert index.normalize_entity("therapy", "erbitux") == "cetuximab"
    assert index.normalize_entity("therapy", "unknown") is None


def test_normalize_entity_disease_and_variant() -> None:
    index = _build_basic_index()

    # Exact and synonym hits
    assert index.normalize_entity("disease", "colorectal carcinoma") == "Colorectal Carcinoma"
    assert index.normalize_entity("disease", "CRC") == "Colorectal Carcinoma"

    # Not in index: should return cleaned input as-is
    assert index.normalize_entity("disease", "Rare Cancer ") == "Rare Cancer"

    # Variant passthrough
    assert index.normalize_entity("variant", "G12C") == "G12C"


def test_normalize_entity_empty_and_unknown_type(caplog: pytest.LogCaptureFixture) -> None:
    index = _build_basic_index()

    assert index.normalize_entity("gene", None) is None
    assert index.normalize_entity("gene", "  ") is None

    with caplog.at_level("WARNING"):
        assert index.normalize_entity("unknown", "value") is None
        assert any("Unknown entity type" in record.getMessage() for record in caplog.records)


def test_normalize_entities_wrapper() -> None:
    index = _build_basic_index()

    entities = ExtractedEntities(gene="kras", therapy="CETUXIMAB", disease="crc", variant="V600E")
    normalized = index.normalize_entities(entities)

    assert normalized.gene == "KRAS"
    assert normalized.therapy == "cetuximab"
    assert normalized.disease == "Colorectal Carcinoma"
    assert normalized.variant == "V600E"


def test_ambiguity_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    executor = FakeExecutor(
        rows_by_cypher={
            GENES_CYPHER: [
                {"symbol": "GENE1", "synonyms": ["ABC"]},
                {"symbol": "GENE2", "synonyms": ["ABC"]},
            ],
            THERAPIES_CYPHER: [],
            DISEASES_CYPHER: [],
        }
    )

    with caplog.at_level("WARNING"):
        index = EntityIndex(executor)  # type: ignore[arg-type]

    # First mapping should be kept, second ignored with warning
    assert index.genes_index["abc"] == "GENE1"
    assert any("Ambiguous gene synonym" in record.getMessage() for record in caplog.records)


def test_empty_results_log_warnings(caplog: pytest.LogCaptureFixture) -> None:
    executor = FakeExecutor(
        rows_by_cypher={
            GENES_CYPHER: [],
            THERAPIES_CYPHER: [],
            DISEASES_CYPHER: [],
        }
    )

    with caplog.at_level("WARNING"):
        index = EntityIndex(executor)  # type: ignore[arg-type]

    assert index.genes_index == {}
    assert index.therapies_index == {}
    assert index.diseases_index == {}
    messages = [record.getMessage() for record in caplog.records]
    assert "Genes index query returned no rows" in messages
    assert "Therapies index query returned no rows" in messages
    assert "Diseases index query returned no rows" in messages
