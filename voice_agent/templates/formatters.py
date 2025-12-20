from __future__ import annotations

# Number words for voice-friendly output
_NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
}


def _number_to_word(n: int) -> str:
    """Convert number to word for voice-friendly output."""
    if n <= 20:
        return _NUMBER_WORDS.get(n, str(n))
    return str(n)


def _clean_value(value: object) -> str:
    """Clean and stringify a value from Neo4j results."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v)
    return str(value)


def _get_evidence_level_text(level: str | None) -> str:
    """Get evidence level text for voice output."""
    if not level:
        return ""
    level_upper = level.upper()
    if level_upper in ("A", "B"):
        return f"Level {level_upper} evidence"
    return f"Level {level_upper} evidence"


def _format_gene_list(genes: list[str], max_items: int = 3) -> str:
    """Format a list of genes for voice output."""
    if not genes:
        return ""
    if len(genes) <= max_items:
        if len(genes) == 1:
            return genes[0]
        if len(genes) == 2:
            return f"{genes[0]} and {genes[1]}"
        # 3 items: "X, Y, and Z"
        return ", ".join(genes[:-1]) + f", and {genes[-1]}"
    # More than max_items: "X, Y, Z, and N others"
    listed = genes[:max_items]
    others_count = len(genes) - max_items
    return ", ".join(listed) + f", and {_number_to_word(others_count)} others"


def resistance_biomarkers_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format resistance biomarkers query results."""
    therapy = entities.get("therapy", "this therapy") or "this therapy"

    if not results:
        return f"I didn't find resistance biomarkers for {therapy}."

    # Extract genes and evidence
    genes = []
    evidence_info = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if gene:
            genes.append(gene)
            level = _clean_value(row.get("best_evidence_level"))
            count = row.get("evidence_count", 0)
            if isinstance(count, (int, float)) and count > 0:
                evidence_info.append((gene, level, int(count)))

    if not genes:
        return f"I didn't find resistance biomarkers for {therapy}."

    # Build response
    gene_list = _format_gene_list(genes, max_items_to_list)
    total = len(genes)

    # Check for strong evidence (A/B)
    strong_evidence = [g for g, l, _ in evidence_info if l and l.upper() in ("A", "B")]
    if strong_evidence and total <= max_items_to_list:
        level_text = _get_evidence_level_text(evidence_info[0][1] if evidence_info else None)
        if level_text:
            return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting resistance to {therapy}: {gene_list}, with {level_text.lower()}."
        return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting resistance to {therapy}: {gene_list}."

    if total > max_items_to_list:
        return f"Found {_number_to_word(total)} genes predicting resistance to {therapy}. Top ones are {gene_list}. Want pathway enrichment?"

    return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting resistance to {therapy}: {gene_list}."


def sensitivity_biomarkers_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format sensitivity biomarkers query results."""
    therapy = entities.get("therapy", "this therapy") or "this therapy"

    if not results:
        return f"I didn't find sensitivity biomarkers for {therapy}."

    # Extract genes and evidence
    genes = []
    evidence_info = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if gene:
            genes.append(gene)
            level = _clean_value(row.get("best_evidence_level"))
            count = row.get("evidence_count", 0)
            if isinstance(count, (int, float)) and count > 0:
                evidence_info.append((gene, level, int(count)))

    if not genes:
        return f"I didn't find sensitivity biomarkers for {therapy}."

    # Build response
    gene_list = _format_gene_list(genes, max_items_to_list)
    total = len(genes)

    # Check for strong evidence (A/B)
    strong_evidence = [g for g, l, _ in evidence_info if l and l.upper() in ("A", "B")]
    if strong_evidence and total <= max_items_to_list:
        level_text = _get_evidence_level_text(evidence_info[0][1] if evidence_info else None)
        if level_text:
            return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting sensitivity to {therapy}: {gene_list}, with {level_text.lower()}."
        return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting sensitivity to {therapy}: {gene_list}."

    if total > max_items_to_list:
        return f"Found {_number_to_word(total)} genes predicting sensitivity to {therapy}. Top ones are {gene_list}. Want pathway enrichment?"

    return f"Found {_number_to_word(total)} gene{'s' if total > 1 else ''} predicting sensitivity to {therapy}: {gene_list}."


def therapy_targets_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format therapy targets query results."""
    therapy = entities.get("therapy", "this therapy") or "this therapy"

    if not results:
        return f"I didn't find target genes for {therapy}."

    # Extract genes and mechanisms
    targets = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        moa = _clean_value(row.get("targets_moa"))
        if gene:
            targets.append((gene, moa))

    if not targets:
        return f"I didn't find target genes for {therapy}."

    if len(targets) == 1:
        gene, moa = targets[0]
        if moa:
            return f"{therapy} targets {gene} as a {moa}."
        return f"{therapy} targets {gene}."

    gene_list = _format_gene_list([g for g, _ in targets], max_items_to_list)
    total = len(targets)
    return f"{therapy} targets {_number_to_word(total)} genes: {gene_list}."


