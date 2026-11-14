# Historical analysis and statistical baselines

## Status and evidence

The reusable analysis implementation is in
`data_pipeline/historical.py`. A real-data run is now available:

- Source: `VIIRS_SNPP_SP` (VIIRS Suomi-NPP standard processing).
- Raw records: 134,230 across 48 five-day monthly windows.
- Ghana-retained observations: 109,229.
- Observed date span: 2021-01-01 through 2024-12-05.
- Sensor: VIIRS only.
- Cell-specific baseline candidate count: 1,744.

The sample is not continuous coverage: only the first five days of each month
were acquired. Empty weeks therefore represent unacquired windows and must not
be interpreted as zero fire activity.

The tests use explicitly synthetic fixtures to verify calculations only. They
are not TerraGuard observations.

## Data sources and coverage

Milestone 1 is designed to use CSV observations from the official NASA FIRMS
area/archive services. Each processed row retains `source_product`,
`source_file`, `sensor`, `satellite`/`instrument` when supplied, original
coordinates, acquisition date/time, confidence, and FRP where supplied.

The current acquisition method requires `FIRMS_MAP_KEY`. The recent area API
does not replace the need to obtain older standard-quality historical data
through the official FIRMS archive service. Product availability and actual
coverage must be read from the downloaded files and metadata; planned
availability is not treated as observed coverage.

## Temporal aggregation

`temporal_activity()` creates daily, weekly, or monthly summaries. The
supported period definitions are:

- Day: UTC acquisition date.
- Week: Monday-start periods represented by the week containing Sunday.
- Month: calendar month start.

`observation_count` is the number of source satellite detection records. It is
not a count of unique physical fires. Rows remain separated by `sensor`.
FRP sum and mean are calculated only from non-null FRP values; a missing-period
FRP sum is zero while its mean remains missing.

When `include_empty_periods=True`, the function emits every period between the
earliest and latest valid timestamp for each sensor. Empty periods have
`observation_count=0` and `has_observations=False`. This distinguishes an
observed zero-count period in the constructed analysis range from a period
outside the dataset's temporal coverage. It does not prove that no fire
occurred.

## Spatial aggregation

`spatial_activity()` uses the Milestone 1 nominal 5 km equirectangular grid
configuration and keeps sensor rows separate. Coordinates remain WGS84
longitude/latitude (`EPSG:4326`) in the observation dataset. The grid is an
analysis index, not an equal-area or administrative boundary. A nearby pair of
observations is not treated as one physical fire.

Administrative summaries are intentionally not produced. The verified
Natural Earth Ghana ADM0 boundary was used for country filtering, but no
administrative subdivision dataset was selected.

## Baseline methodology

The baseline is seasonal, sensor-specific, and cell-specific when the weekly
analysis is run with `cell_size_km`.

For a target period \(t\), let \(G(t)\) contain other periods with the same
sensor, grid cell (when available), and calendar month. The target period is
excluded to avoid using its own value in its baseline:

\[
m_t = \operatorname{median}(G(t))
\]

\[
MAD_t = \operatorname{median}(|x - m_t| : x \in G(t))
\]

For positive MAD:

\[
z_t = \frac{x_t - m_t}{1.4826 \times MAD_t}
\]

The default candidate threshold is `z_t >= 3.5`, and only unusually high
activity is flagged. The robust scale factor makes MAD comparable to standard
deviation under a normal reference distribution; it does not make the
observations normally distributed.

If MAD is zero, a target is assigned an infinite score only when it is greater
than the peer median; otherwise its score is zero. A baseline is ineligible
unless at least three other comparable periods are available by default.
Ineligible rows have no defensible anomaly decision and are not flagged.
Threshold and minimum-sample values are configuration, not validated truths.

## Missing data and limitations

The analysis cannot distinguish all causes of absent detections. Cloud,
observation timing, product differences, fire characteristics, processing
gaps, and missing source files may all affect coverage. Empty periods are
therefore labeled as zero observed records, not as evidence of no fire.

MODIS and VIIRS have different spatial, temporal, and detection properties.
Their observation counts are never silently combined in the analysis tables.
Comparisons must include sensor identity and sufficient coverage.

The leave-one-out baseline reduces direct in-sample leakage but does not solve
all temporal dependence or source-coverage issues. A candidate unusual period
is unusual relative to this method and comparison group; it is not a confirmed
fire, emergency alert, or prediction.

## Reproduction

From the repository root, after obtaining genuine FIRMS files and a documented
Ghana boundary:

```powershell
python -m data_pipeline.process --input-dir data/raw `
  --boundary path\to\ghana_boundary.geojson `
  --product VIIRS_SNPP_NRT
python -m data_pipeline.historical `
  --observations data/processed/observations.csv `
  --output-dir data/processed/analysis
python -m pytest -q
```

The analysis writes:

- `historical_day.csv`, `historical_week.csv`, `historical_month.csv`
- `historical_spatial.csv`
- `seasonal_baseline.csv`
- `historical_analysis_metadata.json`

These are derived outputs and must remain separate from raw FIRMS files.

## Future work

After real multi-year coverage is acquired, inspect seasonal sample sizes,
coverage gaps, sensor comparability, grid sensitivity, and candidate rows
before exposing results through the backend. Isolation Forest and other
complex models are deliberately deferred until this statistical reference has
been reviewed.

The current real-data run confirms that processing and baseline generation
execute, but the sparse monthly-window design limits conclusions about
continuous weekly activity and should be expanded with complete archive
coverage before scientific or product claims are made.
