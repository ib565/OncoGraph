from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel


class QueryTemplate(BaseModel):
    """Pre-written Cypher template for a specific query intent."""

    id: str  # matches intent ID from router
    description: str  # human-readable description
    example: str | None = None  # example query for prompt building
    required_entities: list[str]  # must be present to execute
    optional_entities: list[str]  # enhance query if present
    cypher: str  # Cypher query with {entity} placeholders
    # Payload builder: returns a Pydantic model instance or None when there are no results.
    format_response: Callable[
        [list[dict[str, object]], dict[str, str | None], int],
        BaseModel | None,
    ]
