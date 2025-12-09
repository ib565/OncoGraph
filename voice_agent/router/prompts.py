from __future__ import annotations

from textwrap import dedent

from .models import INTENT_IDS, INTENT_REQUIRED_ENTITIES

ROUTER_SYSTEM_MESSAGE = "You are a fast intent router for an oncology knowledge graph."


def _format_intent_table() -> str:
    rows: list[str] = []
    for intent in INTENT_IDS:
        required = INTENT_REQUIRED_ENTITIES[intent]
        required_str = ", ".join(required) if required else "none"
        rows.append(f"- {intent}: required = {required_str}")
    return "\n".join(rows)


FEW_SHOT_EXAMPLES = [
    ("Which genes predict resistance to cetuximab?", "resistance_biomarkers", {"therapy": "cetuximab"}),
    ("What does vemurafenib target?", "therapy_targets", {"therapy": "vemurafenib"}),
    ("What therapies target BRAF?", "gene_targeting_therapies", {"gene": "BRAF"}),
    ("Tell me about EGFR", "gene_overview", {"gene": "EGFR"}),
    ("What variants of KRAS have clinical evidence?", "gene_variants", {"gene": "KRAS"}),
    (
        "Does BRAF V600E respond to dabrafenib?",
        "variant_response",
        {"variant": "V600E", "therapy": "dabrafenib", "gene": "BRAF"},
    ),
    (
        "What predicts sensitivity to imatinib in leukemia?",
        "sensitivity_biomarkers",
        {"therapy": "imatinib", "disease": "leukemia"},
    ),
    ("What biomarkers matter in lung cancer?", "disease_biomarkers", {"disease": "lung cancer"}),
    ("What therapies have evidence in colorectal cancer?", "disease_therapies", {"disease": "colorectal cancer"}),
    ("Tell me about cetuximab", "therapy_overview", {"therapy": "cetuximab"}),
    ("Compare resistance profiles for cetuximab and panitumumab", "complex", {}),
    ("Hello", "conversational", {}),
    ("asdfghjkl", "unclear", {}),
]


def _format_examples() -> str:
    lines: list[str] = []
    for question, intent, entities in FEW_SHOT_EXAMPLES:
        lines.append(f"User: {question}")
        lines.append("Response JSON:")
        entity_parts = []
        for key in ("gene", "therapy", "disease", "variant"):
            value = entities.get(key)
            entity_parts.append(f'"{key}": "{value}"' if value is not None else f'"{key}": null')
        entities_json = ", ".join(entity_parts)
        lines.append(f'{{"intent": "{intent}", "confidence": 0.9, "entities": {{{entities_json}}}}}')
        lines.append("")
    return "\n".join(lines).strip()


def build_router_prompt(user_query: str) -> str:
    """Construct the router prompt with schema guidance and few-shots."""
    intent_table = _format_intent_table()
    examples = _format_examples()
    prompt = dedent(
        f"""
        {ROUTER_SYSTEM_MESSAGE}

        Available intents (with required entities):
        {intent_table}

        Entity rules:
        - Genes: uppercase symbols (e.g., KRAS, BRAF). Normalize obvious casing.
        - Therapies: lowercase names (e.g., cetuximab, vemurafenib). Normalize obvious casing.
        - Disease: keep user wording; no strict normalization.
        - Variants: keep as provided; if gene + variant provided, keep both
          (e.g., BRAF V600E -> gene=BRAF, variant=V600E).

        Output:
        - Strict JSON matching:
          {{"intent": <intent>, "confidence": <float 0-1>,
            "entities": {{"gene": str|null, "therapy": str|null, "disease": str|null, "variant": str|null}}}}
        - No code fences, no explanations, no extra fields.
        - Set intent="unclear" with confidence<=0.3 if you cannot classify.
        - Use confidence=1.0 when the match is obvious; lower when ambiguous.

        Examples:
        {examples}

        User query: "{user_query.strip()}"
        Respond with JSON only.
        """
    ).strip()
    return prompt


