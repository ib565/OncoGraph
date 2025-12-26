from __future__ import annotations

from typing import TYPE_CHECKING

from voice_agent.router.models import ExtractedEntities

if TYPE_CHECKING:
    from voice_agent.templates.models import QueryTemplate

# Generic disease type terms to exclude when specific tokens exist
GENERIC_DISEASE_TERMS = {"cancer", "carcinoma", "tumor", "neoplasm"}


def _escape_cypher_literal(value: str) -> str:
    """Escape a Python string for safe inclusion in single-quoted Cypher string literals.

    Rules:
    - Backslashes first (\\ -> \\\\)
    - Single quotes (') as \\'
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def tokenize_disease(name: str) -> list[str]:
    """Tokenize disease name, preserving hyphens.

    Filters out generic disease type terms ("cancer", "carcinoma", "tumor", "neoplasm")
    when more specific anatomical/organ tokens or disease-specific modifiers are available.

    Args:
        name: Disease name (e.g., "Non-small Cell Lung Carcinoma")

    Returns:
        List of lowercase tokens (e.g., ['lung', 'non-small', 'cell'])
    """
    if not name:
        return []

    lower = name.lower()
    tokens = [t.strip() for t in lower.split() if t.strip()]

    if not tokens:
        return []

    # Check if we have specific tokens beyond generic terms
    specific_tokens = [t for t in tokens if t not in GENERIC_DISEASE_TERMS]

    # If we have specific tokens, exclude generic terms
    if specific_tokens:
        return specific_tokens

    # For umbrella terms (only generic terms), return minimal anchor token
    # For "lung cancer", return ['lung']
    filtered = [t for t in tokens if t != "cancer"]
    return filtered if filtered else tokens


def build_disease_filter(tokens: list[str], use_where: bool = True) -> str:
    """Build Cypher WHERE clause with AND-separated CONTAINS clauses.

    Args:
        tokens: List of lowercase tokens to match (e.g., ['lung', 'non-small', 'cell'])
        use_where: If True, prefix with WHERE. If False, prefix with AND.

    Returns:
        Cypher fragment: "WHERE ( ... )" or "AND ( ... )" or empty string if no tokens
    """
    if not tokens:
        return ""

    # Build AND clause for each token
    token_clauses = [f"toLower(rel.disease_name) CONTAINS '{_escape_cypher_literal(t)}'" for t in tokens]
    and_clause = " AND\n    ".join(token_clauses)

    prefix = "WHERE" if use_where else "AND"
    return f"{prefix} (\n    {and_clause}\n  )"


def fill_template(template: QueryTemplate, entities: ExtractedEntities) -> str:
    """Fill a Cypher template with normalized entity values.

    Args:
        template: QueryTemplate with Cypher containing {entity} placeholders
        entities: ExtractedEntities with normalized values

    Returns:
        Final Cypher string ready for execution
    """
    cypher = template.cypher

    # Replace entity placeholders with escaped normalized values
    if entities.therapy:
        escaped_therapy = _escape_cypher_literal(entities.therapy)
        cypher = cypher.replace("{therapy}", escaped_therapy)

    if entities.gene:
        escaped_gene = _escape_cypher_literal(entities.gene)
        cypher = cypher.replace("{gene}", escaped_gene)

    if entities.variant:
        escaped_variant = _escape_cypher_literal(entities.variant)
        cypher = cypher.replace("{variant}", escaped_variant)

    # Handle disease filter (tokenized WHERE clause)
    disease_filter = ""
    if entities.disease:
        tokens = tokenize_disease(entities.disease)
        if tokens:
            # Check if we need WHERE or AND based on existing WHERE in template
            # Simple heuristic: if {disease_filter} appears after a WHERE, use AND
            # Otherwise, use WHERE
            use_where = "WHERE" not in cypher[: cypher.find("{disease_filter}")]
            disease_filter = build_disease_filter(tokens, use_where=use_where)

    cypher = cypher.replace("{disease_filter}", disease_filter)

    return cypher
