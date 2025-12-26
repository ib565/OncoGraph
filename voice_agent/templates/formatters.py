from __future__ import annotations

from voice_agent.contracts import (
    DiseaseBiomarkersPayload,
    DiseaseTherapiesPayload,
    GeneOverviewPayload,
    GeneTargetingTherapiesPayload,
    GeneVariantsPayload,
    ResistanceBiomarkersPayload,
    SensitivityBiomarkersPayload,
    TherapyOverviewPayload,
    TherapyTargetsPayload,
    VariantResponsePayload,
)


def _clean_value(value: object) -> str:
    """Clean and stringify a value from Neo4j results."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v)
    return str(value)


def _cap_items(items: list[dict[str, object]], speak_top_n: int) -> list[dict[str, object]]:
    """Return at most min(speak_top_n, 5) items from a list."""
    limit = min(max(speak_top_n, 1), 5)
    return items[:limit]


def build_resistance_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> ResistanceBiomarkersPayload | None:
    """Build payload for resistance biomarkers query. Returns None if no results."""
    if not results:
        return None

    therapy = entities.get("therapy") or "this therapy"
    disease = entities.get("disease")

    top_genes: list[dict[str, str | int | None]] = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if not gene:
            continue
        best_level = _clean_value(row.get("best_evidence_level")) or None
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        top_genes.append(
            {
                "gene": gene,
                "best_level": best_level,
                "evidence_count": count,
            }
        )

    if not top_genes:
        return None

    total_genes = len(top_genes)
    capped = _cap_items(top_genes, speak_top_n)

    return ResistanceBiomarkersPayload(
        intent="resistance_biomarkers_query",
        therapy=therapy,
        disease=disease,
        total_genes=total_genes,
        top_genes=capped,
    )


def build_sensitivity_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> SensitivityBiomarkersPayload | None:
    """Build payload for sensitivity biomarkers query. Returns None if no results."""
    if not results:
        return None

    therapy = entities.get("therapy") or "this therapy"
    disease = entities.get("disease")

    top_genes: list[dict[str, str | int | None]] = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if not gene:
            continue
        best_level = _clean_value(row.get("best_evidence_level")) or None
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        top_genes.append(
            {
                "gene": gene,
                "best_level": best_level,
                "evidence_count": count,
            }
        )

    if not top_genes:
        return None

    total_genes = len(top_genes)
    capped = _cap_items(top_genes, speak_top_n)

    return SensitivityBiomarkersPayload(
        intent="sensitivity_biomarkers_query",
        therapy=therapy,
        disease=disease,
        total_genes=total_genes,
        top_genes=capped,
    )


def build_therapy_targets_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> TherapyTargetsPayload | None:
    """Build payload for therapy targets query. Returns None if no results."""
    if not results:
        return None

    therapy = entities.get("therapy") or "this therapy"

    targets: list[dict[str, str | None]] = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if not gene:
            continue
        moa = _clean_value(row.get("targets_moa")) or None
        targets.append({"gene": gene, "moa": moa})

    if not targets:
        return None

    total_targets = len(targets)
    capped = _cap_items(targets, speak_top_n)

    return TherapyTargetsPayload(
        intent="therapy_targets_query",
        therapy=therapy,
        total_targets=total_targets,
        targets=capped,
    )


def build_gene_targeting_therapies_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> GeneTargetingTherapiesPayload | None:
    """Build payload for gene targeting therapies query. Returns None if no results."""
    if not results:
        return None

    gene = entities.get("gene") or "this gene"

    therapies: list[dict[str, str | None]] = []
    for row in results:
        therapy = _clean_value(row.get("therapy_name"))
        if not therapy:
            continue
        moa = _clean_value(row.get("targets_moa")) or None
        therapies.append({"therapy": therapy, "moa": moa})

    if not therapies:
        return None

    total_therapies = len(therapies)
    capped = _cap_items(therapies, speak_top_n)

    return GeneTargetingTherapiesPayload(
        intent="gene_targeting_therapies_query",
        gene=gene,
        total_therapies=total_therapies,
        therapies=capped,
    )


def build_gene_variants_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> GeneVariantsPayload | None:
    """Build payload for gene variants query. Returns None if no results."""
    if not results:
        return None

    gene = entities.get("gene") or "this gene"

    variants: list[dict[str, str | int | None]] = []
    for row in results:
        variant = _clean_value(row.get("variant_name"))
        if not variant:
            continue
        best_level = _clean_value(row.get("best_evidence_level")) or None
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        variants.append(
            {
                "variant": variant,
                "best_level": best_level,
                "evidence_count": count,
            }
        )

    if not variants:
        return None

    total_variants = len(variants)
    capped = _cap_items(variants, speak_top_n)

    return GeneVariantsPayload(
        intent="gene_variants_query",
        gene=gene,
        total_variants=total_variants,
        top_variants=capped,
    )


def build_variant_response_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> VariantResponsePayload | None:
    """Build payload for variant response query. Returns None if no results."""
    if not results:
        return None

    variant = entities.get("variant") or "this variant"
    therapy = entities.get("therapy") or "this therapy"

    items: list[dict[str, str | int | None]] = []
    for row in results:
        effect_raw = _clean_value(row.get("effect"))
        if not effect_raw:
            continue
        effect = effect_raw.lower()
        if effect not in {"sensitivity", "resistance"}:
            continue
        disease = _clean_value(row.get("disease_name")) or None
        best_level = _clean_value(row.get("best_evidence_level")) or None
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        items.append(
            {
                "effect": effect,
                "disease": disease,
                "best_level": best_level,
                "evidence_count": count,
            }
        )

    if not items:
        return None

    capped = _cap_items(items, speak_top_n)

    return VariantResponsePayload(
        intent="variant_response_query",
        variant=variant,
        therapy=therapy,
        results=capped,
    )


def build_gene_overview_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,  # unused but kept for signature consistency
) -> GeneOverviewPayload | None:
    """Build payload for gene overview query. Returns None if gene not found."""
    if not results:
        return None

    gene = entities.get("gene") or "this gene"

    row = results[0]
    variant_count_raw = row.get("variant_count", 0)
    therapy_count_raw = row.get("therapy_count", 0)

    variant_count = int(variant_count_raw) if isinstance(variant_count_raw, (int, float)) else 0
    therapy_count = int(therapy_count_raw) if isinstance(therapy_count_raw, (int, float)) else 0

    if variant_count == 0 and therapy_count == 0:
        # Gene exists but no useful stats; treat as no-results for this payload
        return None

    return GeneOverviewPayload(
        intent="gene_overview_query",
        gene=gene,
        variant_count=variant_count,
        therapy_count=therapy_count,
    )


def build_therapy_overview_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> TherapyOverviewPayload | None:
    """Build payload for therapy overview query. Returns None if therapy not found."""
    if not results:
        return None

    therapy = entities.get("therapy") or "this therapy"

    row0 = results[0]
    target_count_raw = row0.get("target_count", 0)
    biomarker_count_raw = row0.get("biomarker_count", 0)

    target_count = int(target_count_raw) if isinstance(target_count_raw, (int, float)) else 0
    biomarker_count = int(biomarker_count_raw) if isinstance(biomarker_count_raw, (int, float)) else 0

    targets: list[dict[str, str | None]] = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if not gene:
            continue
        moa = _clean_value(row.get("targets_moa")) or None
        targets.append({"gene": gene, "moa": moa})

    capped_targets = _cap_items(targets, speak_top_n) if targets else []

    if target_count == 0 and biomarker_count == 0 and not capped_targets:
        return None

    return TherapyOverviewPayload(
        intent="therapy_overview_query",
        therapy=therapy,
        target_count=target_count,
        biomarker_count=biomarker_count,
        targets=capped_targets,
    )


def build_disease_biomarkers_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> DiseaseBiomarkersPayload | None:
    """Build payload for disease biomarkers query. Returns None if no results."""
    if not results:
        return None

    disease = entities.get("disease") or "this disease"

    genes: list[dict[str, str | int | None]] = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if not gene:
            continue
        best_level = _clean_value(row.get("best_evidence_level")) or None
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        genes.append(
            {
                "gene": gene,
                "best_level": best_level,
                "evidence_count": count,
            }
        )

    if not genes:
        return None

    total_genes = len(genes)
    capped = _cap_items(genes, speak_top_n)

    return DiseaseBiomarkersPayload(
        intent="disease_biomarkers_query",
        disease=disease,
        total_genes=total_genes,
        top_genes=capped,
    )


def build_disease_therapies_payload(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    speak_top_n: int = 3,
) -> DiseaseTherapiesPayload | None:
    """Build payload for disease therapies query. Returns None if no results."""
    if not results:
        return None

    disease = entities.get("disease") or "this disease"

    therapies: list[dict[str, int]] = []
    for row in results:
        therapy = _clean_value(row.get("therapy_name"))
        if not therapy:
            continue
        count_raw = row.get("evidence_count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        therapies.append({"therapy": therapy, "evidence_count": count})

    if not therapies:
        return None

    total_therapies = len(therapies)
    capped = _cap_items(therapies, speak_top_n)

    return DiseaseTherapiesPayload(
        intent="disease_therapies_query",
        disease=disease,
        total_therapies=total_therapies,
        therapies=capped,
    )
