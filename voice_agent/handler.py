from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from pipeline.executor import Neo4jExecutor
from pipeline.gemini import GeminiConfig
from pipeline.types import PipelineError
from voice_agent.contracts import NormalizedEntities, OncoGraphToolResult, VoiceHint
from voice_agent.entities import create_normalizer
from voice_agent.entities.index import _build_executor
from voice_agent.router.classifier import GeminiRouter, route_query
from voice_agent.router.models import INTENT_REQUIRED_ENTITIES
from voice_agent.templates import fill_template, get_template

logger = logging.getLogger(__name__)

# Singleton Neo4jExecutor instance
_executor: Neo4jExecutor | None = None


def get_executor() -> Neo4jExecutor:
    """Get or create the global Neo4jExecutor instance (lazy initialization)."""
    global _executor
    if _executor is None:
        _executor = _build_executor()
    return _executor


def _build_router() -> GeminiRouter:
    """Build GeminiRouter with configuration from environment variables."""
    config = GeminiConfig(
        model="gemini-2.5-flash-lite",
        api_key=os.getenv("GOOGLE_API_KEY"),
        api_key_alt=os.getenv("GOOGLE_API_KEY_ALT"),
    )
    return GeminiRouter(config=config)


async def handle_query(
    transcript: str,
    *,
    router: GeminiRouter | None = None,
    executor: Neo4jExecutor | None = None,
    normalizer: Callable | None = None,
    confidence_threshold: float = 0.6,
    speak_top_n: int = 3,
) -> OncoGraphToolResult:
    """Main entry point for fast-path query handling as a structured tool.

    Args:
        transcript: User's natural language query.
        router: Optional GeminiRouter instance. If None, creates a new one.
        executor: Optional Neo4jExecutor instance. If None, uses singleton.
        normalizer: Optional normalizer function. If None, creates default from EntityIndex.
        confidence_threshold: Minimum confidence score (0.0-1.0) to proceed with query.
        speak_top_n: Max number of items the voice agent is likely to speak.

    Returns:
        OncoGraphToolResult with status, entities, and optional intent-specific payload.
    """
    total_start = time.perf_counter()

    # Initialize components
    router_instance = router or _build_router()
    executor_instance = executor or get_executor()
    normalizer_instance = normalizer or create_normalizer()

    # Step 1: Router call
    router_start = time.perf_counter()
    try:
        result = await route_query(
            transcript,
            router=router_instance,
            normalizer=normalizer_instance,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Router call failed", exc_info=exc)
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": None,
                "status": "error",
                "router_ms": int((time.perf_counter() - router_start) * 1000),
                "template_ms": 0,
                "cypher_ms": 0,
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=0.0,
            entities=NormalizedEntities(),
            message="I ran into a problem processing your query. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )
    router_duration = time.perf_counter() - router_start

    entities_dict = result.entities.model_dump()

    # Step 2: Confidence check
    if result.confidence < confidence_threshold:
        logger.info(
            "Low confidence query rejected",
            extra={"confidence": result.confidence, "intent": result.intent},
        )
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "needs_clarification",
                "router_ms": int(router_duration * 1000),
                "template_ms": 0,
                "cypher_ms": 0,
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="needs_clarification",
            confidence=result.confidence,
            entities=result.entities,
            message="I'm not sure what you're asking. Could you rephrase that?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )

    # Step 3: Handle special intents (no payload, just guidance)
    if result.intent == "conversational":
        message = "Hi! I'm OncoGraph. Ask me about cancer biomarkers, therapies, or resistance mechanisms."
        status = "not_supported"
    elif result.intent == "complex":
        message = (
            "That's a complex question that needs more analysis. "
            "I'll have results ready in the web dashboard in about a minute. "
            "Is there something simpler I can help with now?"
        )
        status = "not_supported"
    elif result.intent == "unclear":
        message = (
            "I'm not sure I understood that. "
            "You can ask me things like 'What causes resistance to cetuximab?' "
            "or 'What therapies target BRAF?'"
        )
        status = "not_supported"
    else:
        message = None
        status = None

    if status is not None:
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": status,
                "router_ms": int(router_duration * 1000),
                "template_ms": 0,
                "cypher_ms": 0,
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status=status,  # type: ignore[arg-type]
            confidence=result.confidence,
            entities=result.entities,
            message=message,
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )

    # Step 4: Template lookup
    template_start = time.perf_counter()
    template = get_template(result.intent)
    if template is None:
        logger.warning("Template not found", extra={"intent": result.intent})
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "error",
                "router_ms": int(router_duration * 1000),
                "template_ms": int((time.perf_counter() - template_start) * 1000),
                "cypher_ms": 0,
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=result.confidence,
            entities=result.entities,
            message="I ran into a problem processing your query. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )

    # Step 5: Entity validation
    required_entities = INTENT_REQUIRED_ENTITIES.get(result.intent, [])

    for entity_type in required_entities:
        entity_value = entities_dict.get(entity_type)
        if entity_value is None:
            entity_display = _get_entity_display_name(entity_type)
            total_duration = time.perf_counter() - total_start
            logger.info(
                "Handler timing",
                extra={
                    "intent": result.intent,
                    "status": "needs_clarification",
                    "router_ms": int(router_duration * 1000),
                    "template_ms": int((time.perf_counter() - template_start) * 1000),
                    "cypher_ms": 0,
                    "formatting_ms": 0,
                    "total_ms": int(total_duration * 1000),
                },
            )
            return OncoGraphToolResult(
                status="needs_clarification",
                confidence=result.confidence,
                entities=result.entities,
                message=f"I need to know the {entity_type}. Which {entity_display} are you asking about?",
                voice=VoiceHint(speak_top_n=speak_top_n),
                payload=None,
            )

    # Step 6: Template filling
    try:
        filled_cypher = fill_template(template, result.entities)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Template filling failed", exc_info=exc, extra={"intent": result.intent})
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "error",
                "router_ms": int(router_duration * 1000),
                "template_ms": int((time.perf_counter() - template_start) * 1000),
                "cypher_ms": 0,
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=result.confidence,
            entities=result.entities,
            message="I ran into a problem processing your query. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )
    template_duration = time.perf_counter() - template_start

    # Step 7: Cypher execution
    cypher_start = time.perf_counter()
    try:
        results = executor_instance.execute_read(filled_cypher)
    except PipelineError as exc:
        logger.error("Cypher execution failed", exc_info=exc, extra={"intent": result.intent})
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "error",
                "router_ms": int(router_duration * 1000),
                "template_ms": int(template_duration * 1000),
                "cypher_ms": int((time.perf_counter() - cypher_start) * 1000),
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=result.confidence,
            entities=result.entities,
            message="I ran into a problem looking that up. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Unexpected error during Cypher execution", exc_info=exc, extra={"intent": result.intent})
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "error",
                "router_ms": int(router_duration * 1000),
                "template_ms": int(template_duration * 1000),
                "cypher_ms": int((time.perf_counter() - cypher_start) * 1000),
                "formatting_ms": 0,
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=result.confidence,
            entities=result.entities,
            message="I ran into a problem looking that up. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )
    cypher_duration = time.perf_counter() - cypher_start

    # Step 8: Payload building
    formatting_start = time.perf_counter()
    try:
        payload = template.format_response(results, entities_dict, speak_top_n)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Payload building failed", exc_info=exc, extra={"intent": result.intent})
        total_duration = time.perf_counter() - total_start
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": "error",
                "router_ms": int(router_duration * 1000),
                "template_ms": int(template_duration * 1000),
                "cypher_ms": int(cypher_duration * 1000),
                "formatting_ms": int((time.perf_counter() - formatting_start) * 1000),
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="error",
            confidence=result.confidence,
            entities=result.entities,
            message="I ran into a problem processing your query. Could you try asking differently?",
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )
    formatting_duration = time.perf_counter() - formatting_start

    # Step 9: Build final result and log timing
    total_duration = time.perf_counter() - total_start

    if payload is None:
        status: str = "no_results"
        message = _build_no_results_message(result.intent, entities_dict)
        logger.info(
            "Handler timing",
            extra={
                "intent": result.intent,
                "status": status,
                "router_ms": int(router_duration * 1000),
                "template_ms": int(template_duration * 1000),
                "cypher_ms": int(cypher_duration * 1000),
                "formatting_ms": int(formatting_duration * 1000),
                "total_ms": int(total_duration * 1000),
            },
        )
        return OncoGraphToolResult(
            status="no_results",
            confidence=result.confidence,
            entities=result.entities,
            message=message,
            voice=VoiceHint(speak_top_n=speak_top_n),
            payload=None,
        )

    logger.info(
        "Handler timing",
        extra={
            "intent": result.intent,
            "status": "ok",
            "router_ms": int(router_duration * 1000),
            "template_ms": int(template_duration * 1000),
            "cypher_ms": int(cypher_duration * 1000),
            "formatting_ms": int(formatting_duration * 1000),
            "total_ms": int(total_duration * 1000),
        },
    )

    return OncoGraphToolResult(
        status="ok",
        confidence=result.confidence,
        entities=result.entities,
        message=None,
        voice=VoiceHint(speak_top_n=speak_top_n),
        payload=payload,
    )


