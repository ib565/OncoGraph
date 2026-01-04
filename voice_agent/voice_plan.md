# OncoGraph Voice Agent - Complete Implementation Plan

## Note

This document provides a comprehensive implementation plan for the OncoGraph voice AI agent. The plan is structured in stages, with each stage building on the previous ones. Feel free to deviate from it and suggest improvements and changes.

## Overview

This document covers the complete implementation of the OncoGraph voice AI agent, from the initial fast-path query router through to the full voice-enabled system. The agent uses a two-tier architecture:

1. **Fast-Path Query Engine** (Stages 1-5): A specialized tool that classifies natural language queries, extracts entities, matches to pre-written Cypher templates, executes queries against Neo4j, and returns structured JSON payloads optimized for voice output.

2. **Conversational Agent** (Stage 6+): A Gemini Flash-powered conversational agent that handles greetings, clarifications, and natural language generation, calling the fast-path tool when graph queries are needed. Integrated with the existing OncoGraph web frontend (Stage 7) and deployed to LiveKit Cloud (Stage 8).

The system is designed for low latency (~3 seconds for template-matched queries) and voice-friendly responses (1-3 sentences, top N items, natural phrasing).

## Current Progress

**✅ Stage 1: Router Prototype** - COMPLETE
- Pydantic models, router prompt, LLM integration, timeout handling, and tests all implemented
- Location: `voice_agent/router/`

**✅ Stage 2: Entity Index** - COMPLETE
- Entity normalization indexes for genes, therapies, and diseases implemented
- Singleton pattern, normalization methods, logging, and comprehensive tests all complete
- Location: `voice_agent/entities/`

**✅ Stage 3: Template Library** - COMPLETE
- Pre-written Cypher templates for 10 query types
- Location: `voice_agent/templates/`

**✅ Stage 4: Fast Path Integration** - COMPLETE
- Main handler function implemented with full error handling
- Router → normalization → template → Neo4j → response flow working
- Singleton executor pattern, latency tracking, and test CLI script all complete
- Location: `voice_agent/handler.py`, `voice_agent/test_handler_cli.py`

**✅ Stage 5: Convert Fast Path to a Tool** - COMPLETE
- Refactor handler to return structured `OncoGraphToolResult` with intent-specific payloads
- Convert formatters from string generators to payload builders
- Update all templates and tests to use new payload structure
- Location: `voice_agent/contracts.py`, `voice_agent/handler.py`, `voice_agent/templates/formatters.py`

**✅ Stage 6: Wire in LiveKit (Voice MVP - Local)** - COMPLETE
- Integrated LiveKit agent framework (`voice_agent/voice_server.py`)
- Connected Gemini Flash Lite as conversational LLM via LiveKit Inference
- Registered OncoGraph tool (`oncograph_query`) for function calling
- Added Deepgram STT (Nova-3-Medical) and Cartesia TTS (Sonic-3) via LiveKit Inference
- Configured logging to suppress verbose third-party DEBUG logs
- Tested end-to-end locally: agent successfully processes voice queries and calls tool
- Note: Stage 6 uses LiveKit Cloud for hosting, but tested locally first



### Target Latency
- Template-matched queries: ~3 seconds end-to-end
- Complex queries (fallback): acknowledge immediately, process in background

### Architecture Pipeline

**Fast-Path Tool (Stages 1-5):**
```
User query (natural language)
    ↓
Intent + Entity Extraction (LLM, structured output)
    ↓
Entity Normalization (deterministic + fuzzy fallback)
    ↓
Template Selection + Fill
    ↓
Cypher Execution (Neo4j)
    ↓
Payload Building (structured JSON)
    ↓
Return OncoGraphToolResult to conversational agent
```

**Full Voice System (Stage 6+):**
```
User speech (OncoGraph Frontend → LiveKit)
    ↓
Speech-to-Text (Deepgram)
    ↓
Conversational Agent (Gemini Flash)
    ↓
[If graph query needed] → Fast-Path Tool → Structured payload
    ↓
Natural Language Generation (Gemini Flash)
    ↓
Text-to-Speech (Cartesia)
    ↓
User hears response (via LiveKit → Frontend)
```

---

## Stage 1: Router Prototype ✅ COMPLETE

**Goal:** Prove intent classification and entity extraction works fast enough.

**Implementation:** `voice_agent/router/` - All components implemented and tested.

### 1.1 Pydantic Models

Create models for structured LLM output (see `voice_agent/router/models.py` for the concrete implementation):

**RouteResult**
- `intent`: Literal enum of all template IDs plus "conversational", "complex", "unclear"
- `entities`: ExtractedEntities object
- `confidence`: float 0.0-1.0

**ExtractedEntities**
- `gene`: str | None
- `therapy`: str | None  
- `disease`: str | None
- `variant`: str | None

In code, the router metadata is centralized in:
- `INTENT_IDS`: ordered list of all supported intent IDs
- `INTENT_REQUIRED_ENTITIES`: mapping from intent → list of required entities
- `INTENT_DESCRIPTIONS`: mapping from intent → human-readable description
- `INTENT_EXAMPLES`: mapping from intent → a single example query string

### 1.2 Intent Categories

| Intent ID | Description | Required Entities |
|-----------|-------------|-------------------|
| `resistance_biomarkers_query` | Find genes whose variants predict resistance to a specific therapy | therapy |
| `sensitivity_biomarkers_query` | Find genes whose variants predict sensitivity to a specific therapy | therapy |
| `therapy_targets_query` | What genes a therapy targets via `TARGETS` relationships | therapy |
| `gene_targeting_therapies_query` | What therapies target a specific gene | gene |
| `gene_variants_query` | List variants of a gene that have clinical evidence in the database | gene |
| `variant_response_query` | How a specific variant affects response to a specific therapy | variant, therapy |
| `gene_overview_query` | Summary statistics about a gene (variants, targeting therapies) | gene |
| `therapy_overview_query` | Summary statistics about a therapy (modality, target genes, biomarker associations) | therapy |
| `disease_biomarkers_query` | Top biomarker genes for a specific disease | disease |
| `disease_therapies_query` | Therapies with biomarker evidence in a specific disease | disease |
| `conversational` | Greetings, thanks, off-topic chat | none |
| `complex` | Multi-entity comparisons, exclusions, etc. | varies |
| `unclear` | Can't determine intent | none |

### 1.3 Router Prompt Design

The prompt should:
- List all available intents with short descriptions
- Instruct the LLM to extract entities and normalize obvious cases (KRAS not kras, cetuximab not Cetuximab)
- Request JSON output matching your Pydantic model
- Surface one natural-language example per intent (from `INTENT_EXAMPLES`)
- Include 2-3 end-to-end JSON examples showing the exact `RouteResult` shape

Key prompt elements:
- System context: "You are a query router for an oncology knowledge graph"
- Available intents list with descriptions and examples
- Entity extraction rules (gene=uppercase, therapy=lowercase)
- Output format specification
- Confidence guidance: 1.0 for obvious matches, lower for ambiguous

Examples:
- "What causes resistance to cetuximab?" → resistance_biomarkers_query, {therapy: cetuximab}
- "Tell me about KRAS" → gene_overview_query, {gene: KRAS}
- "Does BRAF V600E respond to dabrafenib?" → variant_response_query, {variant: V600E, therapy: dabrafenib, gene: BRAF}
- "Compare all EGFR inhibitors" → complex, {}
- "Thanks!" → conversational, {}

The current router prompt also includes a small block of concrete JSON output examples, for instance:

```json
User: "What genes predict resistance to trastuzumab?"
Response JSON: {
  "intent": "resistance_biomarkers_query",
  "confidence": 1.0,
  "entities": {
    "gene": null,
    "therapy": "trastuzumab",
    "disease": null,
    "variant": null
  }
}

User: "What is KRAS?"
Response JSON: {
  "intent": "gene_overview_query",
  "confidence": 1.0,
  "entities": {
    "gene": "KRAS",
    "therapy": null,
    "disease": null,
    "variant": null
  }
}

User: "What does erlotinib target?"
Response JSON: {
  "intent": "therapy_targets_query",
  "confidence": 1.0,
  "entities": {
    "gene": null,
    "therapy": "erlotinib",
    "disease": null,
    "variant": null
  }
}
```

### 1.4 Implementation Notes

- Use Gemini Flash Lite with structured output
- Wrap in async function for later integration
- Add timeout handling (fail if LLM takes >5s)
- Log inputs/outputs for debugging

### 1.5 Test Cases

Test the router against these queries (expected results in parentheses):

```
"Which genes predict resistance to cetuximab?" 
  → resistance_biomarkers_query, {therapy: cetuximab}

"What does vemurafenib target?"
  → therapy_targets_query, {therapy: vemurafenib}

"What therapies target BRAF?"
  → gene_targeting_therapies_query, {gene: BRAF}

"Tell me about EGFR"
  → gene_overview_query, {gene: EGFR}

"What variants of KRAS have clinical evidence?"
  → gene_variants_query, {gene: KRAS}

"Does BRAF V600E respond to dabrafenib?"
  → variant_response_query, {variant: V600E, therapy: dabrafenib}

"What predicts sensitivity to imatinib in leukemia?"
  → sensitivity_biomarkers_query, {therapy: imatinib, disease: leukemia}

"What biomarkers matter in lung cancer?"
  → disease_biomarkers_query, {disease: lung cancer}

"What therapies have evidence in colorectal cancer?"
  → disease_therapies_query, {disease: colorectal cancer}

"Tell me about cetuximab"
  → therapy_overview_query, {therapy: cetuximab}

"Compare resistance profiles for cetuximab and panitumumab"
  → complex, {}

"Hello"
  → conversational, {}  

"asdfghjkl"
  → unclear, {}
```

