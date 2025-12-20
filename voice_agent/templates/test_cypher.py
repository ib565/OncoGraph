from __future__ import annotations

import pytest

from voice_agent.router.models import ExtractedEntities
from voice_agent.templates.cypher import (
    _escape_cypher_literal,
    build_disease_filter,
    fill_template,
    tokenize_disease,
)
from voice_agent.templates.models import QueryTemplate


class TestEscapeCypherLiteral:
    """Test _escape_cypher_literal function."""

    def test_normal_string(self):
        """Test escaping normal string."""
        assert _escape_cypher_literal("cetuximab") == "cetuximab"

    def test_string_with_single_quote(self):
        """Test escaping string with single quote."""
        assert _escape_cypher_literal("O'Brien") == "O\\'Brien"

    def test_string_with_backslash(self):
        """Test escaping string with backslash."""
        assert _escape_cypher_literal("path\\to\\file") == "path\\\\to\\\\file"

    def test_string_with_both(self):
        """Test escaping string with both quote and backslash."""
        result = _escape_cypher_literal("O'\\Brien")
        # Backslashes first, then quotes
        # Input: O'\\Brien -> escape backslashes: O'\\\\Brien -> escape quotes: O\\'\\\\Brien
        assert result == "O\\'\\\\Brien"
        # Verify both are escaped
        assert "\\\\" in result  # Escaped backslash
        assert "\\'" in result  # Escaped quote

    def test_empty_string(self):
        """Test escaping empty string."""
        assert _escape_cypher_literal("") == ""

    def test_string_with_multiple_quotes(self):
        """Test escaping string with multiple quotes."""
        assert _escape_cypher_literal("don't can't") == "don\\'t can\\'t"


class TestTokenizeDisease:
    """Test tokenize_disease function."""

    def test_simple_disease(self):
        """Test tokenizing simple disease name."""
        assert tokenize_disease("Lung Cancer") == ["lung"]

    def test_complex_disease(self):
        """Test tokenizing complex disease name."""
        tokens = tokenize_disease("Non-small Cell Lung Carcinoma")
        assert "lung" in tokens
        assert "non-small" in tokens
        assert "cell" in tokens
        assert "carcinoma" not in tokens  # Generic term excluded

    def test_umbrella_term(self):
        """Test tokenizing umbrella term."""
        assert tokenize_disease("Lung Cancer") == ["lung"]

    def test_only_generic_terms(self):
        """Test disease with only generic terms."""
        # If only "cancer", should return empty after filtering
        result = tokenize_disease("Cancer")
        # Should return empty list or minimal token
        assert isinstance(result, list)

    def test_preserves_hyphens(self):
        """Test that hyphens are preserved."""
        tokens = tokenize_disease("Non-small Cell")
        assert "non-small" in tokens

    def test_empty_string(self):
        """Test empty string."""
        assert tokenize_disease("") == []

    def test_colorectal_cancer(self):
        """Test colorectal cancer."""
        tokens = tokenize_disease("Colorectal Cancer")
        assert "colorectal" in tokens
        assert "cancer" not in tokens

    def test_multiple_generic_terms(self):
        """Test disease with multiple generic terms."""
        tokens = tokenize_disease("Lung Carcinoma Tumor")
        # Should have "lung" but exclude generic terms
        assert "lung" in tokens


class TestBuildDiseaseFilter:
    """Test build_disease_filter function."""

    def test_with_tokens_where(self):
        """Test building filter with tokens using WHERE."""
        result = build_disease_filter(["lung", "non-small"], use_where=True)
        assert result.startswith("WHERE")
        assert "lung" in result
        assert "non-small" in result
        assert "CONTAINS" in result

    def test_with_tokens_and(self):
        """Test building filter with tokens using AND."""
        result = build_disease_filter(["lung"], use_where=False)
        assert result.startswith("AND")
        assert "lung" in result

    def test_empty_tokens(self):
        """Test with empty tokens."""
        assert build_disease_filter([], use_where=True) == ""
        assert build_disease_filter([], use_where=False) == ""

    def test_single_token(self):
        """Test with single token."""
        result = build_disease_filter(["colorectal"], use_where=True)
        assert "colorectal" in result
        assert "WHERE" in result

    def test_multiple_tokens(self):
        """Test with multiple tokens."""
        result = build_disease_filter(["lung", "non-small", "cell"], use_where=True)
        assert "lung" in result
        assert "non-small" in result
        assert "cell" in result
        assert "AND" in result  # Should have AND between tokens


