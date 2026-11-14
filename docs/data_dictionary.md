# Data dictionary

## Processed observations - `data/processed/observations/<product>.parquet`
One row per validated FIRMS detection. Original FIRMS columns are kept; these are added or normalised.

| Column | Meaning |
|---|---|
| `acq_datetime` | UTC timestamp from `acq_date` + HHMM `acq_time` (timezone-naive, UTC) |
| `sensor` | `MODIS` or `VIIRS` |
| `platform` | Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21 (from FIRMS `satellite`: Terra, Aqua, N, N20, N21) |
| `source_product`, `source_file` | Provenance of the row |
| `confidence` | Original FIRMS value as text (MODIS 0-100; VIIRS l/n/h) |
| `confidence_class` | low/nominal/high within the product (MODIS <30, 30-79, >=80); not comparable across sensors |
| `type` | Original FIRMS type (0 presumed vegetation fire, 2 other static land source, 3 offshore) |
| `is_presumed_vegetation_fire` | True for type 0, False for other types, missing if unknown |
| `frp` | Fire radiative power, MW (not a count; not calibrated across sensors) |

## Harmonized cell-days - `data/processed/harmonized/cell_days_<grid>.parquet`
| Column | Meaning |
|---|---|
| `date` | UTC day |
| `grid_x`, `grid_y` | Integer cell indices of the regular grid (cell centre via `cell_centres`) |
| `modis_detections`, `viirs_detections` | Detections of each sensor in this cell-day |
| `occupied_by` | `both`, `MODIS_only`, `VIIRS_only` |
| `region` | Ghana region of the cell centre |

## Monthly series - `data/processed/harmonized/monthly_<grid>.csv`
One row per region (and `Ghana`) per month.

| Column | Meaning |
|---|---|
| `active_cell_days` | Harmonized index: cell-days with a detection from either sensor |
| `modis_cell_days`, `viirs_cell_days`, `both_cell_days` | Cell-days seen by each sensor / both |
| `modis_detections`, `viirs_detections` | Raw detection counts (kept separate) |
| `agreement_jaccard` | `both_cell_days / active_cell_days` |
| `raw_viirs_to_modis_ratio`, `cell_day_viirs_to_modis_ratio` | Sensor ratios before / after aggregation |
| `modis_archive_ok`, `viirs_archive_ok` | Archive covers the whole month for the selected products |
| `coverage_ok` | Both archives complete; incomplete months are excluded from baselines |
| `modis_days_with_records`, `viirs_days_with_records`, `days_in_month` | Diagnostics only |

## Calendar analytics - `data/processed/analytics/`
`calendar_<grid>.csv` adds, per region-month: `baseline_n`, `baseline_median`, `baseline_mad`, `abs_diff`, `pct_diff`,
`robust_score`, `threshold`, `status`, `reliable`, `explanation`. `status` is one of `typical`, `unusually_high`, `unusually_low`,
`incomplete_coverage`, `insufficient_baseline`, `above_flat_baseline`, `below_flat_baseline`.
`annual_<grid>.csv` (with `complete_year`), `seasonal_<grid>.csv` (median, mean, min/max and their years across complete years),
and `anomalies_<grid>.csv` (flagged rows only).

## Rainfall context - `data/processed/environment/`
`rainfall_monthly.csv` (NASA POWER PRECTOTCORR; raw responses are kept unchanged in `data/raw/environment/`)

| Column | Meaning |
|---|---|
| `region` | Ghana (area-weighted mean of the regions) or one of the 16 regions |
| `year`, `month`, `days` | The calendar month |
| `rainfall_mm_per_day`, `rainfall_mm` | Monthly mean rate and the month total |
| `rain_percentile` | Rank of this month among the same calendar month in all years (1.0 = wettest) |
| `rain_median_mm_per_day` | Typical rate for that calendar month |

`rainfall_association.json`: rank correlations of burning and rainfall anomalies per area at lags 0-3 and for the previous three months,
each with its number of paired months, plus the sample points, source, retrieval date and caveats.

## Other analytics outputs - `data/processed/analytics/`
- `model_comparison.json`: baseline versus Isolation Forest (held-out flags, agreement, synthetic sensitivity with AUC).
- `sensitivity.json`: national summary of each sensitivity scenario (series correlation, sensor agreement, season, flagged months).
- `validation.json`: sensor agreement statistics and overpass-time drift.

## Place gazetteer - `data/reference/west_africa_places.parquet`
One row per populated place, region or country (GeoNames, CC BY 4.0; see `data/reference/ATTRIBUTION.md`).

| Column | Meaning |
|---|---|
| `id`, `name`, `kind` | GeoNames id (negative for countries and regions), display name, `city` / `town` / `place` / `region` / `country` |
| `norm`, `alt_norm` | Accent-folded, lower-case name and alternate names used for matching |
| `admin1`, `country`, `country_code` | First-level region (as GeoNames names it), country and ISO code |
| `lat`, `lon`, `population`, `feature_code` | Coordinates; population (mostly 0 = unknown); GeoNames feature code |
| `seat_rank` | Administrative importance: capital 4, regional seat 3, district seats 2 and 1, other 0 (countries and regions 5) |
| `ghana_region` | For Ghana: which of TerraGuard's 16 regions the place falls in |
| `west`, `south`, `east`, `north` | Bounding box for countries and Ghana regions |
