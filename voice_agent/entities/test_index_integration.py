from __future__ import annotations

import os
import time

import pytest
from dotenv import load_dotenv

from pipeline import Neo4jExecutor, PipelineConfig
from voice_agent.entities.index import EntityIndex

# Load .env before skipif decorators are evaluated
load_dotenv()


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_entity_index_builds_against_real_neo4j() -> None:
    """Build EntityIndex against a real Neo4j instance and sanity check it.

    This test assumes the same environment variables as the main API/CLI:
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
    """

    config = PipelineConfig()
    executor = Neo4jExecutor(
        uri=os.environ["NEO4J_URI"].strip(),
        user=os.environ["NEO4J_USER"].strip(),
        password=os.environ["NEO4J_PASSWORD"].strip(),
        config=config,
    )

    start = time.perf_counter()
    index = EntityIndex(executor)
    build_ms = int((time.perf_counter() - start) * 1000)

    # Basic shape checks – indexes should not be empty on a populated graph
    assert isinstance(index.genes_index, dict)
    assert isinstance(index.therapies_index, dict)
    assert isinstance(index.diseases_index, dict)

    # If the database is populated, expect some entries; if not,
    # this still validates that the queries execute without error.
    # We log the sizes for debugging.
    sizes = {
        "genes": len(index.genes_index),
        "therapies": len(index.therapies_index),
        "diseases": len(index.diseases_index),
        "build_ms": build_ms,
    }
    print(f"EntityIndex integration sizes: {sizes}")

    # Soft timing assertion – should typically be under 5000 ms
    assert build_ms < 5000


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_USER") or not os.getenv("NEO4J_PASSWORD"),
    reason="Neo4j connection details not configured in environment",
)
def test_entity_index_normalization_sanity() -> None:
    """Sanity-check that at least a few well-known entities normalize correctly.

    The exact symbols/names depend on the database contents; adjust expectations
    here if your graph schema or seed data changes.
    """

    config = PipelineConfig()
    executor = Neo4jExecutor(
        uri=os.environ["NEO4J_URI"].strip(),
        user=os.environ["NEO4J_USER"].strip(),
        password=os.environ["NEO4J_PASSWORD"].strip(),
        config=config,
    )
    index = EntityIndex(executor)

    # These checks are intentionally loose: they only run when the DB is
    # configured and populated with standard OncoGraph data.
    # If needed, update the expected names to match your seed data.
    maybe_kras = index.normalize_entity("gene", "kras")
    if maybe_kras is not None:
        assert maybe_kras == maybe_kras.upper()

    maybe_cetuximab = index.normalize_entity("therapy", "Cetuximab")
    if maybe_cetuximab is not None:
        assert maybe_cetuximab == maybe_cetuximab.lower()

    # Diseases can fall back to input when not found; just ensure call succeeds.
    assert index.normalize_entity("disease", "colorectal cancer") is not None
