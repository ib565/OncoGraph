from __future__ import annotations

from voice_agent.templates.cypher import fill_template
from voice_agent.templates.formatters import (
    disease_biomarkers_formatter,
    disease_therapies_formatter,
    gene_overview_formatter,
    gene_targeting_therapies_formatter,
    gene_variants_formatter,
    resistance_biomarkers_formatter,
    sensitivity_biomarkers_formatter,
    therapy_overview_formatter,
    therapy_targets_formatter,
    variant_response_formatter,
)
from voice_agent.templates.models import QueryTemplate
from voice_agent.templates.registry import TEMPLATES


def get_template(intent_id: str) -> QueryTemplate | None:
    """Get a template by intent ID.

    Args:
        intent_id: Intent ID from router (e.g., "resistance_biomarkers_query")

    Returns:
        QueryTemplate if found, None otherwise
    """
    return TEMPLATES.get(intent_id)


__all__ = [
    "QueryTemplate",
    "get_template",
    "fill_template",
    "TEMPLATES",
    "resistance_biomarkers_formatter",
    "sensitivity_biomarkers_formatter",
    "therapy_targets_formatter",
    "gene_targeting_therapies_formatter",
    "gene_variants_formatter",
    "variant_response_formatter",
    "gene_overview_formatter",
    "therapy_overview_formatter",
    "disease_biomarkers_formatter",
    "disease_therapies_formatter",
]

