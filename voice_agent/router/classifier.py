from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from pydantic import ValidationError

from pipeline.gemini import GeminiConfig, _GeminiBase  # type: ignore
from pipeline.types import PipelineError
from pipeline.utils import TTLCache

from .models import ExtractedEntities, RouteResult
from .prompts import build_router_prompt

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    genai = None  # type: ignore
    genai_types = None  # type: ignore

logger = logging.getLogger(__name__)


class GeminiRouter(_GeminiBase):
    """LLM-powered router using Gemini 2.5 Flash Lite with structured JSON output."""

    def __init__(
        self,
        config: GeminiConfig | None = None,
        client: object | None = None,
        *,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 300,
    ) -> None:
        cfg = config or GeminiConfig(model="gemini-2.5-flash-lite")
        super().__init__(config=cfg, client=client)
        self._cache = TTLCache(default_ttl_seconds=cache_ttl_seconds) if enable_cache else None

    def _build_content_config(self) -> object | None:  # type: ignore[override]
        """Override to request structured JSON adhering to RouteResult."""
        if genai_types is None:
            return None
        return genai_types.GenerateContentConfig(  # type: ignore[attr-defined]
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            response_mime_type="application/json",
            response_schema=RouteResult,
        )

    async def route_query(
        self,
        transcript: str,
        *,
        timeout_s: float = 5.0,
        debug: bool = False,
        normalizer: Callable[[ExtractedEntities], ExtractedEntities] | None = None,
    ) -> RouteResult:
        text = transcript.strip()
        if not text:
            return self._fallback()

        cache_key = None
        if self._cache:
            cache_key = f"router:{text.lower()}"
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        prompt = build_router_prompt(text)

        start = time.perf_counter()
        try:
            raw = await asyncio.wait_for(asyncio.to_thread(self._call_model, prompt=prompt), timeout=timeout_s)
        except TimeoutError:
            logger.warning("Router LLM call timed out", extra={"timeout_s": timeout_s})
            return self._fallback()
        except PipelineError:
            # Already logged at _call_model level
            return self._fallback()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Router LLM call failed", exc_info=exc)
            return self._fallback()
        latency = time.perf_counter() - start

        try:
            import json as json_lib

            # Parse JSON first to allow clamping confidence before validation
            data = json_lib.loads(raw)
            # Clamp confidence to [0, 1] before validation
            if "confidence" in data:
                data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
            result = RouteResult.model_validate(data)
        except (json_lib.JSONDecodeError, ValidationError) as err:
            logger.warning("Router JSON validation failed", extra={"errors": str(err)})
            return self._fallback()

        if normalizer is not None:
            try:
                normalized = normalizer(result.entities)
                result = result.model_copy(update={"entities": normalized})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Normalizer raised, returning unnormalized entities", exc_info=exc)

        if self._cache and cache_key:
            self._cache.set(cache_key, result)

        logger.info(
            "Router result",
            extra={
                "intent": result.intent,
                "confidence": result.confidence,
                "latency_ms": int(latency * 1000),
                "cached": False,
                "model": self.config.model,
            },
        )
        return result

    def _fallback(self) -> RouteResult:
        """Return a conservative unclear result."""
        return RouteResult(intent="unclear", confidence=0.0, entities=ExtractedEntities())


async def route_query(
    transcript: str,
    *,
    timeout_s: float = 5.0,
    debug: bool = False,
    normalizer: Callable[[ExtractedEntities], ExtractedEntities] | None = None,
    router: GeminiRouter | None = None,
) -> RouteResult:
    """Convenience async entrypoint that reuses a router instance if provided."""
    router_instance = router or GeminiRouter()
    return await router_instance.route_query(
        transcript,
        timeout_s=timeout_s,
        debug=debug,
        normalizer=normalizer,
    )
