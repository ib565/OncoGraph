from __future__ import annotations

from voice_agent.templates.formatters import (
    build_disease_biomarkers_payload,
    build_disease_therapies_payload,
    build_gene_overview_payload,
    build_gene_targeting_therapies_payload,
    build_gene_variants_payload,
    build_resistance_biomarkers_payload,
    build_sensitivity_biomarkers_payload,
    build_therapy_overview_payload,
    build_therapy_targets_payload,
    build_variant_response_payload,
)
from voice_agent.templates.models import QueryTemplate

# Template 1: resistance_biomarkers_query
RESISTANCE_BIOMARKERS_CYPHER = """
MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
WHERE (
  toLower(t.name) = toLower('{therapy}')
  OR any(s IN coalesce(t.synonyms, []) WHERE toLower(s) = toLower('{therapy}'))
)
AND toLower(rel.effect) = 'resistance'
{disease_filter}
OPTIONAL MATCH (b)-[:VARIANT_OF]->(g:Gene)
WITH CASE WHEN b:Gene THEN b.symbol ELSE g.symbol END AS gene_symbol,
     t.name AS therapy_name,
     rel.disease_name AS disease_name,
     rel
WHERE gene_symbol IS NOT NULL
RETURN
  NULL AS variant_name,
  gene_symbol,
  therapy_name,
  'resistance' AS effect,
  disease_name,
  reduce(s = [], p IN collect(coalesce(rel.pmids, [])) | s + p) AS pmids,
  min(rel.best_evidence_level) AS best_evidence_level,
  collect(DISTINCT rel.best_evidence_level) AS evidence_levels,
  sum(rel.evidence_count) AS evidence_count,
  avg(rel.avg_rating) AS avg_rating,
  max(rel.max_rating) AS max_rating
ORDER BY best_evidence_level ASC, evidence_count DESC
LIMIT 10
"""

# Template 2: sensitivity_biomarkers_query
SENSITIVITY_BIOMARKERS_CYPHER = """
MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
WHERE (
  toLower(t.name) = toLower('{therapy}')
  OR any(s IN coalesce(t.synonyms, []) WHERE toLower(s) = toLower('{therapy}'))
)
AND toLower(rel.effect) = 'sensitivity'
{disease_filter}
OPTIONAL MATCH (b)-[:VARIANT_OF]->(g:Gene)
WITH CASE WHEN b:Gene THEN b.symbol ELSE g.symbol END AS gene_symbol,
     t.name AS therapy_name,
     rel.disease_name AS disease_name,
     rel
WHERE gene_symbol IS NOT NULL
RETURN
  NULL AS variant_name,
  gene_symbol,
  therapy_name,
  'sensitivity' AS effect,
  disease_name,
  reduce(s = [], p IN collect(coalesce(rel.pmids, [])) | s + p) AS pmids,
  min(rel.best_evidence_level) AS best_evidence_level,
  collect(DISTINCT rel.best_evidence_level) AS evidence_levels,
  sum(rel.evidence_count) AS evidence_count,
  avg(rel.avg_rating) AS avg_rating,
  max(rel.max_rating) AS max_rating
ORDER BY best_evidence_level ASC, evidence_count DESC
LIMIT 10
"""

# Template 3: therapy_targets_query
THERAPY_TARGETS_CYPHER = """
MATCH (t:Therapy)-[r:TARGETS]->(g:Gene)
WHERE (
  toLower(t.name) = toLower('{therapy}')
  OR any(s IN coalesce(t.synonyms, []) WHERE toLower(s) = toLower('{therapy}'))
)
RETURN
  NULL AS variant_name,
  g.symbol AS gene_symbol,
  t.name AS therapy_name,
  NULL AS effect,
  NULL AS disease_name,
  r.moa AS targets_moa,
  coalesce(r.ref_sources, []) AS ref_sources,
  coalesce(r.ref_ids, []) AS ref_ids,
  coalesce(r.ref_urls, []) AS ref_urls
LIMIT 10
"""

# Template 4: gene_targeting_therapies_query
GENE_TARGETING_THERAPIES_CYPHER = """
MATCH (t:Therapy)-[r:TARGETS]->(g:Gene)
WHERE (
  toLower(g.symbol) = toLower('{gene}')
  OR any(s IN coalesce(g.synonyms, []) WHERE toLower(s) = toLower('{gene}'))
)
RETURN
  NULL AS variant_name,
  g.symbol AS gene_symbol,
  t.name AS therapy_name,
  NULL AS effect,
  NULL AS disease_name,
  r.moa AS targets_moa,
  coalesce(r.ref_sources, []) AS ref_sources,
  coalesce(r.ref_ids, []) AS ref_ids,
  coalesce(r.ref_urls, []) AS ref_urls
LIMIT 10
"""

