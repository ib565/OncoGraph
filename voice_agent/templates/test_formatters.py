from __future__ import annotations

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


class TestResistanceBiomarkersFormatter:
    """Test resistance_biomarkers_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = resistance_biomarkers_formatter([], {"therapy": "cetuximab"}, 3)
        assert "didn't find" in result.lower()
        assert "cetuximab" in result

    def test_single_result(self):
        """Test with single result."""
        results = [{"gene_symbol": "KRAS", "best_evidence_level": "A", "evidence_count": 5}]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        assert "KRAS" in result
        assert "cetuximab" in result
        assert "one" in result or "1" in result

    def test_three_results(self):
        """Test with three results."""
        results = [
            {"gene_symbol": "KRAS", "best_evidence_level": "A", "evidence_count": 5},
            {"gene_symbol": "BRAF", "best_evidence_level": "B", "evidence_count": 3},
            {"gene_symbol": "EGFR", "best_evidence_level": "A", "evidence_count": 2},
        ]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        assert "KRAS" in result
        assert "BRAF" in result
        assert "EGFR" in result
        assert "three" in result or "3" in result

    def test_five_results(self):
        """Test with five results (should list top 3)."""
        results = [
            {"gene_symbol": "KRAS", "best_evidence_level": "A", "evidence_count": 5},
            {"gene_symbol": "BRAF", "best_evidence_level": "B", "evidence_count": 3},
            {"gene_symbol": "EGFR", "best_evidence_level": "A", "evidence_count": 2},
            {"gene_symbol": "PIK3CA", "best_evidence_level": "B", "evidence_count": 1},
            {"gene_symbol": "TP53", "best_evidence_level": "C", "evidence_count": 1},
        ]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        assert "KRAS" in result
        assert "BRAF" in result
        assert "EGFR" in result
        assert "five" in result or "5" in result
        assert "others" in result or "two" in result

    def test_with_evidence_level(self):
        """Test with evidence level."""
        results = [{"gene_symbol": "KRAS", "best_evidence_level": "A", "evidence_count": 5}]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        assert "level" in result.lower() or "evidence" in result.lower()


class TestSensitivityBiomarkersFormatter:
    """Test sensitivity_biomarkers_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = sensitivity_biomarkers_formatter([], {"therapy": "imatinib"}, 3)
        assert "didn't find" in result.lower()
        assert "imatinib" in result

    def test_single_result(self):
        """Test with single result."""
        results = [{"gene_symbol": "BCR", "best_evidence_level": "A", "evidence_count": 10}]
        result = sensitivity_biomarkers_formatter(results, {"therapy": "imatinib"}, 3)
        assert "BCR" in result
        assert "imatinib" in result


class TestTherapyTargetsFormatter:
    """Test therapy_targets_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = therapy_targets_formatter([], {"therapy": "vemurafenib"}, 3)
        assert "didn't find" in result.lower()

    def test_single_result(self):
        """Test with single result."""
        results = [{"gene_symbol": "BRAF", "targets_moa": "inhibitor"}]
        result = therapy_targets_formatter(results, {"therapy": "vemurafenib"}, 3)
        assert "BRAF" in result
        assert "vemurafenib" in result
        assert "targets" in result

    def test_multiple_results(self):
        """Test with multiple results."""
        results = [
            {"gene_symbol": "BRAF", "targets_moa": "inhibitor"},
            {"gene_symbol": "MEK", "targets_moa": "inhibitor"},
        ]
        result = therapy_targets_formatter(results, {"therapy": "vemurafenib"}, 3)
        assert "BRAF" in result
        assert "two" in result or "2" in result


class TestGeneTargetingTherapiesFormatter:
    """Test gene_targeting_therapies_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = gene_targeting_therapies_formatter([], {"gene": "BRAF"}, 3)
        assert "didn't find" in result.lower()

    def test_single_result(self):
        """Test with single result."""
        results = [{"therapy_name": "vemurafenib", "targets_moa": "inhibitor"}]
        result = gene_targeting_therapies_formatter(results, {"gene": "BRAF"}, 3)
        assert "vemurafenib" in result
        assert "BRAF" in result

    def test_multiple_results_same_moa(self):
        """Test with multiple results, same MOA."""
        results = [
            {"therapy_name": "vemurafenib", "targets_moa": "inhibitor"},
            {"therapy_name": "dabrafenib", "targets_moa": "inhibitor"},
        ]
        result = gene_targeting_therapies_formatter(results, {"gene": "BRAF"}, 3)
        assert "vemurafenib" in result
        assert "dabrafenib" in result
        assert "inhibitor" in result