### Done When
- [x] Pydantic models defined and importable (`voice_agent/router/models.py`)
- [x] Router prompt written (`voice_agent/router/prompts.py` with descriptions, examples, and JSON examples)
- [x] Router function implemented with LLM call (`voice_agent/router/classifier.py` - `GeminiRouter.route_query()`)
- [x] Function returns structured RouteResult
- [x] Latency measured (logged in router with `latency_ms`)
- [x] Test cases pass correctly (`voice_agent/router/test_classifier.py`)
- [x] Timeout handling works (5s default timeout with fallback to unclear intent)

---

## Stage 2: Entity Index

**Status:** ✅ COMPLETE

**Goal:** Fast deterministic normalization of user-spoken entities to canonical database names.

### 2.1 Architecture Decisions

**Singleton Pattern:** Use a simple global singleton with lazy initialization via `get_index()` function. This provides a clean API while remaining testable (can pass mock index to functions).

**Neo4j Connection:** Reuse `Neo4jExecutor` from `src/pipeline/executor.py` to avoid code duplication.

**Index Persistence:** Rebuild indexes on startup (no file caching). Query Neo4j each time the agent starts (~1-2 seconds). This ensures freshness and simplicity. Render's filesystem is ephemeral anyway, so file caching wouldn't help across deploys.

**Disease Index:** Build full index from Disease nodes (not relationships) with synonyms property. Disease nodes exist in the graph but don't participate in relationships. We'll build the index and figure out the best normalization strategy as we go.

### 2.2 Index Structure

Build in-memory dictionaries at startup:

**genes_index**: dict[str, str]
- Keys: lowercase variations (symbol, synonyms)
- Values: canonical uppercase symbol
- Example: {"kras": "KRAS", "k-ras": "KRAS", "kirsten rat sarcoma": "KRAS"}

**therapies_index**: dict[str, str]
- Keys: lowercase variations (name, synonyms)
- Values: canonical lowercase name
- Example: {"cetuximab": "cetuximab", "erbitux": "cetuximab"}

**diseases_index**: dict[str, str]
- Keys: lowercase variations (name, synonyms)
- Values: canonical name as stored in database
- Example: {"colorectal cancer": "Colorectal Carcinoma", "crc": "Colorectal Carcinoma"}

### 2.3 Data Extraction Queries

Run these against Neo4j at startup using `Neo4jExecutor`:

**Genes:**
```cypher
MATCH (g:Gene)
RETURN g.symbol AS symbol, g.synonyms AS synonyms
```

**Therapies:**
```cypher
MATCH (t:Therapy)
RETURN t.name AS name, t.synonyms AS synonyms
```

**Diseases:**
```cypher
MATCH (d:Disease)
RETURN d.name AS name, d.synonyms AS synonyms
```

**Note:** Synonyms are stored as arrays in Neo4j (not semicolon-separated strings). The CSV files use semicolons, but the builder splits them into arrays during ingestion.

### 2.4 Index Building Logic

For each entity type, the building process:

1. Query Neo4j to get all nodes with their synonyms
2. For each node:
   - Add canonical name → canonical name mapping (using lowercase key)
   - For each synonym in the synonyms array:
     - Add synonym → canonical name mapping (using lowercase key)
     - If synonym already maps to a different canonical name, log a warning (ambiguity detected)
3. Store mappings in the appropriate index dictionary

**Example for Genes:**
- Query returns: `{symbol: "KRAS", synonyms: ["KRAS2", "RASK2"]}`
- Add mappings:
  - `"kras" → "KRAS"` (canonical symbol)
  - `"kras2" → "KRAS"` (synonym)
  - `"rask2" → "KRAS"` (synonym)

**Example for Therapies:**
- Query returns: `{name: "Cetuximab", synonyms: ["Erbitux"]}`
- Add mappings:
  - `"cetuximab" → "cetuximab"` (canonical name, lowercase)
  - `"erbitux" → "cetuximab"` (synonym)

**Example for Diseases:**
- Query returns: `{name: "Colorectal Carcinoma", synonyms: ["Colorectal Cancer", "CRC"]}`
- Add mappings:
  - `"colorectal carcinoma" → "Colorectal Carcinoma"` (canonical name, as stored)
  - `"colorectal cancer" → "Colorectal Carcinoma"` (synonym)
  - `"crc" → "Colorectal Carcinoma"` (synonym)

### 2.5 EntityIndex Class Design

**File:** `voice_agent/entities/index.py`

```python
class EntityIndex:
    """In-memory index for fast entity normalization."""
    
    def __init__(self, executor: Neo4jExecutor):
        self.genes_index: dict[str, str] = {}      # lowercase -> canonical uppercase
        self.therapies_index: dict[str, str] = {}   # lowercase -> canonical lowercase  
        self.diseases_index: dict[str, str] = {}    # lowercase -> canonical name
        self._build_indexes(executor)
    
    def _build_indexes(self, executor: Neo4jExecutor) -> None:
        """Query Neo4j and build all three indexes."""
        # Build genes_index
        # Build therapies_index  
        # Build diseases_index
    
    def normalize_entity(self, entity_type: str, raw: str) -> str | None:
        """
        Normalize an entity to its canonical form.
        
        Args:
            entity_type: "gene", "therapy", "disease", or "variant"
            raw: Raw entity string from user input
            
        Returns:
            Canonical entity name, or None if not found (diseases return input as-is if not found)
        """
        # Lookup logic
    
    def normalize_entities(self, entities: ExtractedEntities) -> ExtractedEntities:
        """
        Normalize all entities in an ExtractedEntities object.
        Matches the router's normalizer function signature.
        """
        # Wrapper that calls normalize_entity for each field
```

**Global Singleton:**
```python
# Module-level
_index: EntityIndex | None = None

def get_index() -> EntityIndex:
    """Get or create the global EntityIndex instance (lazy initialization)."""
    global _index
    if _index is None:
        executor = _build_executor()  # Build from env vars
        _index = EntityIndex(executor)
    return _index
```

### 2.6 Normalization Function

**Method:** `normalize_entity(entity_type: str, raw: str) -> str | None`

**Logic:**
1. If input is empty/None, return None
2. Lowercase and strip the input
3. Lookup in appropriate index based on entity_type:
   - **gene**: Lookup in `genes_index`, return canonical uppercase symbol or None
   - **therapy**: Lookup in `therapies_index`, return canonical lowercase name or None
   - **disease**: Lookup in `diseases_index`, return canonical name if found, otherwise return input as-is (allows Cypher CONTAINS to handle fuzzy matching)
   - **variant**: Return input as-is (no normalization, let Cypher CONTAINS handle it)
4. If entity_type is unknown, log warning and return None

**Special handling for diseases:** Return the input as-is if not found in index. This allows Cypher CONTAINS to handle fuzzy matching for disease names that aren't in our synonym index. We can refine this strategy later based on usage patterns.

### 2.7 Variant Handling

**Strategy:** No special parsing in the normalizer. The router LLM should extract entities correctly. The normalizer only does canonical name lookup.

**Examples:**
- "KRAS G12C" → Router extracts `{gene: "KRAS", variant: "G12C"}` → Normalizer normalizes gene to "KRAS", variant passes through as "G12C"
- "G12C" → Router extracts `{variant: "G12C"}` → Normalizer passes through as-is (no normalization)

**Rationale:** Variant names are complex and context-dependent. Let the router LLM handle extraction, and let Cypher CONTAINS handle matching in the database.

### 2.8 Handling Ambiguity

If a synonym maps to multiple canonical entities (rare but possible):

**Strategy:**
- Log a warning with both mappings: `"Ambiguous {entity_type} synonym: '{synonym}' maps to both '{canonical1}' and '{canonical2}'"`
- Use the first match encountered (deterministic but arbitrary)
- Future enhancement: Could return a list and let the router/query handle disambiguation, or ask user for clarification in voice

**Example:**
- If "ABC" is a synonym for both "Gene1" and "Gene2", log warning and use whichever was processed first.

### 2.9 Router Integration

**File:** `voice_agent/entities/__init__.py`

Create a `create_normalizer()` function that matches the router's expected signature:

```python
def create_normalizer(index: EntityIndex | None = None) -> Callable[[ExtractedEntities], ExtractedEntities]:
    """
    Create a normalizer function matching router's expected signature.
    
    Args:
        index: Optional EntityIndex instance. If None, uses global singleton.
    
    Returns:
        Function that takes ExtractedEntities and returns normalized ExtractedEntities
    """
    idx = index or get_index()
    
    def normalize(entities: ExtractedEntities) -> ExtractedEntities:
        normalized_gene = idx.normalize_entity("gene", entities.gene) if entities.gene else None
        normalized_therapy = idx.normalize_entity("therapy", entities.therapy) if entities.therapy else None
        normalized_disease = idx.normalize_entity("disease", entities.disease) if entities.disease else None
        normalized_variant = entities.variant  # Pass through, no normalization
        
        return ExtractedEntities(
            gene=normalized_gene,
            therapy=normalized_therapy,
            disease=normalized_disease,
            variant=normalized_variant,
        )
    
    return normalize
```

**Usage:**
```python
from voice_agent.entities import create_normalizer

normalizer = create_normalizer()
result = await router.route_query(transcript, normalizer=normalizer)
```

### 2.10 Error Handling

- **Neo4j connection failure:** Raise exception (fail fast at startup)
- **Empty results:** Indexes will be empty (log warning)
- **Invalid entity types:** Log warning, return None
- **Missing required env vars:** Raise RuntimeError with helpful message

### 2.11 Logging

Log the following:
- Index build start/completion with timing
- Number of entities indexed per type (genes, therapies, diseases)
- Ambiguity warnings (synonym → multiple canonicals)
- Build time for each index type
- Total build time

### 2.12 Testing Strategy

**Unit Tests (`voice_agent/entities/test_index.py`):**
- Mock `Neo4jExecutor` with sample data
- Test index building with known inputs
- Test normalization (exact matches, synonyms, not found)
- Test ambiguity handling (synonym maps to multiple entities)
- Test edge cases (empty synonyms, None values, etc.)

