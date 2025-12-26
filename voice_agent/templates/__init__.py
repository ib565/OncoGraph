from __future__ import annotations

from voice_agent.templates.cypher import fill_template
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
]
