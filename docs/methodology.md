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
   Regions and custom areas inherit the national coverage flag. A month in which an area has no detections is a **zero**, not a gap,
   and is part of that area's baseline and calendar (an earlier version silently dropped such months, which biased quiet regions'
   baselines upward; fixed and covered by tests).

### Sensor views and custom areas

The dashboard can show the harmonized index (either sensor), MODIS only or VIIRS only. A single-sensor view re-runs the same
calendar and baseline analysis on that sensor's cell-days and uses that sensor's own archive coverage. Flagged months report
whether each sensor *alone* also finds the month unusual, as corroboration. Any region or user-drawn bounding box (cells assigned
by cell centre) can be analysed the same way, on demand. Daily and weekly series count active cell-days per day, or per day
within the week.

## 3. Historical comparison and unusual activity (`calendar_analytics.py`)

For each region and calendar month, a month's value is compared with the **same calendar month in other years** (leave-one-out),
using complete months only:

- baseline = median and MAD of the other years (shown in cell-days);
- robust score = (log1p(value) - median of log1p(others)) / (1.4826 x MAD of log1p(others)); the log scale is used because activity
  is right-skewed and varies multiplicatively;
- flagged "unusually high/low" when |score| exceeds a threshold **calibrated to the baseline size** (see below) **and** at least 5
  other complete years exist;
- if the baseline has no spread (MAD = 0) no score is invented: the month is labelled above/below a flat baseline and not flagged;
- every row carries the baseline sample size, percentage and absolute difference, a reliability flag and a text explanation.

This describes unusual *historical* activity. It is not a forecast, an alert or a validated classifier; no ground-truth labels
exist, so no accuracy, precision or recall is reported.

### Why the threshold is calibrated

The usual "modified z-score above 3.5" rule assumes a large sample. With the 5-13 other years available per calendar month, median/MAD
scores have heavy tails. Simulation (`data_pipeline/calibration.py`, tested) shows that a fixed 3.5 falsely flags ordinary months
about **2.4%** of the time with 13 baseline years, **6.9%** with 7 and **12%** with 5 (more for skewed data), so most flags under that
rule could be chance. TerraGuard instead uses, for each baseline size, the threshold at which ordinary (Gaussian, on the log scale)
months are falsely flagged about **1%** of the time: 14.3 for 5 baseline years, 7.8 for 7, 4.4 for 13, 3.5 for 20. Short baselines
therefore need very large changes before anything is called unusual. This calibration assumes Gaussian noise on the log scale;
real series can have heavier tails, so the realised false-flag rate can be higher. On the full 2012-2025 data the calibrated rule
flags 32 of 2,782 scored region-months (1.15%), compared with 118 (4.2%) under the fixed rule. Nationally one month survives:
December 2025 (-56%), flagged in both sensors independently. Many of the regional flags are the same December 2025 event seen in
10 of the 17 areas (Ghana as a whole plus 9 regions), so the number of independent findings is smaller than the number of flags (22 of the 32 flags are outside December 2025).

### Baseline versus Isolation Forest

`python -m data_pipeline.model_comparison` (also part of `run_all`) compares the baseline with Isolation Forest, fitted on 2012-2019 and
applied unchanged to 2020-2025 for all 17 areas (1,224 held-out months). With no ground-truth labels, it reports agreement, how
often each method flags ordinary held-out months, and a clearly labelled **synthetic** sensitivity test that scales real months up
or down one at a time. Because each method ships with a different alarm threshold, ranking power is compared threshold-free (AUC):

| Change applied to a real month | Baseline | Isolation Forest (raw) | Isolation Forest (deseasonalised) |
|---|---|---|---|
| tripled | 0.82 | 0.83 | 0.84 |
| doubled | 0.70 | 0.72 | 0.70 |
| cut to a third | 0.85 | 0.72 | 0.88 |

Isolation Forest brings no clear ranking advantage (within 0.03 AUC of the baseline wherever it is not worse), flags 5-11% of ordinary
held-out months against 2.4% for the baseline, and cannot say why it flagged a month. The explainable baseline therefore remains the
primary method. The two methods agree on December 2025 and otherwise overlap little (Jaccard 0.09 nationally).

## 4. Validation performed

Run `python -m data_pipeline.validation` (also part of `run_all`); results are in `data/processed/analytics/validation.json` and on
the *Sensor harmonization* page. On the full 2012-2025 Ghana series (167 complete months, national):

| Measure | Raw detections | Active cell-days (5 km) |
|---|---|---|
| Rank correlation MODIS vs VIIRS, raw series | 0.98 | 0.98 |
| Rank correlation, **deseasonalised** (shared year-to-year change) | 0.77 | 0.76 |
| Mean VIIRS / MODIS ratio | 10.8 | 9.2 |
| Variability of that ratio (CV) | 1.07 | 1.04 |

Reading: the two sensors share real year-to-year signal (deseasonalised correlation about 0.77), but converting to cell-days does
**not** measurably improve their mutual consistency, and the VIIRS/MODIS ratio is far from constant, so a single calibration
factor is not justified. The benefit of cell-days is conceptual (no pixel-size inflation, no double counting of co-detections),
not an empirical gain in agreement. The share of cell-days seen by both sensors is small: 8% of all cell-days at 1 km, 13% at
2 km and 17% at 5 km (activity-weighted), and about 2-8% in a typical month.

Other checks:

- Unit tests for grid assignment, UTC day assignment, double-count avoidance, per-sensor preservation, filters, coverage rules,
  baselines, flat-baseline handling, region assignment, validation statistics and API contracts.
- Regression tests for two coverage-rule bugs found on real data (per-region coverage mislabelled quiet regions; a days-with-records
  rule would have excluded every rainy season).
- Orbit drift (daytime detections, median UTC hour): Terra 10.7 h (2019) to 9.6 h (2025), Aqua 13.6 h to 14.7 h (all months); Suomi-NPP, NOAA-20
  and NOAA-21 stay near 13.4-13.5 h.
- December 2025 is flagged nationally as unusually low. All five platforms (including the independent NOAA-20 and NOAA-21) fall by
  roughly 58-75% against December 2024, with data present on all 31 days, so it is not a single-sensor or orbit artefact. The data
  alone cannot say whether burning really fell or a shared processing effect exists.

## 5. What the harmonization does not do

See [limitations.md](limitations.md). In short: it does not make the sensors equivalent, count fires, calibrate FRP or
confidence across sensors, or model observation opportunity (cloud, overpass time, Terra's orbital drift).
