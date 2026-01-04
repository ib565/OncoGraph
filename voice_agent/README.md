# OncoGraph Voice Agent

Voice interface for querying the OncoGraph oncology knowledge graph. Ask questions about biomarkers, therapies, genes, variants, and diseases. Template-matched queries respond in ~3 seconds.

> **Note:** The voice agent is implemented and tested locally but **not yet deployed** due to inference budget constraints. It will not work out of the box. Interested in seeing a demo? [Get in touch](mailto:ish.bhartiya@gmail.com).

## Quick Start

### Prerequisites

- Python 3.10+
- Neo4j database with OncoGraph data loaded
- Google Gemini API key
- LiveKit Cloud account (or local LiveKit server)

### Environment Variables

Create `.env` in project root:

```bash
# Neo4j
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your_password"

# Google Gemini (for router LLM)
GOOGLE_API_KEY="your_gemini_api_key"
GOOGLE_API_KEY_ALT="optional_fallback_key"

# LiveKit (for voice server)
LIVEKIT_URL="wss://your-project.livekit.cloud"
LIVEKIT_API_KEY="your_api_key"
LIVEKIT_API_SECRET="your_api_secret"
```

### Running Locally

**1. Start the voice agent server:**

```bash
python -m voice_agent.voice_server dev
```

**2. Test the fast-path handler (without voice):**

```bash
python -m voice_agent.test_handler_cli "What causes resistance to cetuximab?"
```

**3. Access via web frontend:**

- Start the FastAPI backend: `uvicorn api.main:app --reload`
- Start the frontend: `cd web && npm run dev`
- Navigate to `/voice` tab in the browser

## How It Works

The standard OncoGraph query flow takes 5–30 seconds (LLM generates Cypher, validates, executes). For voice, this is too slow. So I created pre-written Cypher templates for 10 popular query patterns and implemented a lightweight router to match queries to templates.

**Fast-path flow:**
1. Router classifies intent and extracts entities (gene, therapy, disease, variant)
2. Entity normalizer maps user input to canonical names (KRAS/kras → KRAS, Erbitux → cetuximab)
3. Template engine fills in the matched Cypher template with normalized entities
4. Neo4j executes the query and returns structured results
5. Results are formatted for voice (top 3–5 items, 1–3 sentences)

**Conversational layer:**
- Gemini Flash handles greetings, clarifications, and natural language responses
- Calls the fast-path tool when graph queries are needed
- Manages voice I/O (speech-to-text, text-to-speech via LiveKit)

**Pipeline:**
```
User speech → STT → Gemini Flash → [oncograph_query tool] → Neo4j → Results → TTS → User hears response
```

## Key Technical Decisions

**Templates for speed:** The standard query engine uses LLM-generated Cypher (5–30s). Templates cut this to ~3s by using pre-written queries for common patterns. Each template handles biomarker collapsing, evidence aggregation, and synonym matching.

**Entity normalization:** Built in-memory indexes at startup from Neo4j (genes, therapies, diseases with synonyms). Handles common variations (KRAS/kras, cetuximab/Erbitux) without extra LLM calls. Diseases fall back to fuzzy matching if not in index.

**Structured results:** Tool returns JSON with intent-specific fields (one format per query type) instead of free-form text. Makes it easy for the conversational agent to summarize and for the frontend to visualize. Limited to top 5 items to keep responses short.

**Direct Neo4j connection:** Agent connects directly to Neo4j (no API hop) for lower latency. Entity index rebuilds on startup (~1–2s) to stay fresh.

**LiveKit Agents:** Uses LiveKit's framework for voice I/O, room management, and tool registration. Models via LiveKit Inference (Gemini Flash Lite, Deepgram Nova-3-Medical, Cartesia Sonic-3) to simplify deployment.

## Supported Query Types

10 query types with pre-written templates:

| Query Type | Needs | Returns |
|------------|-------|---------|
| Resistance biomarkers | therapy | Genes predicting resistance |
| Sensitivity biomarkers | therapy | Genes predicting sensitivity |
| Therapy targets | therapy | Target genes and mechanisms |
| Gene targeting therapies | gene | Therapies targeting the gene |
| Gene variants | gene | Variants with clinical evidence |
| Variant response | variant, therapy | Effect (sensitivity/resistance) |
| Gene overview | gene | Variant count, therapy count |
| Therapy overview | therapy | Modality, targets, biomarker count |
| Disease biomarkers | disease | Top biomarker genes |
| Disease therapies | disease | Therapies with evidence |

Other intents: greetings, complex queries (not supported), unclear queries.

## Performance

**Typical latency:** ~3 seconds end-to-end for template-matched queries.

**Breakdown:**
- Router (intent classification): ~1s
- Entity normalization: <10ms
- Cypher execution: ~1s
- Formatting: <10ms

**Why it's fast:**
- Templates avoid slow LLM Cypher generation
- Entity index built once at startup (not per query)
- Results limited to top 5 items
- Direct Neo4j connection (no API hop)

## Testing

Run all tests:
```bash
python -m pytest voice_agent/
```

Test fast-path without voice:
```bash
python -m voice_agent.test_handler_cli "What does cetuximab target?"
```

## Deployment

**Local:** Run `voice_server dev` (connects to LiveKit Cloud SFU). Frontend generates tokens via `/api/voice/token`.

**Production:** Deploy agent worker to LiveKit Cloud with environment secrets. See `voice_plan.md` Stage 8 for details.

## File Structure

```
voice_agent/
├── router/              # Intent classification + entity extraction
├── entities/           # Entity normalization (gene/therapy/disease indexes)
├── templates/           # Cypher templates + result formatters
├── handler.py          # Main query handler (router → template → Neo4j)
├── contracts.py        # Result models (OncoGraphToolResult + payloads)
└── voice_server.py     # LiveKit agent server
```

## Limitations

- Only 10 query types supported (complex comparisons not supported)
- No pathway enrichment (web-only feature)
- Results limited to top 5 items (voice-friendly)
- English only (STT/TTS)

## See Also

- [Architecture Diagram](ARCHITECTURE.md) - Visual system architecture
- [Technical Details](../docs/TECHNICAL_DETAILS.md) - OncoGraph system architecture

