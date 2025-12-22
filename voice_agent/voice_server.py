"""LiveKit voice agent server for OncoGraph."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool

from voice_agent.handler import handle_query

# Load environment variables
load_dotenv()

# Configure logging: suppress verbose DEBUG logs from third-party libraries
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

# Set third-party libraries to WARNING level to reduce noise
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("neo4j.io").setLevel(logging.WARNING)
logging.getLogger("neo4j.pool").setLevel(logging.WARNING)
logging.getLogger("livekit.agents").setLevel(logging.INFO)  # Keep INFO for agent lifecycle
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

# Keep our own modules at INFO level for useful debugging
logging.getLogger("voice_agent").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# System instructions for the voice agent
SYSTEM_INSTRUCTIONS = """You are OncoGraph, a voice assistant for oncology research using a curated knowledge graph.

Use the oncograph_query tool when the user asks about:
- resistance or sensitivity biomarkers for a therapy
- what a therapy targets, or what therapies target a gene
- variant response evidence (variant vs therapy)
- disease-specific top biomarkers or therapies with evidence
- gene or therapy overview in the database

When the tool returns results:
- If status is "ok": Summarize the payload in 1-3 sentences. List the top 3 items. Mention evidence level only when A or B appears. Ask one short follow-up question when helpful.
- If status is "needs_clarification": Ask exactly one clarifying question using the message field.
- If status is "no_results": Say nothing was found and suggest a rephrasing.
- If status is "not_supported": Explain that it's a complex or unsupported request and propose an example supported query.
- If status is "error": Give a generic apology and suggest trying again. Never expose internal errors.

Speaking style:
- 1 to 3 sentences maximum.
- If there are many items, name the top three and say "and X others."
- Mention evidence level only when A or B appears.
- Ask one short follow-up question when helpful.

Do NOT read PMIDs, URLs, or Cypher aloud.

If the user asks for pathway enrichment, say it is not available in voice mode and offer a supported query type instead.

This is for research/education only, not medical advice."""


@function_tool()
async def oncograph_query(
    context: RunContext,
    query: str,
) -> dict:
    """Query the OncoGraph knowledge graph (Neo4j) for oncology biomarkers, therapy targets,
    variant response evidence, and disease-specific evidence. Returns a small structured
    result with counts and top items.

    Args:
        query: Natural language question about oncology biomarkers, therapies, genes, variants, or diseases.

    Returns:
        A dictionary with:
        - status: ok | needs_clarification | no_results | not_supported | error
        - entities: normalized gene/therapy/disease/variant (when available)
        - payload: intent-specific structured data (top results only, when status is ok)
        - message: short user-safe message for non-ok outcomes
    """
    logger.info("oncograph_query called", extra={"query": query})
    try:
        result = await handle_query(query, speak_top_n=3)
        # Convert Pydantic model to dict for LLM consumption
        return result.model_dump()
    except Exception as exc:
        logger.error("oncograph_query failed", exc_info=exc, extra={"query": query})
        # Return error status
        return {
            "status": "error",
            "confidence": 0.0,
            "entities": {},
            "message": "I ran into a problem processing your query. Could you try asking differently?",
            "voice": {"speak_top_n": 3},
            "payload": None,
        }


class OncoGraphAgent(Agent):
    """OncoGraph voice agent with oncology knowledge graph querying capabilities."""

    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS,
            tools=[oncograph_query],
        )


server = AgentServer()


@server.rtc_session()
async def voice_agent(ctx: agents.JobContext) -> None:
    """Entrypoint for the voice agent session."""
    logger.info("Starting voice agent session", extra={"room": ctx.room.name})

    # Configure AgentSession with LiveKit Inference models
    session = AgentSession(
        stt="deepgram/nova-3:en",  # Deepgram STT via LiveKit Inference
        llm="google/gemini-2.5-flash-lite",  # Gemini LLM via LiveKit Inference
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # Cartesia TTS via LiveKit Inference
    )

    # Start the session with the OncoGraph agent
    await session.start(
        room=ctx.room,
        agent=OncoGraphAgent(),
    )

    # Greet the user
    await session.generate_reply(
        instructions="Greet the user and offer your assistance with oncology research questions.",
    )

    logger.info("Voice agent session started", extra={"room": ctx.room.name})


if __name__ == "__main__":
    agents.cli.run_app(server)