# Template 5: gene_variants_query
GENE_VARIANTS_CYPHER = """
MATCH (v:Variant)-[:VARIANT_OF]->(g:Gene)
WHERE (
  toLower(g.symbol) = toLower('{gene}')
  OR any(s IN coalesce(g.synonyms, []) WHERE toLower(s) = toLower('{gene}'))
)
MATCH (v)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
WITH v, g, rel
RETURN
  v.name AS variant_name,
  g.symbol AS gene_symbol,
  NULL AS therapy_name,
  NULL AS effect,
  NULL AS disease_name,
  min(rel.best_evidence_level) AS best_evidence_level,
  collect(DISTINCT rel.best_evidence_level) AS evidence_levels,
  sum(rel.evidence_count) AS evidence_count,
  avg(rel.avg_rating) AS avg_rating,
  max(rel.max_rating) AS max_rating
ORDER BY best_evidence_level ASC, evidence_count DESC
LIMIT 10
"""

# Template 6: variant_response_query
VARIANT_RESPONSE_CYPHER = """
MATCH (v:Variant)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
WHERE (
  toLower(v.name) CONTAINS toLower('{variant}')
  OR any(s IN coalesce(v.synonyms, []) WHERE toLower(s) = toLower('{variant}'))
)
AND (
  toLower(t.name) = toLower('{therapy}')
  OR any(s IN coalesce(t.synonyms, []) WHERE toLower(s) = toLower('{therapy}'))
)
OPTIONAL MATCH (v)-[:VARIANT_OF]->(g:Gene)
RETURN
  v.name AS variant_name,
  CASE WHEN g IS NOT NULL THEN g.symbol ELSE NULL END AS gene_symbol,
  t.name AS therapy_name,
  rel.effect AS effect,
  rel.disease_name AS disease_name,
  coalesce(rel.pmids, []) AS pmids,
  coalesce(rel.best_evidence_level, '') AS best_evidence_level,
  coalesce(rel.evidence_levels, []) AS evidence_levels,
  coalesce(rel.evidence_count, 0) AS evidence_count,
  rel.avg_rating AS avg_rating,
  rel.max_rating AS max_rating
LIMIT 5
"""

# Template 7: gene_overview_query
GENE_OVERVIEW_CYPHER = """
MATCH (g:Gene)
WHERE (
  toLower(g.symbol) = toLower('{gene}')
  OR any(s IN coalesce(g.synonyms, []) WHERE toLower(s) = toLower('{gene}'))
)
OPTIONAL MATCH (v:Variant)-[:VARIANT_OF]->(g)
OPTIONAL MATCH (t:Therapy)-[:TARGETS]->(g)
RETURN
  g.symbol AS gene_symbol,
  count(DISTINCT v) AS variant_count,
  count(DISTINCT t) AS therapy_count
LIMIT 1
"""

# Template 8: therapy_overview_query
THERAPY_OVERVIEW_CYPHER = """
MATCH (t:Therapy)
WHERE (
  toLower(t.name) = toLower('{therapy}')
  OR any(s IN coalesce(t.synonyms, []) WHERE toLower(s) = toLower('{therapy}'))
)
OPTIONAL MATCH (t)-[:TARGETS]->(g_all:Gene)
OPTIONAL MATCH (b:Biomarker)-[:AFFECTS_RESPONSE_TO]->(t)
WITH t, count(DISTINCT g_all) AS target_count, count(DISTINCT b) AS biomarker_count
OPTIONAL MATCH (t)-[r:TARGETS]->(g:Gene)
RETURN
  t.name AS therapy_name,
  target_count,
  biomarker_count,
  g.symbol AS gene_symbol,
  r.moa AS targets_moa
LIMIT 10
"""

# Template 9: disease_biomarkers_query
DISEASE_BIOMARKERS_CYPHER = """
MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
{disease_filter}
OPTIONAL MATCH (b)-[:VARIANT_OF]->(g:Gene)
WITH CASE WHEN b:Gene THEN b.symbol ELSE g.symbol END AS gene_symbol,
     t.name AS therapy_name,
     rel.disease_name AS disease_name,
     rel
WHERE gene_symbol IS NOT NULL
RETURN
  NULL AS variant_name,
  gene_symbol,
  therapy_name,
  rel.effect AS effect,
  disease_name,
  reduce(s = [], p IN collect(coalesce(rel.pmids, [])) | s + p) AS pmids,
  min(rel.best_evidence_level) AS best_evidence_level,
  collect(DISTINCT rel.best_evidence_level) AS evidence_levels,
  sum(rel.evidence_count) AS evidence_count,
  avg(rel.avg_rating) AS avg_rating,
  max(rel.max_rating) AS max_rating
ORDER BY best_evidence_level ASC, evidence_count DESC
LIMIT 10
"""