def _get_entity_display_name(entity_type: str) -> str:
    """Get display name for entity type in error messages."""
    mapping = {
        "therapy": "therapy",
        "gene": "gene",
        "disease": "disease",
        "variant": "variant",
    }
    return mapping.get(entity_type, entity_type)


def _build_no_results_message(intent: str, entities: dict[str, str | None]) -> str:
    """Build a user-facing no-results message for a given intent."""
    therapy = entities.get("therapy") or "this therapy"
    gene = entities.get("gene") or "this gene"
    disease = entities.get("disease") or "this disease"
    variant = entities.get("variant") or "this variant"

    if intent == "resistance_biomarkers_query":
        return f"I didn't find resistance biomarkers for {therapy}."
    if intent == "sensitivity_biomarkers_query":
        return f"I didn't find sensitivity biomarkers for {therapy}."
    if intent == "therapy_targets_query":
        return f"I didn't find target genes for {therapy}."
    if intent == "gene_targeting_therapies_query":
        return f"I didn't find therapies targeting {gene}."
    if intent == "gene_variants_query":
        return f"{gene} has no variants with clinical evidence in the database."
    if intent == "variant_response_query":
        return f"I don't have evidence for {variant} affecting {therapy} response."
    if intent == "gene_overview_query":
        return f"{gene} is not in my database."
    if intent == "therapy_overview_query":
        return f"{therapy} is not in my database."
    if intent == "disease_biomarkers_query":
        return f"I didn't find biomarkers for {disease}."
    if intent == "disease_therapies_query":
        return f"I didn't find therapies with biomarker evidence in {disease}."

    # Fallback
    return "I didn't find any results for that query."
