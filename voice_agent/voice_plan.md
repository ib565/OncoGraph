# OncoGraph Voice Router - Implementation Guide

## Note

This is a rough plan. Feel free to deviate from it and suggest improvements and changes.

## Overview

This document covers implementing a fast-path query router for the OncoGraph voice AI agent. The router classifies natural language queries, extracts entities, matches to pre-written Cypher templates, and returns voice-friendly responses.

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

**⏳ Stage 5: Complex Query Fallback** - Not Started (depends on Stage 4)
- Handle conversational, complex, and unclear intents

**⏳ Stage 6: Conversation Context** - Not Started (depends on Stage 4)
- Handle follow-up queries with context

### Target Latency
- Template-matched queries: <2 seconds end-to-end
- Complex queries (fallback): acknowledge immediately, process in background

### Pipeline
```
User text
    ↓
Intent + Entity Extraction (LLM, structured output)
    ↓
Entity Normalization (deterministic + fuzzy fallback)
    ↓
Template Selection + Fill
    ↓
Cypher Execution
    ↓
Response Formatting
    ↓
Return to conversation agent
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
- Return therapy name, mechanism, modality
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
- OPTIONAL MATCH target genes
- OPTIONAL MATCH biomarker evidence pointing to therapy
- Return therapy name, modality, target count, biomarker count

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

Target breakdown:
- Router: <500ms
- Normalization: <10ms
- Cypher: <500ms
- Formatting: <10ms
- **Total: <1.5s**

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

## Stage 5: Complex Query Fallback

**Status:** ⏳ Not Started - Depends on Stage 4

**Goal:** Gracefully handle queries that don't match templates.

### 5.1 Fallback Triggers

Route to fallback when:
- `intent == "complex"`
- `intent == "unclear"`
- `confidence < 0.6`
- Required entities missing and can't prompt for them

### 5.2 Conversational Intent

For `intent == "conversational"`:
- "Hello" / "Hi" → "Hi! I'm OncoGraph. Ask me about cancer biomarkers, therapies, or resistance mechanisms."
- "Thanks" / "Thank you" → "You're welcome! Anything else?"
- "Goodbye" / "Bye" → "Goodbye! Feel free to come back anytime."
- Off-topic → "I'm specialized in oncology research. I can help with biomarkers, therapies, and drug resistance."

Use a simple keyword/pattern match or let the router LLM handle sub-classification.

### 5.3 Complex Query Handling

For genuinely complex queries that need full pipeline:

Response pattern:
"That's a complex question that needs more analysis. I'll have results ready in the web dashboard in about a minute. Is there something simpler I can help with now?"

Implementation:
- Return acknowledgment immediately
- (Optional) Trigger background job to your existing FastAPI pipeline
- (Optional) Store result somewhere user can access

For MVP: just return the acknowledgment. Don't implement background processing yet.

### 5.4 Unclear Intent

When router can't classify:
"I'm not sure I understood that. You can ask me things like 'What causes resistance to cetuximab?' or 'What therapies target BRAF?'"

### Done When
- [ ] Conversational responses implemented
- [ ] Complex query acknowledgment implemented
- [ ] Unclear intent handled with helpful suggestions
- [ ] All fallback paths tested

---

## Stage 6: Conversation Context

**Status:** ⏳ Not Started - Depends on Stage 4

**Goal:** Handle follow-up queries that reference previous results.

### 6.1 Context Data Structure

Create `ConversationContext` class:
- `last_genes`: list[str] | None — genes from last query result
- `last_therapies`: list[str] | None — therapies from last query result
- `last_disease`: str | None — disease context if mentioned
- `last_query_type`: str | None — template ID of last query
- `turn_count`: int — for tracking conversation length

### 6.2 Context Updates

After each successful query:
- Extract genes/therapies/disease from results
- Store in context
- Increment turn count

### 6.3 Reference Resolution

Before routing, check for references in transcript:
- "those genes" / "these genes" / "them" → substitute `context.last_genes`
- "that therapy" / "this drug" → substitute `context.last_therapies[0]`
- "run enrichment" / "pathway analysis" → trigger enrichment with `context.last_genes`

Implementation options:
1. **Pre-process transcript** — regex/keyword replacement before routing
2. **Include context in router prompt** — let LLM resolve references
3. **Post-process entities** — if entity is None but reference detected, fill from context

For MVP: Option 1 or 3 is simpler. Avoid making router prompt too complex.

### 6.4 Enrichment Flow

When user says "run enrichment" / "pathway analysis" / "what pathways":
- Check `context.last_genes` exists and has 3+ genes
- If yes: could call your existing enrichment endpoint
- Return: "Running pathway enrichment on {N} genes... The top pathway is {X} with p-value {Y}."

For MVP: acknowledge the intent, suggest using web app
"I found these genes: X, Y, Z. For pathway enrichment, check the web dashboard — the results are ready to analyze there."

### 6.5 Context Reset

Reset context when:
- User starts completely new topic (different entity types)
- User explicitly asks to start over
- Conversation idle for extended period (if tracking)

### Done When
- [ ] ConversationContext class implemented
- [ ] Context updated after each query
- [ ] "those genes" / "that therapy" references resolved
- [ ] Enrichment intent recognized
- [ ] Context passed through handle_query correctly

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
├── templates/              # (Stage 3 - not yet implemented)
│   ├── __init__.py
│   ├── models.py          # QueryTemplate dataclass
│   ├── registry.py        # TEMPLATES dict with all 10 templates
│   ├── cypher.py          # Template filling logic
│   └── formatters.py      # Response formatter functions
├── context.py             # ConversationContext class (Stage 6)
├── handler.py             # Main handle_query function (Stage 4)
└── test_router.py         # Test script for non-voice testing
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