def gene_targeting_therapies_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format gene targeting therapies query results."""
    gene = entities.get("gene", "this gene") or "this gene"

    if not results:
        return f"I didn't find therapies targeting {gene}."

    # Extract therapies
    therapies = []
    mechanisms = []
    for row in results:
        therapy = _clean_value(row.get("therapy_name"))
        moa = _clean_value(row.get("targets_moa"))
        if therapy:
            therapies.append(therapy)
            if moa:
                mechanisms.append(moa)

    if not therapies:
        return f"I didn't find therapies targeting {gene}."

    therapy_list = _format_gene_list(therapies, max_items_to_list)
    total = len(therapies)

    # Check if all have same mechanism
    unique_mechanisms = set(m for m in mechanisms if m)
    if len(unique_mechanisms) == 1 and unique_mechanisms:
        mechanism = list(unique_mechanisms)[0]
        return f"{_number_to_word(total)} therap{'ies' if total > 1 else 'y'} target{'s' if total == 1 else ''} {gene}: {therapy_list}. All are {mechanism}s."

    return f"{_number_to_word(total)} therap{'ies' if total > 1 else 'y'} target{'s' if total == 1 else ''} {gene}: {therapy_list}."


def gene_variants_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format gene variants query results."""
    gene = entities.get("gene", "this gene") or "this gene"

    if not results:
        return f"{gene} has no variants with clinical evidence in the database."

    # Extract variants
    variants = []
    for row in results:
        variant = _clean_value(row.get("variant_name"))
        if variant:
            variants.append(variant)

    if not variants:
        return f"{gene} has no variants with clinical evidence in the database."

    variant_list = _format_gene_list(variants, max_items_to_list)
    total = len(variants)

    if total > max_items_to_list:
        return f"{gene} has {_number_to_word(total)} variants with evidence. Most studied are {variant_list}."

    return f"{gene} has {_number_to_word(total)} variant{'s' if total > 1 else ''} with evidence: {variant_list}."


def variant_response_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format variant response query results."""
    variant = entities.get("variant", "this variant") or "this variant"
    therapy = entities.get("therapy", "this therapy") or "this therapy"

    if not results:
        return f"I don't have evidence for {variant} affecting {therapy} response."

    # Extract effects
    effects = []
    for row in results:
        effect = _clean_value(row.get("effect"))
        disease = _clean_value(row.get("disease_name"))
        level = _clean_value(row.get("best_evidence_level"))
        if effect:
            effects.append((effect, disease, level))

    if not effects:
        return f"I don't have evidence for {variant} affecting {therapy} response."

    # Group by effect type
    sensitivity = [e for e in effects if e[0].lower() == "sensitivity"]
    resistance = [e for e in effects if e[0].lower() == "resistance"]

    responses = []
    if sensitivity:
        e = sensitivity[0]
        level_text = _get_evidence_level_text(e[2])
        disease_text = f" in {e[1]}" if e[1] else ""
        level_suffix = f" with {level_text.lower()}" if level_text else ""
        responses.append(f"{variant} predicts sensitivity to {therapy}{disease_text}{level_suffix}")

    if resistance:
        e = resistance[0]
        level_text = _get_evidence_level_text(e[2])
        disease_text = f" in {e[1]}" if e[1] else ""
        level_suffix = f" with {level_text.lower()}" if level_text else ""
        responses.append(f"{variant} predicts resistance to {therapy}{disease_text}{level_suffix}")

    if not responses:
        return f"I don't have evidence for {variant} affecting {therapy} response."

    return ". ".join(responses) + "."


def gene_overview_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format gene overview query results."""
    gene = entities.get("gene", "this gene") or "this gene"

    if not results or len(results) == 0:
        return f"{gene} is not in my database."

    row = results[0]
    variant_count = row.get("variant_count", 0)
    therapy_count = row.get("therapy_count", 0)

    if isinstance(variant_count, (int, float)):
        variant_count = int(variant_count)
    else:
        variant_count = 0

    if isinstance(therapy_count, (int, float)):
        therapy_count = int(therapy_count)
    else:
        therapy_count = 0

    if variant_count == 0 and therapy_count == 0:
        return f"{gene} is in my database but has no variants or targeting therapies."

    parts = []
    if variant_count > 0:
        parts.append(f"{_number_to_word(variant_count)} variant{'s' if variant_count > 1 else ''}")
    if therapy_count > 0:
        parts.append(f"targeted by {_number_to_word(therapy_count)} therap{'ies' if therapy_count > 1 else 'y'}")

    return f"{gene} has {', '.join(parts)} in the database."