# Template 10: disease_therapies_query
DISEASE_THERAPIES_CYPHER = """
MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy)
{disease_filter}
RETURN
  NULL AS variant_name,
  NULL AS gene_symbol,
  t.name AS therapy_name,
  NULL AS effect,
  rel.disease_name AS disease_name,
  count(rel) AS evidence_count
ORDER BY evidence_count DESC
LIMIT 10
"""

TEMPLATES: dict[str, QueryTemplate] = {
    "resistance_biomarkers_query": QueryTemplate(
        id="resistance_biomarkers_query",
        description="Find genes whose variants predict resistance to a specific therapy",
        example="Which genes cause resistance to cetuximab?",
        required_entities=["therapy"],
        optional_entities=["disease"],
        cypher=RESISTANCE_BIOMARKERS_CYPHER.strip(),
        format_response=build_resistance_biomarkers_payload,
    ),
    "sensitivity_biomarkers_query": QueryTemplate(
        id="sensitivity_biomarkers_query",
        description="Find genes whose variants predict sensitivity to a specific therapy",
        example="What predicts sensitivity to imatinib?",
        required_entities=["therapy"],
        optional_entities=["disease"],
        cypher=SENSITIVITY_BIOMARKERS_CYPHER.strip(),
        format_response=build_sensitivity_biomarkers_payload,
    ),
    "therapy_targets_query": QueryTemplate(
        id="therapy_targets_query",
        description="What genes does a therapy target via TARGETS relationship",
        example="What does vemurafenib target?",
        required_entities=["therapy"],
        optional_entities=[],
        cypher=THERAPY_TARGETS_CYPHER.strip(),
        format_response=build_therapy_targets_payload,
    ),
    "gene_targeting_therapies_query": QueryTemplate(
        id="gene_targeting_therapies_query",
        description="What therapies target a specific gene",
        example="What therapies target BRAF?",
        required_entities=["gene"],
        optional_entities=[],
        cypher=GENE_TARGETING_THERAPIES_CYPHER.strip(),
        format_response=build_gene_targeting_therapies_payload,
    ),
    "gene_variants_query": QueryTemplate(
        id="gene_variants_query",
        description="List variants of a gene that have clinical evidence in the database",
        example="What variants of KRAS have evidence?",
        required_entities=["gene"],
        optional_entities=[],
        cypher=GENE_VARIANTS_CYPHER.strip(),
        format_response=build_gene_variants_payload,
    ),
    "variant_response_query": QueryTemplate(
        id="variant_response_query",
        description="How does a specific variant affect response to a specific therapy",
        example="Does BRAF V600E respond to dabrafenib?",
        required_entities=["variant", "therapy"],
        optional_entities=[],
        cypher=VARIANT_RESPONSE_CYPHER.strip(),
        format_response=build_variant_response_payload,
    ),
    "gene_overview_query": QueryTemplate(
        id="gene_overview_query",
        description="General summary statistics about a gene (variant count, therapies targeting it)",
        example="Tell me about EGFR",
        required_entities=["gene"],
        optional_entities=[],
        cypher=GENE_OVERVIEW_CYPHER.strip(),
        format_response=build_gene_overview_payload,
    ),
    "therapy_overview_query": QueryTemplate(
        id="therapy_overview_query",
        description="General summary statistics about a therapy (target genes, biomarker associations)",
        example="Tell me about cetuximab",
        required_entities=["therapy"],
        optional_entities=[],
        cypher=THERAPY_OVERVIEW_CYPHER.strip(),
        format_response=build_therapy_overview_payload,
    ),
    "disease_biomarkers_query": QueryTemplate(
        id="disease_biomarkers_query",
        description="Top biomarker genes for a specific disease",
        example="What biomarkers matter in lung cancer?",
        required_entities=["disease"],
        optional_entities=[],
        cypher=DISEASE_BIOMARKERS_CYPHER.strip(),
        format_response=build_disease_biomarkers_payload,
    ),
    "disease_therapies_query": QueryTemplate(
        id="disease_therapies_query",
        description="Therapies with biomarker evidence in a specific disease",
        example="What therapies have evidence in colorectal cancer?",
        required_entities=["disease"],
        optional_entities=[],
        cypher=DISEASE_THERAPIES_CYPHER.strip(),
        format_response=build_disease_therapies_payload,
    ),
}

# Ordered list of intent IDs derived from templates plus non-query intents.
INTENT_IDS: list[str] = list(TEMPLATES.keys()) + ["conversational", "complex", "unclear"]


def get_required_entities(intent: str) -> list[str]:
    """Return required entities for an intent, or an empty list if missing."""
    template = TEMPLATES.get(intent)
    return template.required_entities if template else []


def get_optional_entities(intent: str) -> list[str]:
    """Return optional entities for an intent, or an empty list if missing."""
    template = TEMPLATES.get(intent)
    return template.optional_entities if template else []