class TestGeneVariantsFormatter:
    """Test gene_variants_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = gene_variants_formatter([], {"gene": "KRAS"}, 3)
        assert "no variants" in result.lower() or "has no" in result.lower()

    def test_single_result(self):
        """Test with single result."""
        results = [{"variant_name": "G12C"}]
        result = gene_variants_formatter(results, {"gene": "KRAS"}, 3)
        assert "G12C" in result
        assert "KRAS" in result

    def test_multiple_results(self):
        """Test with multiple results."""
        results = [
            {"variant_name": "G12C"},
            {"variant_name": "G12D"},
            {"variant_name": "G13D"},
        ]
        result = gene_variants_formatter(results, {"gene": "KRAS"}, 3)
        assert "G12C" in result
        assert "G12D" in result
        assert "G13D" in result


class TestVariantResponseFormatter:
    """Test variant_response_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = variant_response_formatter([], {"variant": "V600E", "therapy": "dabrafenib"}, 3)
        assert "don't have evidence" in result.lower() or "no evidence" in result.lower()

    def test_single_sensitivity_result(self):
        """Test with single sensitivity result."""
        results = [
            {
                "effect": "sensitivity",
                "disease_name": "Melanoma",
                "best_evidence_level": "A",
                "evidence_count": 10,
            }
        ]
        result = variant_response_formatter(results, {"variant": "V600E", "therapy": "dabrafenib"}, 3)
        assert "sensitivity" in result.lower()
        assert "V600E" in result
        assert "dabrafenib" in result

    def test_single_resistance_result(self):
        """Test with single resistance result."""
        results = [
            {
                "effect": "resistance",
                "disease_name": "Colorectal Cancer",
                "best_evidence_level": "B",
                "evidence_count": 5,
            }
        ]
        result = variant_response_formatter(results, {"variant": "G12C", "therapy": "cetuximab"}, 3)
        assert "resistance" in result.lower()
        assert "G12C" in result
        assert "cetuximab" in result

    def test_both_effects(self):
        """Test with both sensitivity and resistance."""
        results = [
            {
                "effect": "sensitivity",
                "disease_name": "Melanoma",
                "best_evidence_level": "A",
                "evidence_count": 10,
            },
            {
                "effect": "resistance",
                "disease_name": "Colorectal Cancer",
                "best_evidence_level": "B",
                "evidence_count": 5,
            },
        ]
        result = variant_response_formatter(results, {"variant": "V600E", "therapy": "dabrafenib"}, 3)
        assert "sensitivity" in result.lower()
        assert "resistance" in result.lower()


class TestGeneOverviewFormatter:
    """Test gene_overview_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = gene_overview_formatter([], {"gene": "KRAS"}, 3)
        assert "not in my database" in result.lower()

    def test_with_variants_and_therapies(self):
        """Test with variants and therapies."""
        results = [{"gene_symbol": "KRAS", "variant_count": 10, "therapy_count": 5}]
        result = gene_overview_formatter(results, {"gene": "KRAS"}, 3)
        assert "KRAS" in result
        assert "ten" in result or "10" in result
        assert "five" in result or "5" in result

    def test_with_only_variants(self):
        """Test with only variants."""
        results = [{"gene_symbol": "KRAS", "variant_count": 10, "therapy_count": 0}]
        result = gene_overview_formatter(results, {"gene": "KRAS"}, 3)
        assert "variants" in result
        assert "therap" not in result.lower()


class TestTherapyOverviewFormatter:
    """Test therapy_overview_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = therapy_overview_formatter([], {"therapy": "cetuximab"}, 3)
        assert "not in my database" in result.lower()

    def test_with_all_info(self):
        """Test with targets and biomarkers."""
        results = [
            {
                "therapy_name": "cetuximab",
                "target_count": 1,
                "biomarker_count": 20,
            }
        ]
        result = therapy_overview_formatter(results, {"therapy": "cetuximab"}, 3)
        assert "cetuximab" in result
        assert "one" in result or "1" in result
        assert "twenty" in result or "20" in result


