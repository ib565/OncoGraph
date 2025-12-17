from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from voice_agent.router.classifier import GeminiRouter, route_query
from voice_agent.router.models import ExtractedEntities

# Load .env for integration tests
try:
    from dotenv import load_dotenv

    # Load .env from project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not available, skip


def _extract_query_from_prompt(prompt: str) -> str:
    """Extract user query from the prompt."""
    # Look for "User query: " line
    for line in prompt.splitlines():
        if "User query:" in line:
            # Extract text between quotes
            parts = line.split('"')
            if len(parts) >= 2:
                return parts[1]
    return ""


@pytest.fixture()
def stub_router(monkeypatch) -> GeminiRouter:
    responses = {
        "Which genes predict resistance to cetuximab?": ("resistance_biomarkers_query", {"therapy": "cetuximab"}),
        "What does vemurafenib target?": ("therapy_targets_query", {"therapy": "vemurafenib"}),
        "What therapies target BRAF?": ("gene_targeting_therapies_query", {"gene": "BRAF"}),
        "Tell me about EGFR": ("gene_overview_query", {"gene": "EGFR"}),
        "What variants of KRAS have clinical evidence?": ("gene_variants_query", {"gene": "KRAS"}),
        "Does BRAF V600E respond to dabrafenib?": (
            "variant_response_query",
            {"variant": "V600E", "therapy": "dabrafenib", "gene": "BRAF"},
        ),
        "What predicts sensitivity to imatinib in leukemia?": (
            "sensitivity_biomarkers_query",
            {"therapy": "imatinib", "disease": "leukemia"},
        ),
        "What biomarkers matter in lung cancer?": ("disease_biomarkers_query", {"disease": "lung cancer"}),
        "What therapies have evidence in colorectal cancer?": (
            "disease_therapies_query",
            {"disease": "colorectal cancer"},
        ),
        "Tell me about cetuximab": ("therapy_overview_query", {"therapy": "cetuximab"}),
        "Compare resistance profiles for cetuximab and panitumumab": ("complex", {}),
        "Hello": ("conversational", {}),
        "asdfghjkl": ("unclear", {}),
    }

    def fake_call(prompt: str) -> str:
        """Fake _call_model that extracts query and returns stubbed response."""
        query = _extract_query_from_prompt(prompt)
        intent, entities = responses.get(query, ("unclear", {}))
        payload = {
            "intent": intent,
            "confidence": 0.9,
            "entities": {
                "gene": entities.get("gene"),
                "therapy": entities.get("therapy"),
                "disease": entities.get("disease"),
                "variant": entities.get("variant"),
            },
        }
        return json.dumps(payload)

    router = GeminiRouter(client=object(), enable_cache=False)
    # Patch _call_model to use our fake function
    # Note: asyncio.to_thread will call it as a function, not a method
    monkeypatch.setattr(router, "_call_model", fake_call)
    return router


@pytest.mark.asyncio()
async def test_stage_examples_route_correctly(stub_router: GeminiRouter):
    for query, expected_intent in [
        ("Which genes predict resistance to cetuximab?", "resistance_biomarkers_query"),
        ("What does vemurafenib target?", "therapy_targets_query"),
        ("What therapies target BRAF?", "gene_targeting_therapies_query"),
        ("Tell me about EGFR", "gene_overview_query"),
        ("What variants of KRAS have clinical evidence?", "gene_variants_query"),
        ("Does BRAF V600E respond to dabrafenib?", "variant_response_query"),
        ("What predicts sensitivity to imatinib in leukemia?", "sensitivity_biomarkers_query"),
        ("What biomarkers matter in lung cancer?", "disease_biomarkers_query"),
        ("What therapies have evidence in colorectal cancer?", "disease_therapies_query"),
        ("Tell me about cetuximab", "therapy_overview_query"),
        ("Compare resistance profiles for cetuximab and panitumumab", "complex"),
        ("Hello", "conversational"),
        ("asdfghjkl", "unclear"),
    ]:
        result = await stub_router.route_query(query)
        assert result.intent == expected_intent
        assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio()
