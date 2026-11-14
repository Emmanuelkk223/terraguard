export type Grid = "1km" | "2km" | "5km";

export type Status =
  | "typical"
  | "unusually_high"
  | "unusually_low"
  | "incomplete_coverage"
  | "insufficient_baseline"
  | "above_flat_baseline"
  | "below_flat_baseline";

export interface CalRow {
  region: string;
  year: number;
  month: number;
  month_start: string;
  active_cell_days: number;
  modis_cell_days: number;
  viirs_cell_days: number;
  both_cell_days: number;
  modis_detections: number;
  viirs_detections: number;
  coverage_ok: boolean;
  baseline_n: number;
  baseline_median: number | null;
  baseline_mad: number | null;
  abs_diff: number | null;
  pct_diff: number | null;
  robust_score: number | null;
  threshold: number;
  status: Status;
  reliable: boolean;
  explanation: string;
}

export interface SeasonalRow {
  region: string;
  month: number;
  n_years: number;
  median: number;
  mean: number;
  min: number;
  min_year: number;
  max: number;
  max_year: number;
}

export interface AnnualRow {
  region: string;
  year: number;
  active_cell_days: number;
  months_with_coverage: number;
  modis_cell_days: number;
  viirs_cell_days: number;
  complete_year: boolean;
}

export interface CellFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    active_days: number;
    modis_detections: number;
    viirs_detections: number;
    days_both: number;
  };
}

export interface CellCollection {
  type: "FeatureCollection";
  features: CellFeature[];
  truncated: boolean;
  note: string;
}

export interface Selection {
  year: number;
  month: number;
}

export interface HarmonizationMeta {
  harmonization: {
    harmonization_method: string;
    harmonization_version: string;
    platforms: string[] | string;
    min_coverage: number;
    min_confidence: string | null;
    vegetation_only: boolean;
    observations_used: number;
    observations_outside_ghana_excluded: number;
    spatial_clip: string;
    grids: Record<string, { cell_days: number; overall_agreement_jaccard: number | null }>;
    notes: string[];
  };
  analytics?: { grid: string; flagged: number; rows: number; threshold: number; min_baseline_years: number }[];
}

export interface SeriesValidation {
  spearman_raw_series: number | null;
  spearman_deseasonalised: number | null;
  ratio_viirs_over_modis_mean: number;
  ratio_cv: number | null;
}

export interface GridValidation {
  months: number;
  raw_detections: SeriesValidation;
  cell_days: SeriesValidation;
  agreement_share_both_by_year: Record<string, number>;
}

export interface Validation {
  grids: Record<string, GridValidation>;
  overpass_hour_by_year?: Record<string, Record<string, number>>;
}
