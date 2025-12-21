from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from pipeline.executor import Neo4jExecutor
from pipeline.gemini import GeminiConfig
from pipeline.types import PipelineError
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
) -> str:
    """Main entry point for fast-path query handling.

    Args:
        transcript: User's natural language query.
        router: Optional GeminiRouter instance. If None, creates a new one.
        executor: Optional Neo4jExecutor instance. If None, uses singleton.
        normalizer: Optional normalizer function. If None, creates default from EntityIndex.
        confidence_threshold: Minimum confidence score (0.0-1.0) to proceed with query.

    Returns:
        Formatted response string ready for voice output.
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
        return "I ran into a problem processing your query. Could you try asking differently?"
    router_duration = time.perf_counter() - router_start

    # Step 2: Confidence check
    if result.confidence < confidence_threshold:
        logger.info(
            "Low confidence query rejected",
            extra={"confidence": result.confidence, "intent": result.intent},
        )
        return "I'm not sure what you're asking. Could you rephrase that?"

    # Step 3: Handle special intents
    if result.intent == "conversational":
        return "Hi! I'm OncoGraph. Ask me about cancer biomarkers, therapies, or resistance mechanisms."

    if result.intent == "complex":
        return (
            "That's a complex question that needs more analysis. "
            "I'll have results ready in the web dashboard in about a minute. "
            "Is there something simpler I can help with now?"
        )

    if result.intent == "unclear":
        return (
            "I'm not sure I understood that. "
            "You can ask me things like 'What causes resistance to cetuximab?' "
            "or 'What therapies target BRAF?'"
        )

    # Step 4: Template lookup
    template_start = time.perf_counter()
    template = get_template(result.intent)
    if template is None:
        logger.warning("Template not found", extra={"intent": result.intent})
        return "I ran into a problem processing your query. Could you try asking differently?"

    # Step 5: Entity validation
    required_entities = INTENT_REQUIRED_ENTITIES.get(result.intent, [])
    entities_dict = result.entities.model_dump()

    for entity_type in required_entities:
        entity_value = entities_dict.get(entity_type)
        if entity_value is None:
            # Entity is None - could be either:
            # 1. Router didn't extract it
            # 2. Normalization failed (entity not found in index)
            # We can't distinguish these cases since normalization happens in router,
            # so we provide a helpful message asking for the entity
            entity_display = _get_entity_display_name(entity_type)
            return f"I need to know the {entity_type}. Which {entity_display} are you asking about?"

    # Step 6: Template filling
    try:
        filled_cypher = fill_template(template, result.entities)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Template filling failed", exc_info=exc, extra={"intent": result.intent})
        return "I ran into a problem processing your query. Could you try asking differently?"
    template_duration = time.perf_counter() - template_start

    # Step 7: Cypher execution
    cypher_start = time.perf_counter()
    try:
        results = executor_instance.execute_read(filled_cypher)
    except PipelineError as exc:
        logger.error("Cypher execution failed", exc_info=exc, extra={"intent": result.intent})
        return "I ran into a problem looking that up. Could you try asking differently?"
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Unexpected error during Cypher execution", exc_info=exc, extra={"intent": result.intent})
        return "I ran into a problem looking that up. Could you try asking differently?"
    cypher_duration = time.perf_counter() - cypher_start

    # Step 8: Response formatting
    formatting_start = time.perf_counter()
    try:
        response = template.format_response(results, entities_dict)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Response formatting failed", exc_info=exc, extra={"intent": result.intent})
        return "I ran into a problem formatting the response. Could you try asking differently?"
    formatting_duration = time.perf_counter() - formatting_start

    # Step 9: Log timing
    total_duration = time.perf_counter() - total_start
    logger.info(
        "Handler timing",
        extra={
            "intent": result.intent,
            "router_ms": int(router_duration * 1000),
            "template_ms": int(template_duration * 1000),
            "cypher_ms": int(cypher_duration * 1000),
            "formatting_ms": int(formatting_duration * 1000),
            "total_ms": int(total_duration * 1000),
        },
    )

    return response


def _get_entity_display_name(entity_type: str) -> str:
    """Get display name for entity type in error messages."""
    mapping = {
        "therapy": "therapy",
        "gene": "gene",
        "disease": "disease",
        "variant": "variant",
    }
    return mapping.get(entity_type, entity_type)