def therapy_overview_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format therapy overview query results."""
    therapy = entities.get("therapy", "this therapy") or "this therapy"

    if not results or len(results) == 0:
        return f"{therapy} is not in my database."

    row = results[0]
    modality = _clean_value(row.get("modality"))
    target_count = row.get("target_count", 0)
    biomarker_count = row.get("biomarker_count", 0)

    if isinstance(target_count, (int, float)):
        target_count = int(target_count)
    else:
        target_count = 0

    if isinstance(biomarker_count, (int, float)):
        biomarker_count = int(biomarker_count)
    else:
        biomarker_count = 0

    parts = []
    if modality:
        parts.append(f"a {modality}")

    if target_count > 0:
        parts.append(f"targets {_number_to_word(target_count)} gene{'s' if target_count > 1 else ''}")

    if biomarker_count > 0:
        parts.append(
            f"has {_number_to_word(biomarker_count)} biomarker association{'s' if biomarker_count > 1 else ''}"
        )

    if not parts:
        return f"{therapy} is in my database but has no target genes or biomarker associations."

    return f"{therapy} is {', '.join(parts)}."


def disease_biomarkers_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format disease biomarkers query results."""
    disease = entities.get("disease", "this disease") or "this disease"

    if not results:
        return f"I didn't find biomarkers for {disease}."

    # Extract genes and evidence
    genes = []
    evidence_info = []
    for row in results:
        gene = _clean_value(row.get("gene_symbol"))
        if gene:
            genes.append(gene)
            level = _clean_value(row.get("best_evidence_level"))
            count = row.get("evidence_count", 0)
            if isinstance(count, (int, float)) and count > 0:
                evidence_info.append((gene, level, int(count)))

    if not genes:
        return f"I didn't find biomarkers for {disease}."

    gene_list = _format_gene_list(genes, max_items_to_list)
    total = len(genes)

    # Check for strong evidence (A/B)
    strong_evidence = [g for g, l, _ in evidence_info if l and l.upper() in ("A", "B")]
    if strong_evidence and total <= max_items_to_list:
        level_text = _get_evidence_level_text(evidence_info[0][1] if evidence_info else None)
        if level_text:
            return f"In {disease}, top biomarkers are {gene_list} with {level_text.lower()}."
        return f"In {disease}, top biomarkers are {gene_list}."

    if total > max_items_to_list:
        return f"In {disease}, found {_number_to_word(total)} biomarker genes. Top ones are {gene_list} with Level A evidence."

    return f"In {disease}, top biomarkers are {gene_list}."


def disease_therapies_formatter(
    results: list[dict[str, object]],
    entities: dict[str, str | None],
    max_items_to_list: int = 3,
) -> str:
    """Format disease therapies query results."""
    disease = entities.get("disease", "this disease") or "this disease"

    if not results:
        return f"I didn't find therapies with biomarker evidence in {disease}."

    # Extract therapies
    therapies = []
    for row in results:
        therapy = _clean_value(row.get("therapy_name"))
        if therapy:
            therapies.append(therapy)

    if not therapies:
        return f"I didn't find therapies with biomarker evidence in {disease}."

    therapy_list = _format_gene_list(therapies, max_items_to_list)
    total = len(therapies)

    if total > max_items_to_list:
        return f"In {disease}, therapies with most evidence are {therapy_list}."

    return f"In {disease}, therapies with biomarker evidence are {therapy_list}."

