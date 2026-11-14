export type Grid = "1km" | "2km" | "5km";

export type Status =
  | "typical"
  | "unusually_high"
  | "unusually_low"
  | "incomplete_coverage"
  | "insufficient_baseline"
  | "above_flat_baseline"
  | "below_flat_baseline";

export type Sensor = "harmonized" | "modis" | "viirs";

/** Which data the whole app is looking at: grid, named region or custom box, and sensor view. */
export interface AreaQuery {
  grid: Grid;
  region: string;
  bbox: string | null; // "west,south,east,north" when a custom area is active (overrides region)
  sensor: Sensor;
}

export interface Period {
  start: string; // YYYY-MM-DD
  end: string;
}

export interface SeriesRow {
  period_start: string;
  period_end: string;
  value: number;
  harmonized_cell_days: number;
  modis_cell_days: number;
  viirs_cell_days: number;
  both_cell_days: number;
  modis_detections: number;
  viirs_detections: number;
}

export interface Quality {
  products: Record<string, {
    source_files?: number;
    loaded_records?: number;
    retained_records?: number;
    exclusions_by_reason?: Record<string, number>;
    missing_values?: Record<string, number>;
    earliest_observation?: string;
    latest_observation?: string;
    covered_ranges?: string[][];
    non_vegetation_type_records?: number;
  }>;
  records_by_platform: Record<string, number>;
  harmonization: {
    observations_used: number | null;
    observations_outside_ghana_excluded: number | null;
    platforms: string[] | string | null;
    coverage_rule: string | null;
    spatial_clip: string | null;
  };
  coverage: { months_total: number; months_complete: number; incomplete_months: string[] };
}

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
  view?: Sensor;
  modis_status?: Status | null;
  viirs_status?: Status | null;
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

export type Method = "stat" | "if_raw" | "if_deseason";
export type Factor = "x3" | "x2" | "div3";

export interface AreaComparison {
  train_months: number;
  test_months: number;
  flags: Record<Method, string[]>;
  flag_counts: Record<Method, number>;
  unscorable_by_stat: number;
  jaccard_stat_vs_if_raw: number | null;
  jaccard_stat_vs_if_deseason: number | null;
  spearman_abs_stat_vs_if: Record<string, number | null>;
}

export interface MethodComparison {
  protocol: Record<string, unknown>;
  areas: Record<string, AreaComparison>;
  pooled: {
    areas: number;
    test_months: number;
    flag_rate_on_heldout_months: Record<Method, number | null>;
    synthetic_injection: {
      months_per_factor: number;
      stat_scorable_share: number | null;
      detection_rate: Record<Factor, Record<Method, number | null>>;
      auc: Record<Factor, Record<Method, number | null>>;
    };
  };
  notes: string[];
}
