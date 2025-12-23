/**
 * Transform OncoGraph tool payloads into MiniGraph-compatible row format.
 * MiniGraph expects rows with fields like gene_symbol, therapy_name, variant_name,
 * effect, disease_name, targets_moa, relationship, evidence_levels, evidence_count.
 */

type Payload = 
  | ResistanceBiomarkersPayload
  | SensitivityBiomarkersPayload
  | TherapyTargetsPayload
  | GeneTargetingTherapiesPayload
  | GeneVariantsPayload
  | VariantResponsePayload
  | GeneOverviewPayload
  | TherapyOverviewPayload
  | DiseaseBiomarkersPayload
  | DiseaseTherapiesPayload;

type ResistanceBiomarkersPayload = {
  intent: "resistance_biomarkers_query";
  therapy: string;
  disease: string | null;
  total_genes: number;
  top_genes: Array<{ gene: string; best_level: string | null; evidence_count: number }>;
};

type SensitivityBiomarkersPayload = {
  intent: "sensitivity_biomarkers_query";
  therapy: string;
  disease: string | null;
  total_genes: number;
  top_genes: Array<{ gene: string; best_level: string | null; evidence_count: number }>;
};

type TherapyTargetsPayload = {
  intent: "therapy_targets_query";
  therapy: string;
  total_targets: number;
  targets: Array<{ gene: string; moa: string | null }>;
};

type GeneTargetingTherapiesPayload = {
  intent: "gene_targeting_therapies_query";
  gene: string;
  total_therapies: number;
  therapies: Array<{ therapy: string; moa: string | null }>;
};

type GeneVariantsPayload = {
  intent: "gene_variants_query";
  gene: string;
  total_variants: number;
  top_variants: Array<{ variant: string; best_level: string | null; evidence_count: number }>;
};

type VariantResponsePayload = {
  intent: "variant_response_query";
  variant: string;
  therapy: string;
  results: Array<{
    effect: "sensitivity" | "resistance";
    disease: string | null;
    best_level: string | null;
    evidence_count: number;
  }>;
};

type GeneOverviewPayload = {
  intent: "gene_overview_query";
  gene: string;
  variant_count: number;
  therapy_count: number;
};

type TherapyOverviewPayload = {
  intent: "therapy_overview_query";
  therapy: string;
  target_count: number;
  biomarker_count: number;
  targets: Array<{ gene: string; moa: string | null }>;
};

type DiseaseBiomarkersPayload = {
  intent: "disease_biomarkers_query";
  disease: string;
  total_genes: number;
  top_genes: Array<{ gene: string; best_level: string | null; evidence_count: number }>;
};

type DiseaseTherapiesPayload = {
  intent: "disease_therapies_query";
  disease: string;
  total_therapies: number;
  therapies: Array<{ therapy: string; evidence_count: number }>;
};

export function payloadToMiniGraphRows(payload: Payload): Array<Record<string, unknown>> {
  switch (payload.intent) {
    case "resistance_biomarkers_query":
    case "sensitivity_biomarkers_query": {
      const effect = payload.intent === "resistance_biomarkers_query" ? "resistance" : "sensitivity";
      return payload.top_genes.map((gene) => ({
        gene_symbol: gene.gene,
        therapy_name: payload.therapy,
        disease_name: payload.disease || null,
        effect,
        evidence_levels: gene.best_level ? [gene.best_level] : [],
        evidence_count: gene.evidence_count || 0,
        total_genes: payload.total_genes,
      }));
    }

    case "therapy_targets_query": {
      return payload.targets.map((target) => ({
        therapy_name: payload.therapy,
        gene_symbol: target.gene,
        targets_moa: target.moa || null,
        relationship: "TARGETS",
        total_targets: payload.total_targets,
      }));
    }

    case "gene_targeting_therapies_query": {
      return payload.therapies.map((therapy) => ({
        gene_symbol: payload.gene,
        therapy_name: therapy.therapy,
        targets_moa: therapy.moa || null,
        relationship: "TARGETS",
        total_therapies: payload.total_therapies,
      }));
    }

    case "gene_variants_query": {
      return payload.top_variants.map((variant) => ({
        gene_symbol: payload.gene,
        variant_name: variant.variant,
        evidence_levels: variant.best_level ? [variant.best_level] : [],
        evidence_count: variant.evidence_count || 0,
        total_variants: payload.total_variants,
      }));
    }

    case "variant_response_query": {
      return payload.results.map((result) => ({
        variant_name: payload.variant,
        therapy_name: payload.therapy,
        disease_name: result.disease || null,
        effect: result.effect,
        evidence_levels: result.best_level ? [result.best_level] : [],
        evidence_count: result.evidence_count || 0,
      }));
    }

    case "gene_overview_query": {
      // Summary stats only, no relationships to visualize
      return [];
    }

    case "therapy_overview_query": {
      return payload.targets.map((target) => ({
        therapy_name: payload.therapy,
        gene_symbol: target.gene,
        targets_moa: target.moa || null,
        relationship: "TARGETS",
        target_count: payload.target_count,
        biomarker_count: payload.biomarker_count,
      }));
    }

    case "disease_biomarkers_query": {
      return payload.top_genes.map((gene) => ({
        gene_symbol: gene.gene,
        disease_name: payload.disease,
        evidence_levels: gene.best_level ? [gene.best_level] : [],
        evidence_count: gene.evidence_count || 0,
        total_genes: payload.total_genes,
        // Note: No therapy or effect - these are disease-level biomarkers
        // MiniGraph will show disease → gene nodes (no AFFECTS_RESPONSE_TO edges)
      }));
    }

    case "disease_therapies_query": {
      // Therapy list with counts only, no relationships to visualize
      return [];
    }

    default:
      // TypeScript exhaustiveness check
      const _exhaustive: never = payload;
      return [];
  }
}