**Integration Tests:**
- Use real Neo4j connection (read-only)
- Test index building from actual database
- Test normalization with real entity names from the database
- Measure and verify build time (<5 seconds target)
- Test that indexes are populated correctly

### Done When
- [x] `EntityIndex` class implemented in `voice_agent/entities/index.py`
- [x] `_build_indexes()` method implemented with three Cypher queries
- [x] Index building logic implemented for genes, therapies, and diseases
- [x] `normalize_entity()` method implemented
- [x] `normalize_entities()` method implemented (wrapper for router integration)
- [x] `get_index()` singleton getter implemented
- [x] `_build_executor()` helper function implemented
- [x] `create_normalizer()` function implemented in `voice_agent/entities/__init__.py`
- [x] Logging added throughout (build times, entity counts, ambiguity warnings)
- [x] Unit tests written with mocked Neo4jExecutor
- [x] Integration tests written with real Neo4j connection
- [x] Ambiguity handling tested and verified
- [x] Index build time measured and logged (<5 seconds acceptable)
- [x] All tests passing

---

## Stage 3: Template Library

**Status:** ✅ COMPLETE

**Goal:** Pre-written Cypher templates for the 10 supported query types.

### 3.1 Template Data Structure

Define a dataclass or Pydantic model:

**QueryTemplate**
- `id`: str — matches intent ID
- `description`: str — human readable
- `required_entities`: list[str] — must be present to execute
- `optional_entities`: list[str] — enhance query if present
- `cypher`: str — Cypher with {entity} placeholders
- `format_response`: Callable — function to format results for voice

### 3.2 Template Specifications

#### Template 1: resistance_biomarkers_query

**Purpose:** Find genes whose variants predict resistance to a therapy

**Required entities:** therapy

**Optional entities:** disease

**Cypher pattern:**
- MATCH Biomarker -[AFFECTS_RESPONSE_TO]-> Therapy
- Filter: therapy name/synonyms match, effect = 'resistance'
- Optional: disease_name CONTAINS filter
- Collapse to gene level using CASE WHEN b:Gene THEN b.symbol ELSE g.symbol END
- Aggregate: COUNT evidence, MIN evidence_level
- Order by evidence_level ASC, count DESC
- Limit 10

**Response format:**
- No results: "I didn't find resistance biomarkers for {therapy}."
- 1-3 results: List all genes with evidence level note
- 4+ results: "Found N genes. Top ones are X, Y, Z with Level A evidence. Want pathway enrichment?"

---

#### Template 2: sensitivity_biomarkers_query

**Purpose:** Find genes whose variants predict sensitivity to a therapy

**Required entities:** therapy

**Optional entities:** disease

**Cypher pattern:** Same as resistance_biomarkers but effect = 'sensitivity'

**Response format:** Same pattern as resistance

---

#### Template 3: therapy_targets_query

**Purpose:** What genes does a therapy target (TARGETS relationship)

**Required entities:** therapy

**Cypher pattern:**
- MATCH Therapy -[TARGETS]-> Gene
- Filter: therapy name/synonyms match
- Return gene symbol, mechanism of action
- Limit 10

**Response format:**
- No results: "I didn't find target genes for {therapy}."
- 1 result: "{therapy} targets {gene} as an {mechanism}."
- Multiple: "{therapy} targets N genes: X, Y, Z."

---

#### Template 4: gene_targeting_therapies_query

**Purpose:** What therapies target a specific gene

**Required entities:** gene

**Cypher pattern:**
- MATCH Therapy -[TARGETS]-> Gene
- Filter: gene symbol/synonyms match
- Return therapy name and mechanism of action (MOA)
- Limit 10

**Response format:**
- No results: "I didn't find therapies targeting {gene}."
- Results: "N therapies target {gene}: X, Y, Z. [All are inhibitors / Various mechanisms]."

---

#### Template 5: gene_variants_query

**Purpose:** List variants of a gene that have clinical evidence

**Required entities:** gene

**Cypher pattern:**
- MATCH Variant -[:VARIANT_OF]-> Gene
- Filter: gene symbol/synonyms match
- MATCH Variant -[AFFECTS_RESPONSE_TO]-> (must have evidence)
- Aggregate by variant: count evidence, min level
- Order by level ASC, count DESC
- Limit 10

**Response format:**
- No results: "{gene} has no variants with clinical evidence in the database."
- Results: "{gene} has N variants with evidence. Most studied are X, Y, Z."

---

#### Template 6: variant_response_query

**Purpose:** How does a specific variant affect response to a specific therapy

**Required entities:** variant, therapy

**Cypher pattern:**
- MATCH Variant -[AFFECTS_RESPONSE_TO]-> Therapy
- Filter: variant name CONTAINS match, therapy name/synonyms match
- Return effect, disease, evidence_level, evidence_count
- Limit 5

**Response format:**
- No results: "I don't have evidence for {variant} affecting {therapy} response."
- Results: "{variant} predicts {sensitivity/resistance} to {therapy} in {disease} with Level {X} evidence."
- Multiple effects: Handle both sensitivity and resistance if present

---

#### Template 7: gene_overview_query

**Purpose:** Summary stats about a gene in the database

**Required entities:** gene

**Cypher pattern:**
- MATCH Gene by symbol/synonyms
- OPTIONAL MATCH variants of gene
- OPTIONAL MATCH therapies targeting gene
- Return gene symbol, variant count, targeting therapy count

**Response format:**
- Not found: "{gene} is not in my database."
- Found: "{gene} has N variants in the database and is targeted by M therapies."

---

#### Template 8: therapy_overview_query

**Purpose:** Summary stats about a therapy in the database

**Required entities:** therapy

**Cypher pattern:**
- MATCH Therapy by name/synonyms
- OPTIONAL MATCH target genes (and their TARGETS MOA)
- OPTIONAL MATCH biomarker evidence pointing to therapy
- Return therapy name, target count, biomarker count, and top-N target genes with MOA

**Response format:**
- Not found: "{therapy} is not in my database."
- Found: "{therapy} is a {modality}. It targets N genes and has M biomarker associations."

---

#### Template 9: disease_biomarkers_query

**Purpose:** Top biomarker genes for a disease

**Required entities:** disease

**Cypher pattern:**
- MATCH Biomarker -[AFFECTS_RESPONSE_TO]-> Therapy
- Filter: disease_name CONTAINS
- Collapse to gene level
- Aggregate: count, min level
- Order by level ASC, count DESC
- Limit 10

**Response format:**
- No results: "I didn't find biomarkers for {disease}."
- Results: "In {disease}, top biomarkers are X, Y, Z with Level A evidence."

---

#### Template 10: disease_therapies_query

**Purpose:** Therapies with biomarker evidence in a disease

**Required entities:** disease

**Cypher pattern:**
- MATCH Biomarker -[AFFECTS_RESPONSE_TO]-> Therapy
- Filter: disease_name CONTAINS
- Aggregate by therapy: count evidence
- Order by count DESC
- Limit 10

**Response format:**
- No results: "I didn't find therapies with biomarker evidence in {disease}."
- Results: "In {disease}, therapies with most evidence are X, Y, Z."

---

### 3.3 Cypher Guidelines (from existing prompts)

Apply these patterns in all templates:
- Always use `toLower()` for string comparisons
- Always check synonyms: `any(s IN coalesce(x.synonyms, []) WHERE toLower(s) = toLower('{value}'))`
- Use `CASE WHEN b:Gene THEN b.symbol ELSE g.symbol END` for gene resolution
- Use `MIN(rel.best_evidence_level)` for aggregated level (A < B lexicographically)
- Always include LIMIT

### 3.4 Template Filling Function

Create `fill_template(template: QueryTemplate, entities: dict) -> str`

Logic:
1. Start with template.cypher
2. Handle optional disease_filter: replace `{disease_filter}` with actual filter or empty string
3. Replace each `{entity}` placeholder with the normalized value
4. Escape single quotes in entity values (replace `'` with `\'`)
5. Return final Cypher string

### 3.5 Response Formatter Guidelines

Each formatter should:
- Accept `results: list[dict]` and `entities: dict`
- Handle empty results gracefully
- Keep response under 3 sentences
- Mention evidence level when available and strong (A/B)
- Offer follow-up actions for rich results ("Want me to run enrichment?")
- Use entity names from input for natural phrasing

### Done When
- [x] QueryTemplate Pydantic model defined (`voice_agent/templates/models.py`)
- [x] All 10 templates written with Cypher (`voice_agent/templates/registry.py`)
- [x] Cypher tested directly against Neo4j (integration tests in `voice_agent/templates/test_templates_integration.py`)
- [x] Response formatters written for all 10 templates (`voice_agent/templates/formatters.py`)
- [x] fill_template function works correctly (`voice_agent/templates/cypher.py`)
- [x] Edge cases handled (empty results, single result, many results) - tested in `voice_agent/templates/test_formatters.py`)
- [x] Cypher utilities implemented (escaping, disease tokenization) - tested in `voice_agent/templates/test_cypher.py`
- [x] Module exports configured (`voice_agent/templates/__init__.py`)

---

## Stage 4: Fast Path Integration

**Status:** ✅ COMPLETE

**Goal:** Wire router → normalization → template → Neo4j → response into one function.

### 4.1 Main Handler Function

Create `handle_query(transcript: str) -> str`

Flow:
1. Call router to get intent + entities + confidence
2. Check confidence threshold (0.6)
3. Check for special intents (conversational, complex, unclear)
4. Look up template by intent ID
5. Validate required entities present
6. Normalize entities
7. Fill template with entities
8. Execute Cypher against Neo4j
9. Format response
10. Return response string

### 4.2 Error Handling

**Low confidence (<0.6):**
Return: "I'm not sure what you're asking. Could you rephrase that?"

**Missing required entity:**
Return: "I need to know the {entity_type}. Which {therapy/gene/disease} are you asking about?"

