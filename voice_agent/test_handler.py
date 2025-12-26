from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from pipeline.types import PipelineError
from voice_agent.handler import handle_query
from voice_agent.router.models import ExtractedEntities, RouteResult


def _stub_route(result: RouteResult) -> Callable[..., asyncio.Future]:
    async def _route_stub(*_: object, **__: object) -> RouteResult:
        return result

    return _route_stub


class _StubExecutor:
    def __init__(self, results: list[dict[str, object]] | None = None, raise_error: Exception | None = None) -> None:
        self._results = results or []
        self._error = raise_error

    def execute_read(self, _: str) -> list[dict[str, object]]:
        if self._error:
            raise self._error
        return self._results


async def _run_with_route_result(route_result: RouteResult, executor: _StubExecutor) -> tuple[RouteResult, object]:
    # Patch route_query inside handler to return our route_result
    from voice_agent import handler  # import inside to patch the module reference

    handler_route_query_orig = handler.route_query
    handler.route_query = _stub_route(route_result)  # type: ignore[assignment]
    try:
        result = await handle_query(
            "dummy",
            router=SimpleNamespace(),  # non-None to bypass _build_router
            executor=executor,
            normalizer=lambda e: e,  # pass-through
        )
        return route_result, result
    finally:
        handler.route_query = handler_route_query_orig  # restore


@pytest.mark.asyncio
async def test_low_confidence_needs_clarification() -> None:
    route_result = RouteResult(
        intent="therapy_targets_query",
        confidence=0.2,
        entities=ExtractedEntities(therapy="cetuximab"),
    )
    _, result = await _run_with_route_result(route_result, _StubExecutor([]))

    assert result.status == "needs_clarification"
    assert "rephrase" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_missing_required_entity_needs_clarification() -> None:
    route_result = RouteResult(
        intent="therapy_targets_query",
        confidence=1.0,
        entities=ExtractedEntities(therapy=None),
    )
    _, result = await _run_with_route_result(route_result, _StubExecutor([]))

    assert result.status == "needs_clarification"
    assert "therapy" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_not_supported_conversational() -> None:
    route_result = RouteResult(
        intent="conversational",
        confidence=1.0,
        entities=ExtractedEntities(),
    )
    _, result = await _run_with_route_result(route_result, _StubExecutor([]))

    assert result.status == "not_supported"
    assert "oncograph" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_cypher_error_maps_to_error_status() -> None:
    route_result = RouteResult(
        intent="therapy_targets_query",
        confidence=1.0,
        entities=ExtractedEntities(therapy="cetuximab"),
    )
    executor = _StubExecutor(raise_error=PipelineError("boom"))
    _, result = await _run_with_route_result(route_result, executor)

    assert result.status == "error"
    assert "problem" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_no_results_maps_to_no_results_status() -> None:
    # gene_overview payload builder returns None when counts are zero/empty
    route_result = RouteResult(
        intent="gene_overview_query",
        confidence=1.0,
        entities=ExtractedEntities(gene="UNKNOWN"),
    )
    executor = _StubExecutor(results=[])
    _, result = await _run_with_route_result(route_result, executor)

    assert result.status == "no_results"
    assert "not in my database" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_ok_status_with_payload() -> None:
    route_result = RouteResult(
        intent="therapy_targets_query",
        confidence=1.0,
        entities=ExtractedEntities(therapy="cetuximab"),
    )
    executor = _StubExecutor(
        results=[{"gene_symbol": "EGFR", "targets_moa": "inhibitor"}],
    )
    _, result = await _run_with_route_result(route_result, executor)

    assert result.status == "ok"
    assert result.payload is not None
    assert result.payload.intent == "therapy_targets_query"
    assert result.payload.therapy == "cetuximab"
    assert len(result.payload.targets) == 1

