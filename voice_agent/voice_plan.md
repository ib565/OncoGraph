# OncoGraph Voice Router - Implementation Guide

## Note

This is a rough plan. Feel free to deviate from it and suggest improvements and changes.

## Overview

This document covers implementing a fast-path query router for the OncoGraph voice AI agent. The router classifies natural language queries, extracts entities, matches to pre-written Cypher templates, and returns voice-friendly responses.

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

## Stage 1: Router Prototype

**Goal:** Prove intent classification and entity extraction works fast enough.

### 1.1 Pydantic Models

Create models for structured LLM output:

**RouteResult**
- `intent`: Literal enum of all template IDs plus "conversational", "complex", "unclear"
- `entities`: ExtractedEntities object
- `confidence`: float 0.0-1.0

**ExtractedEntities**
- `gene`: str | None
- `therapy`: str | None  
- `disease`: str | None
- `variant`: str | None

### 1.2 Intent Categories

| Intent ID | Description | Required Entities |
|-----------|-------------|-------------------|
| `resistance_biomarkers` | Genes predicting resistance | therapy |
| `sensitivity_biomarkers` | Genes predicting sensitivity | therapy |
| `therapy_targets` | What genes a therapy targets | therapy |
| `gene_targeting_therapies` | What therapies target a gene | gene |
| `gene_variants` | Variants of a gene with evidence | gene |
| `variant_response` | Specific variant + therapy response | variant, therapy |
| `gene_overview` | General info about a gene | gene |
| `therapy_overview` | General info about a therapy | therapy |
| `disease_biomarkers` | Top biomarkers in a disease | disease |
| `disease_therapies` | Therapies with evidence in a disease | disease |
| `conversational` | Greetings, thanks, off-topic chat | none |
| `complex` | Multi-entity comparisons, exclusions, etc. | varies |
| `unclear` | Can't determine intent | none |

### 1.3 Router Prompt Design

The prompt should:
- List all available intents with short descriptions
- Instruct the LLM to extract entities and normalize obvious cases (KRAS not kras, cetuximab not Cetuximab)
- Request JSON output matching your Pydantic model
- Include 2-3 few-shot examples for tricky cases

Key prompt elements:
- System context: "You are a query router for an oncology knowledge graph"
- Available intents list with examples
- Entity extraction rules (gene=uppercase, therapy=lowercase)
- Output format specification
- Confidence guidance: 1.0 for obvious matches, lower for ambiguous

Examples:
- "What causes resistance to cetuximab?" → resistance_biomarkers, {therapy: cetuximab}
- "Tell me about KRAS" → gene_overview, {gene: KRAS}
- "Does BRAF V600E respond to dabrafenib?" → variant_response, {variant: V600E, therapy: dabrafenib, gene: BRAF}
- "Compare all EGFR inhibitors" → complex
- "Thanks!" → conversational

### 1.4 Implementation Notes

- Use Gemini Flash Lite with structured output
- Wrap in async function for later integration
- Add timeout handling (fail if LLM takes >5s)
- Log inputs/outputs for debugging

### 1.5 Test Cases

Test the router against these queries (expected results in parentheses):

```
"Which genes predict resistance to cetuximab?" 
  → resistance_biomarkers, {therapy: cetuximab}

"What does vemurafenib target?"
  → therapy_targets, {therapy: vemurafenib}

"What therapies target BRAF?"
  → gene_targeting_therapies, {gene: BRAF}

"Tell me about EGFR"
  → gene_overview, {gene: EGFR}

"What variants of KRAS have clinical evidence?"
  → gene_variants, {gene: KRAS}

"Does BRAF V600E respond to dabrafenib?"
  → variant_response, {variant: V600E, therapy: dabrafenib}

"What predicts sensitivity to imatinib in leukemia?"
  → sensitivity_biomarkers, {therapy: imatinib, disease: leukemia}

"What biomarkers matter in lung cancer?"
  → disease_biomarkers, {disease: lung cancer}

"What therapies have evidence in colorectal cancer?"
  → disease_therapies, {disease: colorectal cancer}

"Tell me about cetuximab"
  → therapy_overview, {therapy: cetuximab}

"Compare resistance profiles for cetuximab and panitumumab"
  → complex

"Hello"
  → conversational

"asdfghjkl"
  → unclear
```

### Done When
- [ ] Pydantic models defined and importable
- [ ] Router prompt written
- [ ] Router function implemented with LLM call
- [ ] Function returns structured RouteResult
- [ ] Latency measured
- [ ] 10/12 test cases pass correctly
- [ ] Timeout handling works

---

## Stage 2: Entity Index

**Goal:** Fast deterministic normalization of user-spoken entities to canonical database names.

### 2.1 Index Structure

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
- Values: canonical name as stored
- Example: {"colorectal cancer": "Colorectal Carcinoma", "crc": "Colorectal Carcinoma"}

### 2.2 Data Extraction Queries

