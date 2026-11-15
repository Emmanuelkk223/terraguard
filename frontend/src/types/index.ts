export type Grid = "1km" | "2km" | "5km";

export type Status =
  | "typical"
  | "unusually_high"
  | "unusually_low"
  | "incomplete_coverage"
  | "insufficient_baseline"
  | "above_flat_baseline"
  | "below_flat_baseline";

export interface Place {
  id: number;
  name: string;
  kind: "city" | "town" | "place" | "region" | "country";
  admin1: string | null;
  country: string;
  country_code: string;
  lat: number;
  lon: number;
  covered: boolean; // TerraGuard has fire data for this place
  region: string | null; // the Ghana region TerraGuard analyses, for places in Ghana
  bbox?: [number, number, number, number]; // countries and regions
}

export type Sensor = "harmonized" | "steady" | "modis" | "viirs";

export interface AreaOption {
  name: string;
  grids: string[];
  bbox?: [number, number, number, number] | null;
}

export interface AreaGroup {
  label: string;
  areas: AreaOption[];
}

export interface AreaList {
  default: string;
  west_africa_available: boolean;
  groups: AreaGroup[];
}

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
  steady_cell_days?: number;
  scored_cell_days?: number;
  viirs_steady_detections?: number;
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
  /** True when VIIRS did not exist yet and the value is MODIS expressed on the combined scale. */
  estimated?: boolean;
  series_basis?: "combined" | "modis_scaled" | "single_sensor";
  observed_cell_days?: number;
  estimate_low?: number;
  estimate_high?: number;
  limited_reason?: "" | "terra_only";
  baseline_estimated_n?: number;
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

export interface SensitivityScenario {
  group: string;
  label: string;
  complete_months: number;
  total_active_cell_days: number;
  share_seen_by_both_sensors: number | null;
  viirs_to_modis_cell_day_ratio: number | null;
  burning_season: { months: number[]; label: string; peak_month: number; share_of_year: number } | null;
  flagged_months: string[];
  correlation_with_default: number | null;
  correlation_with_default_deseasonalised: number | null;
}

export interface SensitivityReport {
  scenarios: Record<string, SensitivityScenario>;
  default_flagged_months: string[];
  notes: string[];
}

export interface RainRow {
  region: string;
  year: number;
  month: number;
  rainfall_mm_per_day: number;
  rainfall_mm: number;
  rain_percentile: number;
  rain_median_mm_per_day: number;
}

export interface RainAssociation {
  source: string;
  retrieved: string;
  association: Record<string, Record<string, { spearman: number | null; n: number }>>;
  notes: string[];
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

export interface HotspotPreview {
  rows: number;
  limit: number;
  too_large: boolean;
  by_sensor: Record<string, number>;
}

export interface CurrentWindow {
  year: number;
  value: number;
  estimated: boolean;
  all_satellites_value?: number;
  window_start: string;
  window_end: string;
}

export interface CurrentComparison {
  as_of: string;
  window_days: number;
  mode?: "days" | "month";
  window_label?: string | null;
  basis?: string;
  area: string;
  sensor: Sensor;
  grid: string;
  current: CurrentWindow;
  history: CurrentWindow[];
  median: number;
  pct_diff_from_median: number | null;
  rank_among_years: number;
  years_compared: number;
  percentile: number;
  note: string;
}

export interface BridgeBacktest {
  fit_years: string;
  test_years: string;
  test_months: number;
  median_absolute_error_pct: number;
  median_bias_pct: number;
  mean_absolute_log_error: number;
  range_90_coverage: number;
}

export interface BridgeValidation {
  method: string;
  backtests: BridgeBacktest[];
}