**Cypher execution error:**
Log error, return: "I ran into a problem looking that up. Could you try asking differently?"

**Empty results:**
Let the formatter handle it (each has empty result messaging)

### 4.3 Neo4j Integration

Reuse your existing Neo4j connection/execution code from the FastAPI backend.

Options:
- Import directly if agent runs alongside backend
- Call backend API endpoint if separate
- Duplicate connection code in agent (simplest for MVP)

For MVP: duplicate the connection code. Avoid network hop.

### 4.4 Latency Tracking

Add timing logs for each step:
- Router LLM call
- Entity normalization
- Cypher execution
- Total end-to-end

Typical breakdown:
- Router: ~1s
- Normalization: <10ms
- Cypher: ~1s
- Formatting: <10ms
- **Total: ~3s**

### 4.5 Testing Without Voice

Create a simple test script:
```
Input: user query string
Output: response string + timing breakdown
```

Test all 10 template types plus edge cases before adding voice.

### Done When
- [x] handle_query function implemented (`voice_agent/handler.py`)
- [x] Router → Template flow works
- [x] Neo4j connection working in agent context (singleton executor pattern)
- [x] All 10 query types tested end-to-end (test script created: `voice_agent/test_handler_cli.py`)
- [x] Error handling covers all cases (low confidence, missing entities, template not found, Cypher errors, formatting errors)
- [x] Latency logged and under 2 seconds for happy path (timing logs for router, template, Cypher, formatting, total)
- [x] Empty results handled gracefully (formatters handle empty results)

### Implementation Notes

- **Router Configuration**: Created `_build_router()` helper function to configure `GeminiRouter` with API keys from environment variables (`GOOGLE_API_KEY`, `GOOGLE_API_KEY_ALT`), following the same pattern as `_build_executor()`.
- **Ambiguous Synonym Logging**: Changed ambiguous synonym warnings from WARNING to DEBUG level in `voice_agent/entities/index.py` to reduce log noise during index building (this is expected behavior when multiple entities share synonyms).

---

## Stage 5: Convert Fast Path to a Tool (Structured, Intent-Specific Output)

**Status:** ✅ COMPLETE

**Goal:** Make your existing router/templates/Neo4j executor callable as a single **tool** that returns small, intent-specific structured JSON. Gemini Flash (the conversational agent) decides when to call it and how to speak.

### 5.1 New Responsibility Split

- **Gemini Flash (conversation brain)**:
  - greetings, thanks, off-topic
  - clarifying questions
  - choosing when to call the tool
  - speaking results in 1–3 sentences

- **OncoGraph tool (fast path engine)**:
  - routing → normalization → template execution → result reduction
  - returns **structured data only**
  - no "conversation", no long text generation

### 5.2 Tool Contract: Discriminated Union (Pydantic)

Use `intent` as the discriminator so the LLM sees a predictable schema and your code stays type-safe.

#### 5.2.1 Core Models (`voice_agent/contracts.py`)

**File:** `voice_agent/contracts.py` (NEW FILE)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, Union, Annotated
from voice_agent.router.models import ExtractedEntities  # Reuse existing model

Status = Literal[
    "ok",
    "needs_clarification",
    "no_results",
    "not_supported",
    "error",
]

# Reuse ExtractedEntities from router/models.py as NormalizedEntities
NormalizedEntities = ExtractedEntities

class VoiceHint(BaseModel):
    """Hints for voice output formatting."""
    speak_top_n: int = Field(default=3, ge=1, le=10)

# Note: No ask_followup or avoid fields - LLM decides follow-ups, 
# and we simply don't include fields we don't want in payloads
```

#### 5.2.2 Intent-Specific Payload Models

All payloads follow this pattern:
- `intent: Literal["..."]` as first field (discriminator)
- Entity names (therapy, gene, disease, variant) when relevant
- `total_*` count field
- `top_*` or `*_list` field with bounded items (3-5 max)
- Evidence levels and counts where applicable

**1. ResistanceBiomarkersPayload**
```python
class ResistanceBiomarkersPayload(BaseModel):
    intent: Literal["resistance_biomarkers_query"]
    therapy: str
    disease: Optional[str] = None  # If provided in query
    total_genes: int
    top_genes: list[dict[str, Union[str, int, None]]] = Field(
        default_factory=list,
        max_length=5
    )
    # top_genes items: {"gene": str, "best_level": str | None, "evidence_count": int}
```

**2. SensitivityBiomarkersPayload**
```python
class SensitivityBiomarkersPayload(BaseModel):
    intent: Literal["sensitivity_biomarkers_query"]
    therapy: str
    disease: Optional[str] = None  # If provided in query
    total_genes: int
    top_genes: list[dict[str, Union[str, int, None]]] = Field(
        default_factory=list,
        max_length=5
    )
    # top_genes items: {"gene": str, "best_level": str | None, "evidence_count": int}
```

**3. TherapyTargetsPayload**
```python
class TherapyTargetsPayload(BaseModel):
    intent: Literal["therapy_targets_query"]
    therapy: str
    total_targets: int
    targets: list[dict[str, Optional[str]]] = Field(
        default_factory=list,
        max_length=5
    )
    # targets items: {"gene": str, "moa": str | None}
```

**4. GeneTargetingTherapiesPayload**
```python
class GeneTargetingTherapiesPayload(BaseModel):
    intent: Literal["gene_targeting_therapies_query"]
    gene: str
    total_therapies: int
    therapies: list[dict[str, Optional[str]]] = Field(
        default_factory=list,
        max_length=5
    )
    # therapies items: {"therapy": str, "moa": str | None}
```

**5. GeneVariantsPayload**
```python
class GeneVariantsPayload(BaseModel):
    intent: Literal["gene_variants_query"]
    gene: str
    total_variants: int
    top_variants: list[dict[str, Union[str, int, None]]] = Field(
        default_factory=list,
        max_length=5
    )
    # top_variants items: {"variant": str, "best_level": str | None, "evidence_count": int}
```

**6. VariantResponsePayload**
```python
class VariantResponsePayload(BaseModel):
    intent: Literal["variant_response_query"]
    variant: str
    therapy: str
    results: list[dict[str, Union[str, int, None]]] = Field(
        default_factory=list,
        max_length=5
    )
    # results items: {"effect": "sensitivity" | "resistance", "disease": str | None, 
    #                 "best_level": str | None, "evidence_count": int}
    # Note: Can mix sensitivity and resistance in same list
```

**7. GeneOverviewPayload**
```python
class GeneOverviewPayload(BaseModel):
    intent: Literal["gene_overview_query"]
    gene: str
    variant_count: int
    therapy_count: int
    # Note: Single object, not a list (query returns one row)
```

**8. TherapyOverviewPayload**
```python
class TherapyOverviewPayload(BaseModel):
    intent: Literal["therapy_overview_query"]
    therapy: str
    target_count: int
    biomarker_count: int
    targets: list[dict[str, Optional[str]]] = Field(
        default_factory=list,
        max_length=5
    )
    # targets items: {"gene": str, "moa": str | None}
    # Note: Includes targets list (like therapy_targets_query)
```

**9. DiseaseBiomarkersPayload**
```python
class DiseaseBiomarkersPayload(BaseModel):
    intent: Literal["disease_biomarkers_query"]
    disease: str
    total_genes: int
    top_genes: list[dict[str, Union[str, int, None]]] = Field(
        default_factory=list,
        max_length=5
    )
    # top_genes items: {"gene": str, "best_level": str | None, "evidence_count": int}
```

**10. DiseaseTherapiesPayload**
```python
class DiseaseTherapiesPayload(BaseModel):
    intent: Literal["disease_therapies_query"]
    disease: str
    total_therapies: int
    therapies: list[dict[str, int]] = Field(
        default_factory=list,
        max_length=5
    )
    # therapies items: {"therapy": str, "evidence_count": int}
```

#### 5.2.3 Discriminated Union and Result Model

```python
Payload = Annotated[
    Union[
        ResistanceBiomarkersPayload,
        SensitivityBiomarkersPayload,
        TherapyTargetsPayload,
        GeneTargetingTherapiesPayload,
        GeneVariantsPayload,
        VariantResponsePayload,
        GeneOverviewPayload,
        TherapyOverviewPayload,
        DiseaseBiomarkersPayload,
        DiseaseTherapiesPayload,
    ],
    Field(discriminator="intent"),
]

class OncoGraphToolResult(BaseModel):
    """Structured result from OncoGraph query tool."""
    status: Status
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: NormalizedEntities = Field(default_factory=NormalizedEntities)
    message: Optional[str] = None  # User-safe message for non-ok statuses
    voice: VoiceHint = Field(default_factory=VoiceHint)
    payload: Optional[Payload] = None  # Present when status="ok"