Run these against Neo4j at startup:

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
MATCH ()-[r:AFFECTS_RESPONSE_TO]->()
RETURN DISTINCT r.disease_name AS name
```

Note: Diseases don't have a dedicated node, so extract unique disease_name values from relationships.

### 2.3 Normalization Function

Create `normalize_entity(entity_type: str, raw: str) -> str | None`

Logic:
1. Lowercase the input
2. Exact lookup in appropriate index
3. If not found, return None (let Cypher CONTAINS handle fuzzy matching)

For diseases specifically: don't require exact match. Return the input as-is and let Cypher CONTAINS do the work. This avoids needing exhaustive disease synonym coverage.

### 2.4 Handling Ambiguity

If a synonym maps to multiple entities (rare but possible):
- For MVP: return the first match
- Log a warning for later review
- Consider: could ask user for clarification in voice ("Did you mean X or Y?")

### 2.5 Variant Handling

Variants are complex. Strategy for MVP:
- If input looks like "GENE VARIANT" (e.g., "BRAF V600E"), split and store both
- If input is just a variant token (e.g., "V600E"), keep as-is, will need gene context
- Don't try to normalize variants against DB — let Cypher CONTAINS handle it

### 2.6 Index Persistence

Options:
1. **Rebuild on startup** — Query Neo4j each time agent starts (~1-2 seconds)
2. **Cache to file** — Save as JSON, reload if exists, rebuild if stale

For MVP: rebuild on startup is fine. It's fast and ensures freshness.

### Done When
- [ ] Neo4j queries written and tested
- [ ] Index building function implemented
- [ ] Indexes populated at startup (or cached)
- [ ] normalize_entity function works for genes
- [ ] normalize_entity function works for therapies
- [ ] Diseases pass through without strict normalization
- [ ] Index build time measured (<3 seconds acceptable)

---

## Stage 3: Template Library

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

#### Template 1: resistance_biomarkers

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

#### Template 2: sensitivity_biomarkers

**Purpose:** Find genes whose variants predict sensitivity to a therapy

**Required entities:** therapy

**Optional entities:** disease

**Cypher pattern:** Same as resistance_biomarkers but effect = 'sensitivity'

**Response format:** Same pattern as resistance

---

#### Template 3: therapy_targets

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

#### Template 4: gene_targeting_therapies

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

#### Template 5: gene_variants

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

#### Template 6: variant_response

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

#### Template 7: gene_overview

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

#### Template 8: therapy_overview

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

#### Template 9: disease_biomarkers

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

#### Template 10: disease_therapies

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
- [ ] QueryTemplate dataclass defined
- [ ] All 10 templates written with Cypher
- [ ] Cypher tested directly against Neo4j (paste in browser/CLI)
- [ ] Response formatters written for all 10 templates
- [ ] fill_template function works correctly
- [ ] Edge cases handled (empty results, single result, many results)

---

## Stage 4: Fast Path Integration

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
- [ ] handle_query function implemented
- [ ] Router → Template flow works
- [ ] Neo4j connection working in agent context
- [ ] All 10 query types tested end-to-end
- [ ] Error handling covers all cases
- [ ] Latency logged and under 2 seconds for happy path
- [ ] Empty results handled gracefully

---

## Stage 5: Complex Query Fallback

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
├── templates/
│   ├── __init__.py
│   ├── models.py          # QueryTemplate dataclass
│   ├── registry.py        # TEMPLATES dict with all 10 templates
│   ├── cypher.py          # Template filling logic
│   └── formatters.py      # Response formatter functions
├── entities/
│   ├── __init__.py
│   ├── index.py           # Entity index building and lookup
│   └── normalize.py       # Normalization function
├── context.py             # ConversationContext class
├── handler.py             # Main handle_query function
├── db.py                  # Neo4j connection (or import from existing)
└── test_router.py         # Test script for non-voice testing
```

---

## Appendix B: Template Quick Reference

| ID | Required | Optional | Returns |
|----|----------|----------|---------|
| resistance_biomarkers | therapy | disease | gene, count, level |
| sensitivity_biomarkers | therapy | disease | gene, count, level |
| therapy_targets | therapy | — | gene, mechanism |
| gene_targeting_therapies | gene | — | therapy, mechanism, modality |
| gene_variants | gene | — | variant, count, level |
| variant_response | variant, therapy | — | effect, disease, level |
| gene_overview | gene | — | variant_count, therapy_count |
| therapy_overview | therapy | — | modality, target_count, biomarker_count |
| disease_biomarkers | disease | — | gene, count, level |
| disease_therapies | disease | — | therapy, count |

---

## Appendix C: Router Intent Reference

| Intent | Confidence Notes |
|--------|------------------|
| resistance_biomarkers | Keywords: "resistance", "resistant", "doesn't respond" |
| sensitivity_biomarkers | Keywords: "sensitivity", "sensitive", "responds to", "effective" |
| therapy_targets | Keywords: "target", "mechanism", "what does X target" |
| gene_targeting_therapies | Keywords: "therapies for", "drugs targeting", "inhibitors of" |
| gene_variants | Keywords: "variants", "mutations", "alterations of" |
| variant_response | Requires both variant name AND therapy name |
| gene_overview | Keywords: "tell me about [gene]", "what is [gene]" |
| therapy_overview | Keywords: "tell me about [therapy]", "what is [therapy]" |
| disease_biomarkers | Keywords: "biomarkers in [disease]", "markers for [disease]" |
| disease_therapies | Keywords: "therapies in [disease]", "treatments for [disease]" |
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