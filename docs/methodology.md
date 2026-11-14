# Methodology

Version: harmonization **A-0.1**. Design background and alternatives considered are in
[analysis/MODIS_VIIRS_HARMONIZATION_DESIGN.md](analysis/MODIS_VIIRS_HARMONIZATION_DESIGN.md).

## 1. The problem

MODIS (Terra, Aqua; ~1 km pixels) and VIIRS (Suomi-NPP, NOAA-20, NOAA-21; 375 m pixels) detect thermal anomalies with
different resolution, sensitivity, overpass times, viewing geometry, algorithms and confidence scales. On a probe week of real
Ghana data (2024-01-10 to 16) VIIRS Suomi-NPP reported about 4.7 times more detections than MODIS (Terra and Aqua combined).
Adding raw counts would mix a change in instrument with a change in fire.

## 2. Pipeline

1. **Acquire.** FIRMS standard-processing products (`MODIS_SP`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_SP`) over the
   Ghana bounding box, in 5-day windows, 2012-2025. Raw CSVs are never modified.
2. **Validate and clean** (`process.py`). Required fields, coordinate ranges, UTC timestamp (`acq_date` + HHMM `acq_time`), and
   removal of *exact* duplicates only. Every exclusion is logged with a reason. Original `confidence`, `type`, `frp` are kept.
3. **Derived fields.** `platform` (Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21); `confidence_class` (low/nominal/high) **within each
   product** (MODIS 0-29 / 30-79 / 80-100; VIIRS l/n/h) - the classes are not calibrated to each other; and
   `is_presumed_vegetation_fire` from the FIRMS `type` code.
4. **Clip to Ghana** (`regions.py`) using the union of geoBoundaries ADM1 polygons, and assign each grid cell to one of 16 regions
   (centre point; nearest region if on a border gap).
5. **Common grid and UTC day** (`harmonize.py`). An equirectangular grid of 1, 2 or 5 km cells (cell sizes are a sensitivity
   analysis, not an assumption of equivalence). Each detection is assigned to a cell and a UTC date.
6. **Harmonized index: active cell-days.** A (UTC day, cell) pair counts once if at least one selected sensor detected activity
   there. Detections seen by both sensors are not double counted. Per-sensor detection counts and cell-days are kept alongside it,
   with the share seen by both sensors as an agreement measure. No event-linking or "unique fire" claim is made.
7. **Constant constellation.** The default series uses Terra, Aqua and Suomi-NPP only, because NOAA-20 (2018) and NOAA-21 (2023)
   add overpasses that would raise counts without any change in fire. They can be included with `--all-platforms`.
8. **Monthly coverage.** A month is *complete* when the downloaded archive covers the whole month for every selected product that
   existed by then. A day with no detections is **not** treated as missing data, because quiet seasons legitimately have such days.
   Regions inherit the national coverage flag.

## 3. Historical comparison and unusual activity (`calendar_analytics.py`)

For each region and calendar month, a month's value is compared with the **same calendar month in other years** (leave-one-out),
using complete months only:

- baseline = median and MAD of the other years;
- robust score = (value - median) / (1.4826 x MAD);
- flagged "unusually high/low" when |score| >= 3.5 (the conventional modified z-score cut-off) **and** at least 5 other complete
  years exist;
- if the baseline has no spread (MAD = 0) no score is invented: the month is labelled above/below a flat baseline and not flagged;
- every row carries the baseline sample size, percentage and absolute difference, a reliability flag and a text explanation.

This describes unusual *historical* activity. It is not a forecast, an alert or a validated classifier; no ground-truth labels
exist, so no accuracy, precision or recall is reported.

## 4. Validation performed

- Unit tests for grid assignment, UTC day assignment, double-count avoidance, per-sensor preservation, filters, coverage rules,
  baselines, flat-baseline handling, region assignment and API contracts.
- A regression test that failed under the earlier per-region coverage rule (which mislabelled quiet regions as missing data).
- Comparison of raw VIIRS/MODIS ratios against cell-day ratios and sensor agreement at 1, 2 and 5 km, shown on the
  *Sensor harmonization* page.

## 5. What the harmonization does not do

See [limitations.md](limitations.md). In short: it does not make the sensors equivalent, count fires, calibrate FRP or
confidence across sensors, or model observation opportunity (cloud, overpass time, Terra's orbital drift).