class TestDiseaseBiomarkersFormatter:
    """Test disease_biomarkers_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = disease_biomarkers_formatter([], {"disease": "lung cancer"}, 3)
        assert "didn't find" in result.lower()

    def test_single_result(self):
        """Test with single result."""
        results = [{"gene_symbol": "EGFR", "best_evidence_level": "A", "evidence_count": 10}]
        result = disease_biomarkers_formatter(results, {"disease": "lung cancer"}, 3)
        assert "EGFR" in result
        assert "lung cancer" in result or "lung" in result

    def test_multiple_results(self):
        """Test with multiple results."""
        results = [
            {"gene_symbol": "EGFR", "best_evidence_level": "A", "evidence_count": 10},
            {"gene_symbol": "KRAS", "best_evidence_level": "B", "evidence_count": 5},
            {"gene_symbol": "BRAF", "best_evidence_level": "A", "evidence_count": 3},
        ]
        result = disease_biomarkers_formatter(results, {"disease": "lung cancer"}, 3)
        assert "EGFR" in result
        assert "KRAS" in result
        assert "BRAF" in result


class TestDiseaseTherapiesFormatter:
    """Test disease_therapies_formatter."""

    def test_empty_results(self):
        """Test with empty results."""
        result = disease_therapies_formatter([], {"disease": "colorectal cancer"}, 3)
        assert "didn't find" in result.lower()

    def test_single_result(self):
        """Test with single result."""
        results = [{"therapy_name": "cetuximab", "evidence_count": 10}]
        result = disease_therapies_formatter(results, {"disease": "colorectal cancer"}, 3)
        assert "cetuximab" in result
        assert "colorectal" in result.lower() or "cancer" in result.lower()

    def test_multiple_results(self):
        """Test with multiple results."""
        results = [
            {"therapy_name": "cetuximab", "evidence_count": 10},
            {"therapy_name": "panitumumab", "evidence_count": 8},
            {"therapy_name": "bevacizumab", "evidence_count": 5},
        ]
        result = disease_therapies_formatter(results, {"disease": "colorectal cancer"}, 3)
        assert "cetuximab" in result
        assert "panitumumab" in result
        assert "bevacizumab" in result


class TestFormatterEdgeCases:
    """Test edge cases for all formatters."""

    def test_none_entities(self):
        """Test formatters handle None entities gracefully."""
        results = [{"gene_symbol": "KRAS"}]
        result = resistance_biomarkers_formatter(results, {"therapy": None}, 3)
        # Should use fallback text
        assert "therapy" in result.lower() or "this" in result.lower()

    def test_missing_fields_in_results(self):
        """Test formatters handle missing fields."""
        results = [{}]  # Empty dict
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        # Should handle gracefully
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_values_in_results(self):
        """Test formatters handle None values in results."""
        results = [{"gene_symbol": None, "best_evidence_level": None}]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, 3)
        # Should handle None gracefully
        assert isinstance(result, str)

    def test_custom_max_items(self):
        """Test formatters respect max_items_to_list parameter."""
        results = [
            {"gene_symbol": "KRAS"},
            {"gene_symbol": "BRAF"},
            {"gene_symbol": "EGFR"},
            {"gene_symbol": "PIK3CA"},
            {"gene_symbol": "TP53"},
        ]
        result = resistance_biomarkers_formatter(results, {"therapy": "cetuximab"}, max_items_to_list=2)
        # Should only list 2 items
        assert "KRAS" in result
        assert "BRAF" in result
        # Should mention others
        assert "others" in result or "three" in result