async def test_confidence_is_clamped(monkeypatch):
    def fake_call(prompt: str) -> str:
        payload = {
            "intent": "gene_overview_query",
            "confidence": 1.7,
            "entities": {"gene": "KRAS", "therapy": None, "disease": None, "variant": None},
        }
        return json.dumps(payload)

    router = GeminiRouter(client=object(), enable_cache=False)
    monkeypatch.setattr(router, "_call_model", fake_call)

    result = await router.route_query("Tell me about KRAS")
    assert result.confidence == 1.0
    assert result.entities.gene == "KRAS"


@pytest.mark.asyncio()
async def test_parse_failure_falls_back(monkeypatch):
    def bad_call(prompt: str) -> str:
        return "not json"

    router = GeminiRouter(client=object(), enable_cache=False)
    monkeypatch.setattr(router, "_call_model", bad_call)

    result = await router.route_query("Tell me about KRAS")
    assert result.intent == "unclear"
    assert result.entities == ExtractedEntities()


@pytest.mark.asyncio()
async def test_timeout_falls_back(monkeypatch):
    def slow_call(prompt: str) -> str:
        time.sleep(0.05)
        payload = {
            "intent": "conversational",
            "confidence": 0.8,
            "entities": {"gene": None, "therapy": None, "disease": None, "variant": None},
        }
        return json.dumps(payload)

    router = GeminiRouter(client=object(), enable_cache=False)
    monkeypatch.setattr(router, "_call_model", slow_call)

    result = await router.route_query("Hello", timeout_s=0.01)
    assert result.intent == "unclear"


# Integration tests with real LLM (require GOOGLE_API_KEY in .env)
# Run with: pytest voice_agent/router/test_classifier.py -m llm_integration
@pytest.mark.llm_integration()
@pytest.mark.asyncio()
async def test_real_llm_resistance_biomarkers():
    """Test real LLM routing for resistance biomarkers query."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set, skipping LLM integration test")

    result = await route_query("Which genes predict resistance to cetuximab?", debug=True)
    assert result.intent == "resistance_biomarkers_query"
    assert result.entities.therapy == "cetuximab"
    assert 0.0 <= result.confidence <= 1.0
    assert result.raw_model_output is not None


@pytest.mark.llm_integration()
@pytest.mark.asyncio()
async def test_real_llm_gene_overview():
    """Test real LLM routing for gene overview."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set, skipping LLM integration test")

    result = await route_query("Tell me about KRAS")
    assert result.intent == "gene_overview_query"
    assert result.entities.gene == "KRAS"
    assert result.confidence >= 0.6  # Should be confident for clear queries


@pytest.mark.llm_integration()
@pytest.mark.asyncio()
async def test_real_llm_variant_response():
    """Test real LLM routing for variant response query."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set, skipping LLM integration test")

    result = await route_query("Does BRAF V600E respond to dabrafenib?")
    assert result.intent == "variant_response_query"
    assert result.entities.variant == "V600E"
    assert result.entities.therapy == "dabrafenib"
    assert result.entities.gene == "BRAF"


@pytest.mark.llm_integration()
@pytest.mark.asyncio()
async def test_real_llm_conversational():
    """Test real LLM routing for conversational queries."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set, skipping LLM integration test")

    result = await route_query("Hello")
    assert result.intent == "conversational"
    assert result.confidence >= 0.5


@pytest.mark.llm_integration()
@pytest.mark.asyncio()
async def test_real_llm_latency():
    """Test that real LLM calls complete within reasonable time."""
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set, skipping LLM integration test")

    import time

    start = time.perf_counter()
    result = await route_query("What therapies target BRAF?", timeout_s=10.0)
    latency = time.perf_counter() - start

    assert result.intent == "gene_targeting_therapies_query"
    assert latency < 5.0  # Should complete in under 5 seconds