```

**Key Design Decisions:**
- Reuse `ExtractedEntities` from `router/models.py` instead of duplicating
- `VoiceHint` only contains `speak_top_n` (no `ask_followup`, no `avoid` field)
- Payloads are bounded (max 5 items in lists) to keep responses small
- Evidence levels stored as strings ("A", "B", "C", etc.) or None
- Effect types are literal strings: "sensitivity" or "resistance"

### 5.3 Update `handle_query` Function

**File:** `voice_agent/handler.py`

**Changes:**
- Return type: `str` → `OncoGraphToolResult`
- Remove `debug` parameter (not implementing debug mode)
- Add `speak_top_n: int = 3` parameter (configurable, defaults to 3)
- Pass `speak_top_n` to payload builders

**Status Mapping Rules:**

| Condition | Status | Message |
|-----------|--------|---------|
| Router confidence < 0.6 | `needs_clarification` | "I'm not sure what you're asking. Could you rephrase that?" |
| Missing required entity | `needs_clarification` | "I need to know the {entity_type}. Which {entity_display} are you asking about?" |
| Intent = "conversational" | `not_supported` | "Hi! I'm OncoGraph. Ask me about cancer biomarkers, therapies, or resistance mechanisms." |
| Intent = "complex" | `not_supported` | "That's a complex question that needs more analysis. I'll have results ready in the web dashboard in about a minute. Is there something simpler I can help with now?" |
| Intent = "unclear" | `not_supported` | "I'm not sure I understood that. You can ask me things like 'What causes resistance to cetuximab?' or 'What therapies target BRAF?'" |
| Template not found | `error` | "I ran into a problem processing your query. Could you try asking differently?" |
| Cypher execution error | `error` | "I ran into a problem looking that up. Could you try asking differently?" |
| Empty results (formatter returns None) | `no_results` | Message from formatter (e.g., "I didn't find resistance biomarkers for {therapy}.") |
| Success with results | `ok` | None (payload contains data) |

**Implementation Flow:**
1. Router call → get `RouteResult`
2. Check confidence → return `needs_clarification` if low
3. Handle special intents (`conversational`, `complex`, `unclear`) → return `not_supported`
4. Template lookup → return `error` if not found
5. Entity validation → return `needs_clarification` if missing
6. Template filling → return `error` if fails
7. Cypher execution → return `error` if fails
8. Payload building → call formatter with `speak_top_n`
9. Build `OncoGraphToolResult`:
   - Set `status` based on conditions above
   - Set `confidence` from router result
   - Set `entities` from normalized router entities
   - Set `message` for non-ok statuses
   - Set `voice.speak_top_n` from parameter
   - Set `payload` when status is `ok` and formatter returns payload
   - Return `no_results` if formatter returns None

### 5.4 Refactor Formatters to Payload Builders

**File:** `voice_agent/templates/formatters.py`

**Changes:**
- **Remove:** All string-returning formatter functions
- **Remove:** Helper functions `_number_to_word()`, `_get_evidence_level_text()`, `_format_gene_list()` (not needed for structured data)
- **Keep:** `_clean_value()` helper (still useful for extracting values from Neo4j results)
- **Add:** 10 new payload builder functions

**Payload Builder Function Signatures:**

```python
def build_resistance_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> ResistanceBiomarkersPayload | None:
    """Build payload for resistance biomarkers query. Returns None if no results."""

def build_sensitivity_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> SensitivityBiomarkersPayload | None:
    """Build payload for sensitivity biomarkers query. Returns None if no results."""

def build_therapy_targets_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> TherapyTargetsPayload | None:
    """Build payload for therapy targets query. Returns None if no results."""

def build_gene_targeting_therapies_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> GeneTargetingTherapiesPayload | None:
    """Build payload for gene targeting therapies query. Returns None if no results."""

def build_gene_variants_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> GeneVariantsPayload | None:
    """Build payload for gene variants query. Returns None if no results."""

def build_variant_response_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> VariantResponsePayload | None:
    """Build payload for variant response query. Returns None if no results."""

def build_gene_overview_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> GeneOverviewPayload | None:
    """Build payload for gene overview query. Returns None if gene not found."""

def build_therapy_overview_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> TherapyOverviewPayload | None:
    """Build payload for therapy overview query. Returns None if therapy not found."""

def build_disease_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> DiseaseBiomarkersPayload | None:
    """Build payload for disease biomarkers query. Returns None if no results."""

def build_disease_therapies_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> DiseaseTherapiesPayload | None:
    """Build payload for disease therapies query. Returns None if no results."""
```

**Payload Builder Logic:**
1. Check if results are empty → return `None`
2. Extract entity names from `entities` dict (therapy, gene, disease, variant)
3. Extract data from Neo4j results:
   - For list payloads: extract top N items (bounded by `speak_top_n`, max 5)
   - For single-object payloads: extract single row
4. Build structured payload objects:
   - Set `intent` field
   - Set entity names (therapy, gene, disease, variant)
   - Set `total_*` count
   - Set `top_*` or `*_list` with bounded items
   - Extract evidence levels and counts where applicable
5. Return payload model instance, or `None` if no results

**Special Cases:**
- `gene_overview_query` and `therapy_overview_query`: Check if gene/therapy exists (results empty or counts are 0) → return `None`
- `variant_response_query`: Can have both sensitivity and resistance results in same list
- `therapy_overview_query`: Include `targets` list (like `therapy_targets_query`)

### 5.5 Update Template Registry

**File:** `voice_agent/templates/registry.py`

**Changes:**
- Update all template definitions to use new payload builders
- Update `format_response` references from old formatters to new payload builders

**File:** `voice_agent/templates/models.py`

**Changes:**
- Update `QueryTemplate.format_response` type signature:
  - From: `Callable[[list[dict[str, object]], dict[str, str | None], int], str]`
  - To: `Callable[[list[dict[str, object]], dict[str, str | None], int], BaseModel | None]`

### 5.6 Update Test CLI

**File:** `voice_agent/test_handler_cli.py`

**Changes:**
- Update to print JSON output: `result.model_dump_json(indent=2)`
- Add `--speak-top-n` argument (default 3)
- Pretty print JSON for readability
- Update error handling to work with `OncoGraphToolResult`

**Example Output:**
```json
{
  "status": "ok",
  "confidence": 1.0,
  "entities": {
    "gene": null,
    "therapy": "cetuximab",
    "disease": null,
    "variant": null
  },
  "message": null,
  "voice": {
    "speak_top_n": 3
  },
  "payload": {
    "intent": "resistance_biomarkers_query",
    "therapy": "cetuximab",
    "disease": null,
    "total_genes": 5,
    "top_genes": [
      {"gene": "KRAS", "best_level": "A", "evidence_count": 88},
      {"gene": "BRAF", "best_level": "B", "evidence_count": 45},
      {"gene": "PIK3CA", "best_level": "C", "evidence_count": 23}
    ]
  }
}
```

### 5.7 Update Tests

**File:** `voice_agent/templates/test_formatters.py`

**Changes:**
- Remove tests for old string formatters
- Add tests for all 10 payload builders:
  - Test with sample Neo4j results
  - Test empty results (returns None)
  - Test `speak_top_n` limiting (max 5 items)
  - Test evidence level extraction
  - Test entity name extraction from entities dict

**File:** `voice_agent/test_handler_cli.py` (if tests exist)

**Changes:**
- Update to expect `OncoGraphToolResult` instead of string
- Test status mapping for all error cases
- Test success path with all 10 query types

### 5.8 Gemini Flash Agent Prompt (System Instruction Snippet)

This is the "policy" that makes voice feel good. (To be implemented in Stage 6)

```text
You are OncoGraph, a voice assistant for oncology research using a curated knowledge graph.

Use the oncograph_query tool when the user asks about:
- resistance or sensitivity biomarkers for a therapy
- what a therapy targets, or what therapies target a gene
- variant response evidence (variant vs therapy)
- disease-specific top biomarkers or therapies with evidence
- gene or therapy overview in the database

Do NOT read PMIDs, URLs, or Cypher aloud.

Speaking style:
- 1 to 3 sentences.
- If there are many items, name the top three and say "and X others."
- Mention evidence level only when A or B appears.
- Ask one short follow-up question when helpful.

If the tool returns needs_clarification, ask exactly one clarifying question.

If the user asks for pathway enrichment, say it is not available in voice mode and offer a supported query type instead.

This is for research/education only, not medical advice.
```

### 5.9 Tool Description Snippet (what Gemini sees)

```text
Tool: oncograph_query
Description:
Query the OncoGraph knowledge graph (Neo4j) for oncology biomarkers, therapy targets,
variant response evidence, and disease-specific evidence. Returns a small structured
result with counts and top items.

Input:
- query: natural language question

