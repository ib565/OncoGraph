from __future__ import annotations

from textwrap import dedent

# Intents that are routed but do not have executable templates.
SPECIAL_INTENTS = [
    {
        "id": "conversational",
        "description": "Greetings, thanks, goodbyes, or off-topic chat that doesn't require database queries",
        "example": "Hello",
    },
    {
        "id": "complex",
        "description": "Multi-entity comparisons or exclusions that need deeper analysis beyond templates",
        "example": "Compare resistance profiles for cetuximab and panitumumab",
    },
    {
        "id": "unclear",
        "description": "Cannot determine intent from the query (too vague or gibberish)",
        "example": "asdfghjkl",
    },
]

ROUTER_SYSTEM_MESSAGE = """You are a fast intent router for an oncology knowledge graph.
You will be given a user query and you will need to determine the intent of the query, 
along with the relevant entities that are present in the query.
"""


def _format_intent_table() -> str:
    rows: list[str] = []
    from voice_agent.templates.registry import INTENT_IDS, TEMPLATES

    for intent_id in INTENT_IDS:
        if intent_id not in TEMPLATES:
            continue
        template = TEMPLATES[intent_id]
        required = template.required_entities
        required_str = ", ".join(required) if required else "none"
        rows.append(f"- {intent_id}: {template.description} (required = {required_str})")
    for intent in SPECIAL_INTENTS:
        rows.append(f"- {intent['id']}: {intent['description']} (required = none)")
    return "\n".join(rows)


def _format_intent_examples() -> str:
    rows: list[str] = []
    from voice_agent.templates.registry import INTENT_IDS, TEMPLATES

    for intent_id in INTENT_IDS:
        if intent_id not in TEMPLATES:
            continue
        template = TEMPLATES[intent_id]
        if not template.example:
            continue
        rows.append(f'- {intent_id}: "{template.example}"')
    for intent in SPECIAL_INTENTS:
        rows.append(f'- {intent["id"]}: "{intent["example"]}"')
    return "\n".join(rows)


def _format_json_examples() -> str:
    """Format 2-3 complete JSON examples showing clear intent matches."""
    examples = [
        (
            "What genes predict resistance to trastuzumab?",
            "resistance_biomarkers_query",
            1.0,
            {"therapy": "trastuzumab", "gene": None, "disease": None, "variant": None},
        ),
        (
            "What is KRAS?",
            "gene_overview_query",
            1.0,
            {"gene": "KRAS", "therapy": None, "disease": None, "variant": None},
        ),
        (
            "What does erlotinib target?",
            "therapy_targets_query",
            1.0,
            {"therapy": "erlotinib", "gene": None, "disease": None, "variant": None},
        ),
    ]
    lines: list[str] = []
    for query, intent, confidence, entities in examples:
        lines.append(f'User: "{query}"')
        lines.append("Response JSON:")
        entity_parts = []
        for key in ("gene", "therapy", "disease", "variant"):
            value = entities.get(key)
            entity_parts.append(f'"{key}": "{value}"' if value is not None else f'"{key}": null')
        entities_json = ", ".join(entity_parts)
        lines.append(f'{{"intent": "{intent}", "confidence": {confidence}, "entities": {{{entities_json}}}}}')
        lines.append("")
    return "\n".join(lines).strip()


def build_router_prompt(user_query: str) -> str:
    """Construct the router prompt with schema guidance and few-shots."""
    intent_table = _format_intent_table()
    intent_examples = _format_intent_examples()
    json_examples = _format_json_examples()
    prompt = dedent(
        f"""
        {ROUTER_SYSTEM_MESSAGE}

        Available intents (with required entities):
        {intent_table}

        Intent examples:
        {intent_examples}

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
        - Set intent="unclear" with confidence<=0.3 if you cannot classify.
        - Use confidence=1.0 when the match is obvious; lower when ambiguous.

        Examples:
        {json_examples}

        User query: "{user_query.strip()}"
        Respond with JSON only.
        """
    ).strip()
    return prompt


if __name__ == "__main__":
    print("Example prompt:")
    print(build_router_prompt("Which genes predict resistance to cetuximab?"))
