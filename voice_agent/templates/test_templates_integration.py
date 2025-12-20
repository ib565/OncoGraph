from __future__ import annotations

import os
import time

import pytest
from dotenv import load_dotenv

from pipeline import Neo4jExecutor, PipelineConfig
from voice_agent.entities.index import EntityIndex
from voice_agent.router.models import ExtractedEntities
from voice_agent.templates import fill_template, get_template

# Load .env before skipif decorators are evaluated
load_dotenv()


@pytest.fixture(scope="module")
def executor() -> Neo4jExecutor:
    """Create Neo4jExecutor for integration tests."""
    config = PipelineConfig()
    return Neo4jExecutor(
        uri=os.environ["NEO4J_URI"].strip(),
        user=os.environ["NEO4J_USER"].strip(),
        password=os.environ["NEO4J_PASSWORD"].strip(),
        config=config,
    )


@pytest.fixture(scope="module")
def entity_index(executor: Neo4jExecutor) -> EntityIndex:
    """Create EntityIndex for normalization in integration tests."""
    return EntityIndex(executor)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_resistance_biomarkers_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test resistance_biomarkers_query template against real Neo4j."""
    template = get_template("resistance_biomarkers_query")
    assert template is not None

    # Normalize entities
    entities = ExtractedEntities(therapy="cetuximab")
    normalized = entity_index.normalize_entities(entities)

    # Fill template
    cypher = fill_template(template, normalized)

    # Execute query
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    # Verify results structure
    assert isinstance(results, list)
    if results:
        row = results[0]
        assert "gene_symbol" in row
        assert "therapy_name" in row
        assert "effect" in row
        assert row.get("effect") == "resistance"

    # Verify timing (target <500ms)
    assert duration_ms < 2000, f"Query took {duration_ms}ms, expected <2000ms"
    print(f"resistance_biomarkers_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_sensitivity_biomarkers_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test sensitivity_biomarkers_query template against real Neo4j."""
    template = get_template("sensitivity_biomarkers_query")
    assert template is not None

    entities = ExtractedEntities(therapy="imatinib")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert results[0].get("effect") == "sensitivity"

    assert duration_ms < 2000
    print(f"sensitivity_biomarkers_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_therapy_targets_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test therapy_targets_query template against real Neo4j."""
    template = get_template("therapy_targets_query")
    assert template is not None

    entities = ExtractedEntities(therapy="vemurafenib")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "gene_symbol" in results[0]
        assert "targets_moa" in results[0]

    assert duration_ms < 2000
    print(f"therapy_targets_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_gene_targeting_therapies_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test gene_targeting_therapies_query template against real Neo4j."""
    template = get_template("gene_targeting_therapies_query")
    assert template is not None

    entities = ExtractedEntities(gene="BRAF")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "therapy_name" in results[0]
        assert "targets_moa" in results[0]

    assert duration_ms < 2000
    print(f"gene_targeting_therapies_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_gene_variants_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test gene_variants_query template against real Neo4j."""
    template = get_template("gene_variants_query")
    assert template is not None

    entities = ExtractedEntities(gene="KRAS")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "variant_name" in results[0]
        assert "gene_symbol" in results[0]

    assert duration_ms < 2000
    print(f"gene_variants_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_variant_response_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test variant_response_query template against real Neo4j."""
    template = get_template("variant_response_query")
    assert template is not None

    entities = ExtractedEntities(variant="V600E", therapy="dabrafenib")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "effect" in results[0]
        assert "therapy_name" in results[0]

    assert duration_ms < 2000
    print(f"variant_response_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_gene_overview_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test gene_overview_query template against real Neo4j."""
    template = get_template("gene_overview_query")
    assert template is not None

    entities = ExtractedEntities(gene="EGFR")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "gene_symbol" in results[0]
        assert "variant_count" in results[0] or "therapy_count" in results[0]

    assert duration_ms < 2000
    print(f"gene_overview_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_therapy_overview_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test therapy_overview_query template against real Neo4j."""
    template = get_template("therapy_overview_query")
    assert template is not None

    entities = ExtractedEntities(therapy="cetuximab")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "therapy_name" in results[0]
        assert "target_count" in results[0] or "biomarker_count" in results[0]

    assert duration_ms < 2000
    print(f"therapy_overview_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_disease_biomarkers_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test disease_biomarkers_query template against real Neo4j."""
    template = get_template("disease_biomarkers_query")
    assert template is not None

    entities = ExtractedEntities(disease="colorectal cancer")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "gene_symbol" in results[0]
        assert "best_evidence_level" in results[0]

    assert duration_ms < 2000
    print(f"disease_biomarkers_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_disease_therapies_template(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test disease_therapies_query template against real Neo4j."""
    template = get_template("disease_therapies_query")
    assert template is not None

    entities = ExtractedEntities(disease="lung cancer")
    normalized = entity_index.normalize_entities(entities)

    cypher = fill_template(template, normalized)
    start = time.perf_counter()
    results = executor.execute_read(cypher)
    duration_ms = int((time.perf_counter() - start) * 1000)

    assert isinstance(results, list)
    if results:
        assert "therapy_name" in results[0]
        assert "evidence_count" in results[0]

    assert duration_ms < 2000
    print(f"disease_therapies_query: {len(results)} results in {duration_ms}ms")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_all_templates_execute_without_errors(executor: Neo4jExecutor, entity_index: EntityIndex) -> None:
    """Test that all templates can be filled and executed without Cypher errors."""
    from voice_agent.templates import TEMPLATES

    test_cases = [
        ("resistance_biomarkers_query", ExtractedEntities(therapy="cetuximab")),
        ("sensitivity_biomarkers_query", ExtractedEntities(therapy="imatinib")),
        ("therapy_targets_query", ExtractedEntities(therapy="vemurafenib")),
        ("gene_targeting_therapies_query", ExtractedEntities(gene="BRAF")),
        ("gene_variants_query", ExtractedEntities(gene="KRAS")),
        ("variant_response_query", ExtractedEntities(variant="V600E", therapy="dabrafenib")),
        ("gene_overview_query", ExtractedEntities(gene="EGFR")),
        ("therapy_overview_query", ExtractedEntities(therapy="cetuximab")),
        ("disease_biomarkers_query", ExtractedEntities(disease="colorectal cancer")),
        ("disease_therapies_query", ExtractedEntities(disease="lung cancer")),
    ]

    for intent_id, entities in test_cases:
        template = TEMPLATES.get(intent_id)
        assert template is not None, f"Template {intent_id} not found"

        normalized = entity_index.normalize_entities(entities)
        cypher = fill_template(template, normalized)

        # Execute query - should not raise exception
        try:
            results = executor.execute_read(cypher)
            assert isinstance(results, list)
            print(f"✓ {intent_id}: {len(results)} results")
        except Exception as e:
            pytest.fail(f"Template {intent_id} failed with error: {e}")