Output:
- status: ok | needs_clarification | no_results | not_supported | error
- entities: normalized gene/therapy/disease/variant (when available)
- payload: intent-specific structured data (top results only)
- message: short user-safe message for non-ok outcomes
```

### Done When
- [x] `voice_agent/contracts.py` created with all Pydantic models (Status, VoiceHint, 10 payload models, Payload union, OncoGraphToolResult)
- [x] All 10 payload builder functions implemented in `voice_agent/templates/formatters.py`
- [x] Old string formatters removed from `voice_agent/templates/formatters.py`
- [x] `QueryTemplate.format_response` type signature updated in `voice_agent/templates/models.py`
- [x] All templates updated in `voice_agent/templates/registry.py` to use new payload builders
- [x] `handle_query` updated to return `OncoGraphToolResult` with correct status mapping
- [x] `handle_query` accepts `speak_top_n` parameter and passes it to payload builders
- [x] Test CLI updated to print JSON output with `--speak-top-n` argument
- [x] All formatter tests updated to test payload builders
- [x] Handler tests updated to expect `OncoGraphToolResult`
- [x] All 10 query types tested end-to-end and return correct payloads (via template + builder tests and existing integration tests)
- [x] Error cases tested (low confidence, missing entities, empty results, Cypher errors)


---

## Stage 6: Wire in LiveKit (Voice MVP)

**Status:** ✅ COMPLETE

**Goal:** Put the “Gemini Flash + oncograph_query tool” loop behind realtime voice using LiveKit Agents, LiveKit Cloud, and LiveKit Inference (Gemini LLM, Deepgram STT, Cartesia TTS).

### 6.1 Architecture & Hosting (Local Development + LiveKit Cloud)

- **Agent hosting:** Run the voice agent as a **LiveKit Agent**. For Stage 6, tested locally first; deployment to **LiveKit Cloud** follows in Stage 8.
- **Code location:** Package the existing `voice_agent` Python package (router, entities, templates, `handler.py`, `contracts.py`) into the agent container so all tool logic runs **inside** the agent.
- **Database access:** The agent connects **directly to Neo4j** using the existing `Neo4jExecutor` and env vars (same as Render), over the public network.
  - For local dev: Use existing `.env` file with Neo4j credentials.
  - For LiveKit Cloud: Configure `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` as **LiveKit Cloud secrets**.
  - Ensure Neo4j is reachable from LiveKit Cloud (public endpoint or firewall rules that allow Cloud IP ranges).
- **Frontend:** For Stage 6 initial testing, used LiveKit **Agent Playground / Voice AI quickstart UI**. Frontend integration with existing OncoGraph web app follows in Stage 7.

This matches LiveKit's standard model: the agent is a normal Python process that can call any Python code and talk to external services (like Neo4j) over the network.

### 6.2 Models: Gemini LLM + Deepgram STT + Cartesia TTS via LiveKit Inference

- Use **LiveKit Inference** to simplify model wiring for MVP (can later swap to provider plugins if needed).
- **LLM (Gemini):**
  - Configure Gemini (e.g., Gemini Flash) as the conversational LLM in the agent’s LLM config, served via LiveKit Inference.
  - Provide the Stage 5.8/5.9-style **system prompt** that describes:
    - OncoGraph’s capabilities and tool usage.
    - Voice style (1–3 sentences, top 3 items, evidence A/B only, no PMIDs/URLs).
    - Status handling (`ok`, `needs_clarification`, `no_results`, `not_supported`, `error`).
- **STT (Deepgram):**
  - Configure Deepgram as the STT model via LiveKit Inference (preferred) or the Deepgram STT plugin.
  - Set language (e.g. `en`) and a high-accuracy model (e.g. Nova-3-Medical) tuned for medical terminology.
- **TTS (Cartesia):**
  - Configure Cartesia TTS via LiveKit Inference (preferred) or Cartesia TTS plugin.
  - Choose a default Cartesia voice (clear, neutral, professional) and keep speaking rate natural.
- **Migration path:** If LiveKit Inference free usage is not sufficient, swap the model configs to use the Gemini, Deepgram, and Cartesia **plugins** with your own provider keys, without changing `oncograph_query` or Neo4j logic.

### 6.3 Agent Server Entrypoint & Session Setup

- Create `voice_agent/voice_server.py` with:
  - An `AgentServer` instance configured for LiveKit Cloud deployment (per LiveKit Agents docs).
  - A `@server.rtc_session()`-decorated function that:
    - Creates an `AgentSession` wired to:
      - Gemini LLM (Inference).
      - Deepgram STT (Inference).
      - Cartesia TTS (Inference).
    - Sets the **system instructions** (Stage 5.8/5.9 prompt) on the LLM node.
    - Registers the `oncograph_query` tool (see 6.4).
    - Enables default turn detection and interruption behavior (no extra tuning needed for MVP).
- The agent session should join a room as an **agent participant**, listen for audio, and speak replies using the configured models.

### 6.4 `oncograph_query` Tool Definition

- Define a tool in `voice_agent/tools.py` (or alongside `voice_server.py`) using LiveKit’s `@function_tool` decorator:
  - **Signature:** `async def oncograph_query(query: str) -> dict:`
  - **Behavior:**
    - Calls `result = await handle_query(query, speak_top_n=3)` from `voice_agent/handler.py`.
    - `handle_query` returns `OncoGraphToolResult` (from `voice_agent/contracts.py`).
    - Return `result.model_dump()` (or equivalent JSON-serializable dict) as the tool output.
  - The tool itself does **no natural language generation**; it only returns structured data.
- Register this tool in the agent’s LLM/tool configuration so Gemini can:
  - Decide **when** to call it (for graph questions only).
  - See the full `OncoGraphToolResult` schema (status, entities, payload) for response planning.

### 6.5 Conversation Policy & Tool Usage

- In the Gemini system prompt (LLM config), encode the Stage 5.8/5.9 behavior:
  - **When to call the tool:**
    - Use `oncograph_query` for questions about biomarkers, therapies, variants, and diseases that match the 10 intents.
    - Do **not** call the tool for greetings, thanks, small talk, or clearly off-topic queries.
  - **Status handling:**
    - `status="ok"`: summarize the payload in 1–3 short sentences, naming the top 3 items and optionally mentioning evidence level A/B.
    - `status="needs_clarification"`: ask exactly **one** clarifying question using the `message` field.
    - `status="no_results"`: say you didn’t find results and suggest a simple rephrase, using `message` if provided.
    - `status="not_supported"`: explain briefly that the question is too complex or unsupported in voice mode, and suggest an example supported query.
    - `status="error"`: give a generic “I ran into a problem, please try again” reply (no stack traces).
  - **List behavior:** When many items exist, speak only the top 3 plus “and N others,” where `speak_top_n` comes from `voice.voice_hint`.
  - **Safety:** Never give medical advice; emphasize research/education only.

### 6.6 Voice UX Guardrails

- If STT produces uncertain or misheard therapy/gene names (common with drug names):
  - Let the `oncograph_query` tool attempt normalization using the entity index.
  - If the tool returns `needs_clarification`, ask a single concise question like: “Which therapy did you mean?”
- Don’t read out long lists or raw counts:
  - Always limit spoken items to the top 3 plus “and N others” when appropriate.
- Avoid PMIDs, URLs, or raw Cypher; keep responses high-level and conversational.

### 6.7 Logging & Observability

- Inside the agent / tool code, log per turn (server-side only):
  - User transcript text (from STT).
  - Tool status/intent/confidence/entities from `OncoGraphToolResult`.
  - Neo4j execution time and total tool latency.
- Use LiveKit Cloud’s **agent logs and traces** to debug latency and tool-calling behavior.
- Do **not** expose internal logs or stack traces to the LLM or to the user.

### Done When
- [x] You can join a LiveKit room and ask at least one query per template type by voice
- [x] Latency feels okay (fast path <2s, otherwise short acknowledgement)
- [x] Clarifications work naturally via Gemini + tool status

### Implementation Notes

- **Agent Server**: Created `voice_agent/voice_server.py` with `AgentServer` and `@server.rtc_session()` entrypoint
- **Tool Definition**: Implemented `oncograph_query` as `@function_tool()` that calls `handle_query()` and returns `OncoGraphToolResult` as dict
- **Models via LiveKit Inference**:
  - LLM: `google/gemini-2.5-flash-lite`
  - STT: `deepgram/nova-3-medical:en`
  - TTS: `cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc`
- **System Instructions**: Comprehensive prompt covering tool usage, status handling, and voice constraints
- **Logging Configuration**: Suppressed verbose DEBUG logs from Neo4j, httpx, and other third-party libraries while keeping INFO logs for agent lifecycle and query processing
- **Testing**: Created `voice_agent/test_tool_local.py` to test tool function independently; verified end-to-end voice queries work correctly


---

## Stage 7: Integrate Voice with OncoGraph Frontend

**Status:** ✅ COMPLETE

**Goal:** Add voice interaction UI to the existing OncoGraph web application (`web/`) so users can query the knowledge graph via voice from the main interface. This enables local demos before deploying to LiveKit Cloud.

### 7.1 Architecture Decisions

**LiveKit Connection Setup:**
- **Local Development:** Agent runs locally via `python -m voice_agent.voice_server dev`
- **Frontend Connection:** Frontend connects to LiveKit Cloud SFU (same as LiveKit Playground)
- **Room Management:** Create unique rooms per session (`voice-{userId}-{timestamp}`)
- **Token Generation:** Backend endpoint `/api/voice/token` generates LiveKit access tokens server-side

**Component Structure (implemented):**
```
web/app/
├── voice/
│   └── page.tsx                    # Voice tab page route
├── components/
│   ├── VoicePanel.tsx              # Main voice component (controls + results)
│   └── MiniGraph.tsx               # Reused for subgraph visualisation
└── contexts/
    └── AppContext.tsx              # Extended with voiceState + persistence
```

**Dependencies:**
- Install `livekit-client` npm package for LiveKit SDK
- Optional: `@livekit/components-react` for React hooks/components (can add later if needed)

### 7.2 New Tab & Route

**TopBar Integration:**
- Add third tab "Voice Agent" to `TopBar.tsx` tabs array
- Route: `/voice` → `web/app/voice/page.tsx`
- Match existing tab styling and navigation patterns

**Page Component:**
- Create `web/app/voice/page.tsx` that renders `<VoicePanel />`
- Similar structure to `web/app/page.tsx` (Graph Q&A)

### 7.3 State Management

**Add Voice State to AppContext:**
- Extend `AppContext.tsx` with `voiceState` similar to `graphState` and `hypothesisState`
- Persist to localStorage with key `oncograph_voice_state`
- State structure:

```typescript
type VoiceState = {
  isConnected: boolean;
  isListening: boolean;
  isAgentSpeaking: boolean;
  roomName: string | null;
  userTranscript: string | null;        // Current user speech transcript
  agentResponse: string | null;          // Agent's spoken response text
  toolResult: OncoGraphToolResult | null; // Latest tool call result
  error: string | null;
  connectionHistory: Array<{           // History of tool calls/responses
    timestamp: number;
    userTranscript: string;
    agentResponse: string;
    toolResult: OncoGraphToolResult | null;
  }>;
};
```

**State Persistence:**
- Save to localStorage on state changes (like Graph Q&A)
- Load from localStorage on mount
- Clear state on "Clear All" button click

### 7.4 LiveKit Integration

**Connection Flow:**
1. User clicks "Start Voice" button
2. Frontend calls `/api/voice/token` endpoint with room name
3. Backend generates LiveKit access token and returns it
4. Frontend connects to LiveKit room using `livekit-client` SDK
5. Request microphone permission (if not already granted)
6. Publish microphone track to room
7. Subscribe to agent audio tracks
8. Handle connection events (connected, disconnected, reconnecting)

**Room Connection Code Pattern (implemented):**
```typescript
import {
  Room,
  RoomEvent,
  Track,
  ConnectionState,
  createLocalAudioTrack,
  type LocalAudioTrack,
} from "livekit-client";

const room = new Room();
await room.connect(LIVEKIT_URL, token);

// Start audio playback (required by browsers for autoplay)
await room.startAudio();

// Publish microphone
const micTrack = await createLocalAudioTrack();
await room.localParticipant.publishTrack(micTrack);

