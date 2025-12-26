from __future__ import annotations

from collections.abc import Callable

from voice_agent.router.models import ExtractedEntities

from .index import EntityIndex, get_index


def create_normalizer(index: EntityIndex | None = None) -> Callable[[ExtractedEntities], ExtractedEntities]:
    """Create a normalizer function matching the router's expected signature.

    The returned callable takes an :class:`ExtractedEntities` instance and
    returns a new instance with genes, therapies, and diseases normalized to
    their canonical forms using the global :class:`EntityIndex` singleton by
    default.
    """
    idx = index or get_index()

    def normalize(entities: ExtractedEntities) -> ExtractedEntities:
        return idx.normalize_entities(entities)

    return normalize
