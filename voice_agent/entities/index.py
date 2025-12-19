from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from pipeline.executor import Neo4jExecutor
from pipeline.types import PipelineConfig, PipelineError
from voice_agent.router.models import ExtractedEntities

logger = logging.getLogger(__name__)


@dataclass
class EntityIndex:
    """In-memory index for fast entity normalization.

    Genes and therapies are stored with lowercase keys mapping to canonical
    values. Diseases map lowercase keys to their canonical name as stored
    in the database.
    """

    genes_index: dict[str, str]
    therapies_index: dict[str, str]
    diseases_index: dict[str, str]

    def __init__(self, executor: Neo4jExecutor) -> None:
        self.genes_index = {}
        self.therapies_index = {}
        self.diseases_index = {}
        self._build_indexes(executor)

    def _build_indexes(self, executor: Neo4jExecutor) -> None:
        """Query Neo4j and build all three indexes."""
        start = time.perf_counter()
        genes_start = time.perf_counter()
        self._build_genes_index(executor)
        genes_duration_ms = int((time.perf_counter() - genes_start) * 1000)

        therapies_start = time.perf_counter()
        self._build_therapies_index(executor)
        therapies_duration_ms = int((time.perf_counter() - therapies_start) * 1000)

        diseases_start = time.perf_counter()
        self._build_diseases_index(executor)
        diseases_duration_ms = int((time.perf_counter() - diseases_start) * 1000)

        total_duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "Built entity indexes",
            extra={
                "genes_count": len(self.genes_index),
                "therapies_count": len(self.therapies_index),
                "diseases_count": len(self.diseases_index),
                "genes_build_ms": genes_duration_ms,
                "therapies_build_ms": therapies_duration_ms,
                "diseases_build_ms": diseases_duration_ms,
                "total_build_ms": total_duration_ms,
            },
        )

    def _build_genes_index(self, executor: Neo4jExecutor) -> None:
        cypher = "MATCH (g:Gene) RETURN g.symbol AS symbol, g.synonyms AS synonyms"
        try:
            rows = executor.execute_read(cypher)
        except PipelineError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise PipelineError(f"Failed to build genes index: {exc}", step="entity_index_genes") from exc

        if not rows:
            logger.warning("Genes index query returned no rows")

        for row in rows:
            symbol_obj = row.get("symbol")
            if not isinstance(symbol_obj, str) or not symbol_obj.strip():
                continue
            canonical_symbol = symbol_obj.strip().upper()
            self._add_mapping("gene", canonical_symbol, canonical_symbol)

            synonyms = row.get("synonyms")
            if isinstance(synonyms, (list, tuple)):
                for syn in synonyms:
                    if isinstance(syn, str) and syn.strip():
                        self._add_mapping("gene", syn.strip(), canonical_symbol)

    def _build_therapies_index(self, executor: Neo4jExecutor) -> None:
        cypher = "MATCH (t:Therapy) RETURN t.name AS name, t.synonyms AS synonyms"
        try:
            rows = executor.execute_read(cypher)
        except PipelineError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise PipelineError(f"Failed to build therapies index: {exc}", step="entity_index_therapies") from exc

        if not rows:
            logger.warning("Therapies index query returned no rows")

        for row in rows:
            name_obj = row.get("name")
            if not isinstance(name_obj, str) or not name_obj.strip():
                continue
            canonical_name = name_obj.strip().lower()
            self._add_mapping("therapy", canonical_name, canonical_name)

            synonyms = row.get("synonyms")
            if isinstance(synonyms, (list, tuple)):
                for syn in synonyms:
                    if isinstance(syn, str) and syn.strip():
                        self._add_mapping("therapy", syn.strip(), canonical_name)

    def _build_diseases_index(self, executor: Neo4jExecutor) -> None:
        cypher = "MATCH (d:Disease) RETURN d.name AS name, d.synonyms AS synonyms"
        try:
            rows = executor.execute_read(cypher)
        except PipelineError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise PipelineError(f"Failed to build diseases index: {exc}", step="entity_index_diseases") from exc

        if not rows:
            logger.warning("Diseases index query returned no rows")

        for row in rows:
            name_obj = row.get("name")
            if not isinstance(name_obj, str) or not name_obj.strip():
                continue
            canonical_name = name_obj.strip()
            self._add_mapping("disease", canonical_name, canonical_name)

            synonyms = row.get("synonyms")
            if isinstance(synonyms, (list, tuple)):
                for syn in synonyms:
                    if isinstance(syn, str) and syn.strip():
                        self._add_mapping("disease", syn.strip(), canonical_name)

    def _add_mapping(self, entity_type: str, raw_key: str, canonical: str) -> None:
        key = raw_key.strip().lower()
        if not key:
            return

        index = self._get_index_for_type(entity_type)
        existing = index.get(key)
        if existing is not None and existing != canonical:
            logger.warning(
                "Ambiguous %s synonym",
                entity_type,
                extra={"synonym": key, "canonical_existing": existing, "canonical_new": canonical},
            )
            return

        index[key] = canonical

    def _get_index_for_type(self, entity_type: str) -> dict[str, str]:
        if entity_type == "gene":
            return self.genes_index
        if entity_type == "therapy":
            return self.therapies_index
        if entity_type == "disease":
            return self.diseases_index
        raise ValueError(f"Unsupported entity type for index: {entity_type}")

    def normalize_entity(self, entity_type: str, raw: str | None) -> str | None:
        """Normalize an entity to its canonical form.

        Args:
            entity_type: "gene", "therapy", "disease", or "variant".
            raw: Raw entity string from user input.

        Returns:
            Canonical entity name, or None if not found. Diseases return the
            cleaned input as-is if not found. Variants are passed through
            unchanged.
        """
        if raw is None:
            return None

        text = raw.strip()
        if not text:
            return None

        lowered = text.lower()

        if entity_type == "variant":
            return text

        if entity_type == "gene":
            canonical = self.genes_index.get(lowered)
            return canonical

        if entity_type == "therapy":
            canonical = self.therapies_index.get(lowered)
            return canonical

        if entity_type == "disease":
            canonical = self.diseases_index.get(lowered)
            return canonical or text

        logger.warning("Unknown entity type in normalize_entity", extra={"entity_type": entity_type})
        return None

    def normalize_entities(self, entities: ExtractedEntities) -> ExtractedEntities:
        """Normalize all entities in an ExtractedEntities object."""
        normalized_gene = self.normalize_entity("gene", entities.gene) if entities.gene else None
        normalized_therapy = self.normalize_entity("therapy", entities.therapy) if entities.therapy else None
        normalized_disease = self.normalize_entity("disease", entities.disease) if entities.disease else None
        normalized_variant = self.normalize_entity("variant", entities.variant) if entities.variant else None

        return ExtractedEntities(
            gene=normalized_gene,
            therapy=normalized_therapy,
            disease=normalized_disease,
            variant=normalized_variant,
        )


_index: EntityIndex | None = None


def _build_executor() -> Neo4jExecutor:
    """Build a Neo4jExecutor using the same environment variables as the backend."""
    import os

    config = PipelineConfig()

    neo4j_uri = os.getenv("NEO4J_URI", "").strip()
    neo4j_user = os.getenv("NEO4J_USER", "").strip()
    neo4j_password = os.getenv("NEO4J_PASSWORD", "").strip()

    if not neo4j_uri:
        raise RuntimeError("NEO4J_URI is not set; please configure it before starting the voice agent")
    if not neo4j_user:
        raise RuntimeError("NEO4J_USER is not set; please configure it before starting the voice agent")
    if not neo4j_password:
        raise RuntimeError("NEO4J_PASSWORD is not set; please configure it before starting the voice agent")

    return Neo4jExecutor(uri=neo4j_uri, user=neo4j_user, password=neo4j_password, config=config)


def get_index() -> EntityIndex:
    """Get or create the global EntityIndex instance (lazy initialization)."""
    global _index
    if _index is None:
        start = time.perf_counter()
        executor = _build_executor()
        _index = EntityIndex(executor)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("Initialized global EntityIndex", extra={"build_ms": duration_ms})
    return _index