// Subscribe to remote (agent) audio
room.on(RoomEvent.ParticipantConnected, (participant) => {
  participant.audioTracks.forEach((publication) => {
    if (publication.track) {
      publication.track.attach(audioElement);
    }
  });

  participant.on("trackSubscribed", (track: Track) => {
    if (track.kind === "audio") {
      track.attach(audioElement);
    }
  });
});

room.on(RoomEvent.TrackSubscribed, (track: Track) => {
  if (track.kind === "audio") {
    track.attach(audioElement);
  }
});
```

**Connection States:**
- `disconnected` → Show "Start Voice" button
- `connecting` → Show "Connecting..." with spinner
- `connected` → Show "Connected" with mic button active
- `reconnecting` → Show "Reconnecting..." with retry option
- `disconnected` (error) → Show error message with retry button

### 7.5 Backend Token Endpoint

**Endpoint:** `POST /api/voice/token`

**Request:**
```json
{
  "room_name": "voice-user123-1234567890",
  "user_identity": "user123"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "url": "wss://your-project.livekit.cloud"
}
```

**Implementation (FastAPI):**
- Use `livekit` Python SDK to generate access tokens
- Include permissions: `canPublish`, `canSubscribe`, `canPublishData`
- Set expiration: 1 hour (or configurable)
- Environment variables: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### 7.6 Payload Transformation Utility

**File:** `web/app/utils/voicePayloadToRows.ts`

**Function:** `payloadToMiniGraphRows(payload: Payload): Array<Record<string, unknown>>`

Transform tool payloads into MiniGraph-compatible row format. MiniGraph expects rows with fields like `gene_symbol`, `therapy_name`, `variant_name`, `effect`, `disease_name`, `targets_moa`, `relationship`, `evidence_levels`, `evidence_count`.

**Transformation Mappings:**

**1. `resistance_biomarkers_query` & `sensitivity_biomarkers_query`:**
```typescript
payload.top_genes.map(gene => ({
  gene_symbol: gene.gene,
  therapy_name: payload.therapy,
  disease_name: payload.disease || null,
  effect: intent === "resistance_biomarkers_query" ? "resistance" : "sensitivity",
  evidence_levels: gene.best_level ? [gene.best_level] : [],
  evidence_count: gene.evidence_count || 0,
  total_genes: payload.total_genes,  // Metadata
}))
```

**2. `therapy_targets_query`:**
```typescript
payload.targets.map(target => ({
  therapy_name: payload.therapy,
  gene_symbol: target.gene,
  targets_moa: target.moa || null,
  relationship: "TARGETS",
  total_targets: payload.total_targets,  // Metadata
}))
```

**3. `gene_targeting_therapies_query`:**
```typescript
payload.therapies.map(therapy => ({
  gene_symbol: payload.gene,
  therapy_name: therapy.therapy,
  targets_moa: therapy.moa || null,
  relationship: "TARGETS",
  total_therapies: payload.total_therapies,  // Metadata
}))
```

**4. `gene_variants_query`:**
```typescript
payload.top_variants.map(variant => ({
  gene_symbol: payload.gene,
  variant_name: variant.variant,
  evidence_levels: variant.best_level ? [variant.best_level] : [],
  evidence_count: variant.evidence_count || 0,
  total_variants: payload.total_variants,  // Metadata
}))
```

**5. `variant_response_query`:**
```typescript
payload.results.map(result => ({
  variant_name: payload.variant,
  therapy_name: payload.therapy,
  disease_name: result.disease || null,
  effect: result.effect,  // "sensitivity" or "resistance"
  evidence_levels: result.best_level ? [result.best_level] : [],
  evidence_count: result.evidence_count || 0,
}))
```

**6. `gene_overview_query`:**
```typescript
// Return empty array - summary stats only, no relationships to visualize
// Show placeholder message: "Summary statistics only - no graph visualization available"
[]
```

**7. `therapy_overview_query`:**
```typescript
payload.targets.map(target => ({
  therapy_name: payload.therapy,
  gene_symbol: target.gene,
  targets_moa: target.moa || null,
  relationship: "TARGETS",
  target_count: payload.target_count,  // Metadata
  biomarker_count: payload.biomarker_count,  // Metadata
}))
```

**8. `disease_biomarkers_query`:**
```typescript
payload.top_genes.map(gene => ({
  gene_symbol: gene.gene,
  disease_name: payload.disease,
  evidence_levels: gene.best_level ? [gene.best_level] : [],
  evidence_count: gene.evidence_count || 0,
  total_genes: payload.total_genes,  // Metadata
  // Note: No therapy or effect - these are disease-level biomarkers
  // MiniGraph will show disease → gene nodes (no AFFECTS_RESPONSE_TO edges)
}))
```

**9. `disease_therapies_query`:**
```typescript
// Return empty array - therapy list with counts only, no relationships to visualize
// Show placeholder message: "Summary statistics only - no graph visualization available"
[]
```

**Special Handling:**
- Transform all items in `top_*` arrays (up to 5 max) for visualization
- Store `evidence_levels` as array format `string[]` (even if payload has single `best_level`)
- Include metadata fields (`total_genes`, `total_therapies`, etc.) in rows
- For empty/no-visualization cases, return empty array and show placeholder message in UI

### 7.7 UI Layout (Matching GraphPanel Style)

**VoicePanel Component Structure:**

```
┌─────────────────────────────────────────────────────────┐
│ Voice Controls (Top Bar)                                │
│ [Mic Button] [Connection Status] [Transcript]            │
└─────────────────────────────────────────────────────────┘
│                                                           │
│ Agent Response Card (Full Width)                        │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Question: "What causes resistance to cetuximab?"    │ │
│ │ Answer: "KRAS, BRAF, and PIK3CA predict resistance │ │
│ │          to cetuximab with Level A evidence..."      │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌──────────────────────┬──────────────────────────────┐ │
│ │ Interactive Subgraph │ Raw Results (JSON)          │ │
│ │                      │                              │ │
│ │   [MiniGraph]        │ {                            │ │
│ │                      │   "status": "ok",            │ │
│ │                      │   "payload": {...}           │ │
│ │                      │ }                            │ │
│ └──────────────────────┴──────────────────────────────┘ │
```

**Component Breakdown:**

**VoiceControls (Top Section):**
- Microphone button (toggle mute/unmute, visual feedback)
- Connection status indicator (connected/disconnected/connecting)
- User transcript display (real-time, optional)
- Agent speaking indicator (waveform or spinner)

**Agent Response Card:**
- Display user's question (from transcript)
- Display agent's spoken response (from agent response text)
- Match GraphPanel's "Answer" card styling

**VoiceResults (Bottom Section):**
- Left column: MiniGraph visualization (reuse existing `MiniGraph` component)
- Right column: Raw JSON payload (expandable/collapsible, syntax-highlighted)
- Show placeholder message if no visualization available (`gene_overview_query`, `disease_therapies_query`)

**Styling:**
- Match existing GraphPanel card styles, layout-row, layout-column classes
- Use same color scheme, fonts, spacing as Graph Q&A tab
- Responsive design (stack columns on mobile)

### 7.8 Tool Result Display

**Capturing Tool Results:**
- Listen to LiveKit data channel messages or room events
- When agent calls `oncograph_query` tool, capture the result
- Store in `voiceState.toolResult` and `voiceState.connectionHistory`

**Display Logic:**
- If `toolResult.status === "ok"` and `toolResult.payload` exists:
  - Transform payload to rows using `payloadToMiniGraphRows()`
  - Pass rows to `MiniGraph` component
  - Display raw JSON in right column
- If `toolResult.status === "no_results"`:
  - Show message: `toolResult.message` or "No results found"
  - No graph visualization
- If `toolResult.status === "needs_clarification"`:
  - Show clarification message
  - No graph visualization
- If `toolResult.status === "not_supported"` or `"error"`:
  - Show error message
  - No graph visualization

**History:**
- Store each tool call in `connectionHistory` array
- Allow user to browse previous queries/results (optional, can add later)

### 7.9 Error Handling

**Connection Errors:**
- Network failures: Show "Connection failed. Please check your internet and try again."
- Token generation failures: Show "Failed to start voice session. Please try again."
- Microphone permission denied: Show "Microphone access denied. Please enable microphone permissions in your browser."
- Room connection timeout: Show "Connection timeout. Please try again."

**Agent Errors:**
- Agent disconnection: Show "Agent disconnected. Reconnecting..." with auto-retry
- Agent not found: Show "Agent not available. Please try again later."
- Tool execution errors: Display `toolResult.message` if available

**Recovery:**
- Provide "Retry" button for failed connections
- Auto-reconnect on network recovery (if supported by LiveKit SDK)
- Clear error state on successful reconnection

### 7.10 Testing Strategy

**Local Testing Setup (implemented):**
1. Run voice agent locally: `python -m voice_agent.voice_server dev`
2. Run FastAPI backend: `python -m api.main` (or existing startup command)
3. Run frontend: `cd web && npm run dev`
4. Navigate to `/voice` tab in browser
5. Click **Start Voice**, accept microphone permission, and verify greeting + responses

**Key Test Cases (completed):**
- [x] Voice tab appears in TopBar navigation
- [x] VoicePanel renders correctly on `/voice` route
- [x] "Start Voice" button requests microphone permission
- [x] Token endpoint generates valid LiveKit tokens
- [x] Frontend connects to LiveKit room successfully
- [x] Microphone audio is published to room
- [x] Agent audio is received and played back (greeting + answers)
- [x] Basic error handling works (token / mic failures)
- [x] State persists to localStorage and is cleared by "Clear All"
- [x] UI matches existing OncoGraph design system

**Current limitation:** Tool results are not yet sent from the agent to the frontend over data channels, so `MiniGraph` and raw JSON panels are wired up in the UI but will only populate once Stage 6/agent-side streaming is extended to emit `OncoGraphToolResult` payloads.

**Query Type Coverage:**
Test all 10 query types:
1. `resistance_biomarkers_query`
2. `sensitivity_biomarkers_query`
3. `therapy_targets_query`
4. `gene_targeting_therapies_query`
5. `gene_variants_query`
6. `variant_response_query`
7. `gene_overview_query` (placeholder message)
8. `therapy_overview_query`
9. `disease_biomarkers_query`
10. `disease_therapies_query` (placeholder message)

### Done When
- [x] Voice tab added to TopBar navigation
- [x] `/voice` route and `VoicePanel` component created
- [x] `voiceState` added to `AppContext` with localStorage persistence
- [x] `/api/voice/token` endpoint implemented in FastAPI backend
- [x] LiveKit client SDK integrated (`livekit-client` installed)
- [x] Room connection, microphone publishing, and audio subscription working
- [x] `payloadToMiniGraphRows()` utility function implemented with all 10 query type mappings
- [x] UI matches GraphPanel styling and layout
- [x] Error handling covers core failure modes (token, mic, connection)
- [x] State persistence working correctly
- [x] Local demo works without LiveKit Cloud deployment
- [ ] Agent sends structured tool results over data channels and UI renders MiniGraph + raw JSON (follow-up enhancement)

### Implementation Notes

- **LiveKit Connection:** Frontend connects to LiveKit Cloud SFU, agent runs locally via `voice_server dev`
- **Token Security:** Always use backend endpoint for token generation (never expose API secret in frontend)
- **Payload Transformation:** Transform all items (up to 5) for visualization, regardless of `speak_top_n`
- **State Persistence:** Use same localStorage pattern as Graph Q&A (`oncograph_voice_state` key)
- **Design Consistency:** Match GraphPanel card styles, layout-row, layout-column classes exactly
- **Error Messages:** Keep user-friendly, no technical jargon or stack traces
- **Microphone Permissions:** Request on first use, handle denial gracefully with clear instructions

---

## Stage 8: Deploy Voice Worker to LiveKit Cloud (Demo-Ready)

**Status:** ⏳ Not Started

**Goal:** Deploy the voice agent to LiveKit Cloud so it's always-on and accessible from the frontend without running local code. This enables production-ready demos.

**Prerequisites:** Stage 7 (Frontend Integration) should be complete so the frontend can connect to the deployed agent.

### 8.1 LiveKit Cloud Deployment

**Agent deployment:**
- Package `voice_agent` Python package for LiveKit Cloud deployment
- Configure LiveKit Cloud project with agent worker settings
- Set environment variables/secrets:
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `GOOGLE_API_KEY` (for Gemini LLM)
  - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (if not using Inference)
- Ensure agent worker has network access to Neo4j (public endpoint or firewall rules)

**Deployment method:**
- Use LiveKit CLI: `lk agent deploy` (or follow LiveKit Cloud dashboard instructions)
- Or use Docker container with LiveKit agent runtime
- Configure auto-scaling if needed (for multiple concurrent sessions)

### 8.2 Agent Worker Configuration

**Startup behavior:**
- Agent worker builds entity index at startup (logs build time)
- Health check endpoint verifies Neo4j connectivity
- Graceful shutdown handling (finish active sessions before stopping)

**Resource requirements:**
- Memory: Sufficient for entity index (~100-200MB) + Python runtime
- CPU: Adequate for LLM calls and Neo4j queries (2+ cores recommended)
- Network: Low latency to Neo4j and LiveKit Cloud SFU

### 8.3 Environment Variable Management

**Required secrets (LiveKit Cloud):**
- `NEO4J_URI`: Neo4j database connection string
- `NEO4J_USER`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password
- `GOOGLE_API_KEY`: Google API key for Gemini (if not using LiveKit Inference)
- `GOOGLE_API_KEY_ALT`: Alternate API key for rate limit fallback (optional)

**Optional configuration:**
- `LOG_LEVEL`: Set to `INFO` (default) or `DEBUG` for troubleshooting
- `ENTITY_INDEX_REBUILD`: Force entity index rebuild on startup (default: false)

### 8.4 Health Checks & Monitoring

**Health check endpoint:**
- Implement `/healthz` endpoint in agent server (if supported by LiveKit Cloud)
- Verify Neo4j connectivity
- Check entity index is loaded
- Return 200 OK if healthy, 503 if unhealthy

**Monitoring:**
- Use LiveKit Cloud's built-in agent logs and traces
- Monitor latency metrics (router, Neo4j, total tool execution)
- Track error rates and tool call success rates
- Set up alerts for high error rates or latency spikes

### 8.5 Timeout & Error Handling

**Timeouts:**
- Router LLM call: 5 seconds (already implemented)
- Neo4j query: 10 seconds (already implemented)
- Tool execution: 15 seconds total (fail gracefully)
- Agent session: No timeout (let user disconnect naturally)

**Error handling:**
- All errors return user-safe messages (no stack traces)
- Log errors server-side for debugging
- Retry logic for transient failures (rate limits, network issues)

### 8.6 Frontend Configuration Update

**Update frontend to use LiveKit Cloud:**
- Set `LIVEKIT_URL` to LiveKit Cloud project URL
- Update token generation endpoint to use LiveKit Cloud credentials
- Test connection from production frontend to deployed agent

### Done When
- [ ] Agent worker deployed to LiveKit Cloud and running
- [ ] Entity index builds successfully on startup
- [ ] Health checks pass (Neo4j connectivity verified)
- [ ] Frontend can connect to deployed agent
- [ ] Voice queries work end-to-end from production frontend
- [ ] No local code execution required for demos
- [ ] Monitoring shows stable latency and low error rates


---

## Stage 9: Demo Polish

**Goal:** Crisp, predictable demo.

- Script 6–8 canonical voice queries (one per template type)
- Add “fallback examples”:
  - enrichment request (refusal)
  - complex comparison (not_supported)
  - misheard entity (needs_clarification)
- Add README section:
  - architecture diagram (voice loop + tool)
  - template list
  - limitations

### Done When
- [ ] 2-minute demo is repeatable and robust
- [ ] Logs show stable latency and successful routing

---

## Appendix A: File Structure

Suggested organization:

```
voice_agent/
├── router/
│   ├── __init__.py
│   ├── models.py          # Pydantic models (RouteResult, ExtractedEntities, etc.)
│   ├── classifier.py      # Router LLM call
│   └── prompts.py         # Router prompt template
├── entities/
│   ├── __init__.py         # Export EntityIndex, get_index(), create_normalizer()
│   └── index.py            # EntityIndex class, index building, normalization
├── templates/              # (Stage 3 - COMPLETE)
│   ├── __init__.py
│   ├── models.py          # QueryTemplate dataclass
│   ├── registry.py        # TEMPLATES dict with all 10 templates
│   ├── cypher.py          # Template filling logic
│   └── formatters.py      # Payload builder functions (Stage 5)
├── handler.py             # Main handle_query function (Stage 4)
├── contracts.py           # OncoGraphToolResult and payload models (Stage 5)
├── voice_server.py        # LiveKit agent server entrypoint (Stage 6)
└── test_handler_cli.py    # Test script for non-voice testing
```

**Note:** Neo4j connection is handled by reusing `Neo4jExecutor` from `src/pipeline/executor.py`. No separate `db.py` needed.

---

## Appendix B: Template Quick Reference

| ID | Required | Optional | Returns |
|----|----------|----------|---------|
| resistance_biomarkers_query | therapy | disease | gene, count, level |
| sensitivity_biomarkers_query | therapy | disease | gene, count, level |
| therapy_targets_query | therapy | — | gene, mechanism |
| gene_targeting_therapies_query | gene | — | therapy, mechanism, modality |
| gene_variants_query | gene | — | variant, count, level |
| variant_response_query | variant, therapy | — | effect, disease, level |
| gene_overview_query | gene | — | variant_count, therapy_count |
| therapy_overview_query | therapy | — | modality, target_count, biomarker_count |
| disease_biomarkers_query | disease | — | gene, count, level |
| disease_therapies_query | disease | — | therapy, count |

---

## Appendix C: Router Intent Reference

| Intent | Confidence Notes |
|--------|------------------|
| resistance_biomarkers_query | Keywords: "resistance", "resistant", "doesn't respond" |
| sensitivity_biomarkers_query | Keywords: "sensitivity", "sensitive", "responds to", "effective" |
| therapy_targets_query | Keywords: "target", "mechanism", "what does X target" |
| gene_targeting_therapies_query | Keywords: "therapies for", "drugs targeting", "inhibitors of" |
| gene_variants_query | Keywords: "variants", "mutations", "alterations of" |
| variant_response_query | Requires both variant name AND therapy name |
| gene_overview_query | Keywords: "tell me about [gene]", "what is [gene]" |
| therapy_overview_query | Keywords: "tell me about [therapy]", "what is [therapy]" |
| disease_biomarkers_query | Keywords: "biomarkers in [disease]", "markers for [disease]" |
| disease_therapies_query | Keywords: "therapies in [disease]", "treatments for [disease]" |
| conversational | Greetings, thanks, goodbyes, off-topic |
| complex | Multi-comparisons, exclusions, "all", "compare", "except" |
| unclear | Gibberish, too vague, no identifiable intent |

---

## Appendix D: Voice Response Guidelines

- **Length:** 1-3 sentences. Never more than 4.
- **Numbers:** Say "thirteen genes" not "13 genes" (TTS reads better)
- **Evidence:** Mention level A/B evidence when present. Skip C/D/E unless specifically asked.
- **Lists:** For 4+ items, say top 3 then "and N others"
- **Follow-ups:** Offer next action: "Want the full list?" / "Should I run enrichment?"
- **Gene names:** Spell out (KRAS reads as "K-R-A-S", which is fine)
- **Drug names:** Should pronounce correctly (cetuximab = "se-TUX-i-mab")
- **Avoid:** PMIDs, URLs, technical jargon, long pauses