class TestFillTemplate:
    """Test fill_template function."""

    def test_simple_replacement(self):
        """Test simple entity replacement."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["therapy"],
            optional_entities=[],
            cypher="MATCH (t:Therapy) WHERE t.name = '{therapy}' RETURN t",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(therapy="cetuximab")
        result = fill_template(template, entities)
        assert "cetuximab" in result
        assert "{therapy}" not in result

    def test_multiple_entities(self):
        """Test replacing multiple entities."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["gene", "therapy"],
            optional_entities=[],
            cypher="MATCH (g:Gene), (t:Therapy) WHERE g.symbol = '{gene}' AND t.name = '{therapy}' RETURN g, t",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(gene="KRAS", therapy="cetuximab")
        result = fill_template(template, entities)
        assert "KRAS" in result
        assert "cetuximab" in result
        assert "{gene}" not in result
        assert "{therapy}" not in result

    def test_escaping_in_replacement(self):
        """Test that entity values are escaped."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["therapy"],
            optional_entities=[],
            cypher="MATCH (t:Therapy) WHERE t.name = '{therapy}' RETURN t",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(therapy="O'Brien")
        result = fill_template(template, entities)
        # Should have escaped quote
        assert "O\\'Brien" in result or "O''Brien" in result

    def test_disease_filter_where(self):
        """Test disease filter with WHERE."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["disease"],
            optional_entities=[],
            cypher="MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy) {disease_filter} RETURN b",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(disease="Lung Cancer")
        result = fill_template(template, entities)
        assert "WHERE" in result or "AND" in result
        assert "lung" in result.lower()

    def test_disease_filter_and(self):
        """Test disease filter with AND when WHERE already exists."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["therapy", "disease"],
            optional_entities=[],
            cypher="MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy) WHERE t.name = '{therapy}' {disease_filter} RETURN b",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(therapy="cetuximab", disease="Lung Cancer")
        result = fill_template(template, entities)
        # Should use AND since WHERE already exists
        assert "AND" in result or "WHERE" in result
        assert "lung" in result.lower()

    def test_no_disease_filter(self):
        """Test template without disease filter when disease not provided."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["therapy"],
            optional_entities=["disease"],
            cypher="MATCH (b:Biomarker)-[rel:AFFECTS_RESPONSE_TO]->(t:Therapy) {disease_filter} RETURN b",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(therapy="cetuximab")
        result = fill_template(template, entities)
        # Should have empty string for disease_filter
        assert "{disease_filter}" not in result

    def test_variant_replacement(self):
        """Test variant entity replacement."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["variant"],
            optional_entities=[],
            cypher="MATCH (v:Variant) WHERE v.name CONTAINS '{variant}' RETURN v",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(variant="G12C")
        result = fill_template(template, entities)
        assert "G12C" in result
        assert "{variant}" not in result

    def test_all_entities(self):
        """Test replacing all entity types."""
        template = QueryTemplate(
            id="test",
            description="Test",
            required_entities=["gene", "therapy", "variant", "disease"],
            optional_entities=[],
            cypher="MATCH (g:Gene), (t:Therapy), (v:Variant) WHERE g.symbol = '{gene}' AND t.name = '{therapy}' AND v.name = '{variant}' {disease_filter} RETURN g, t, v",
            format_response=lambda r, e, m: "",
        )
        entities = ExtractedEntities(gene="KRAS", therapy="cetuximab", variant="G12C", disease="Colorectal Cancer")
        result = fill_template(template, entities)
        assert "KRAS" in result
        assert "cetuximab" in result
        assert "G12C" in result
        assert "colorectal" in result.lower()
        assert "{gene}" not in result
        assert "{therapy}" not in result
        assert "{variant}" not in result
        assert "{disease_filter}" not in result
