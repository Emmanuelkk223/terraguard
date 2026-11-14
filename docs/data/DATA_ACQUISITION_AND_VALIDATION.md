# TerraGuard data acquisition and validation

## Current execution status

Authenticated acquisition and processing have now been executed successfully.
The acquisition command was previously never run because the MAP_KEY and
boundary were absent. After the key was configured securely, 48 real dated
FIRMS requests completed for VIIRS Suomi-NPP standard processing.

Actual results:

- Raw CSV files: 48.
- Raw source records: 134,230.
- Valid before geographic filtering: 134,230.
- Retained within Ghana: 109,229.
- Excluded outside Ghana boundary: 25,001.
- Invalid or duplicate exclusions: 0 in this sample.
- Coverage: 2021-01-01 through 2024-12-05.
- Sensor/product: VIIRS / Suomi-NPP / `VIIRS_SNPP_SP`.
- Confidence: 109,229 non-null values (`n` 83,739; `l` 19,897; `h` 5,593).
- FRP: 109,229 non-null values; median 4.89, mean 7.502, maximum 283.46.

This is a seasonal sample of January–December 1–5 windows, not continuous
four-year coverage. The observed date span must not be described as complete
historical coverage.

## Official sources and authentication

Use only:

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- [FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/)
- [FIRMS download service](https://firms.modaps.eosdis.nasa.gov/download/)
- [NASA Earthdata](https://www.earthdata.nasa.gov/)

Set a FIRMS MAP_KEY obtained through the supported NASA Earthdata/FIRMS
registration process. Never put the key in source control or command history
that will be shared:

```powershell
$env:FIRMS_MAP_KEY = "<your FIRMS MAP_KEY>"
```

The repository's [.env.example](../../.env.example) contains only the
placeholder `FIRMS_MAP_KEY=`.

## Products and historical availability

The intended investigation includes MODIS, VIIRS Suomi-NPP, VIIRS NOAA-20, and
VIIRS NOAA-21 where the official service provides coverage. Product identity
must remain in every raw and processed output. The currently documented FIRMS
availability includes MODIS C6.1 from 2000/2002 depending on Terra/Aqua,
VIIRS 375 m Suomi-NPP from April 2018, and VIIRS NOAA-21 from January 2024;
actual selected date coverage must be read from downloaded files and official
product metadata. This milestone acquired only `VIIRS_SNPP_SP`; MODIS,
NOAA-20, and NOAA-21 were not acquired.

The FIRMS area API supports recent-day requests, not arbitrary historical
date ranges. Use:

```powershell
python -m data_pipeline.acquire --source VIIRS_SNPP_NRT --days 5
```

For dated standard-processing windows, the same endpoint accepts an optional
date segment. For example:

```powershell
python -m data_pipeline.acquire --source VIIRS_SNPP_SP `
  --start 2024-01-01 --end 2024-01-05 --days 5
```

For very large multi-year acquisitions, the official FIRMS Archive Download
workflow may be more practical. Place archive files in `data/raw/` without
renaming away their provenance. Do not treat repeated recent snapshots as
historical coverage.

For a given source and recent-day window, the acquisition command reuses the
latest matching raw snapshot already in `data/raw/` instead of downloading
another duplicate. Historical archive files remain identifiable by their
original source filenames.

## Data locations and schema

```text
data/raw/                  original FIRMS CSV/archive files
data/processed/            validated observations and summaries
data/processed/analysis/   historical temporal/spatial/baseline outputs
data/processed/anomalies/  anomaly candidates and experiment metadata
```

The common processed fields include:

- `latitude`, `longitude` in WGS84 (`EPSG:4326`)
- `acq_date`, `acq_time`, and parsed `acq_datetime`
- `sensor`, `satellite`, `instrument`
- `confidence` and `frp` where provided by the product
- `source_product` and `source_file`

Original source columns are retained. `observation_count` in derived outputs
counts satellite detection records, not unique physical fires.

## Geographic filtering and quality checks

The processing command uses a Ghana ADM0 boundary extracted from Natural Earth
10m Admin-0 Countries:
`https://github.com/nvkelso/natural-earth-vector`. The extracted file is
`data/raw/ghana_boundary.geojson`, used in WGS84 (`EPSG:4326`). It first
applies the documented Ghana bounding box and then performs point-in-polygon
filtering. The raw Natural Earth source is preserved locally as
`data/raw/natural_earth_admin0.geojson` and both are Git-ignored.

Validation checks:

- Required FIRMS date/time and coordinate fields.
- Coordinate ranges.
- Parseable acquisition timestamps.
- Exact duplicate detection by location/time/satellite/instrument/product.
- Exclusion reasons in `exclusions.csv`.
- Sensor/product identity preservation.
- Missing optional confidence and FRP fields without silent row removal.

## Reproduction workflow

After configuring a MAP_KEY and obtaining a documented Ghana boundary:

```powershell
python -m pip install -r data_pipeline\requirements.txt
python -m data_pipeline.acquire --source VIIRS_SNPP_NRT --days 10

python -m data_pipeline.process --input-dir data/raw `
  --boundary path\to\ghana_boundary.geojson `
  --product VIIRS_SNPP_NRT
python -m data_pipeline.analyze
python -m data_pipeline.historical `
  --observations data/processed/observations.csv `
  --output-dir data/processed/analysis
python -m pip install -r ml\requirements.txt
python -m ml.anomaly `
  --activity data/processed/analysis/historical_week.csv `
  --output-dir data/processed/anomalies
python -m pytest -q
```

For archive files, repeat only the processing and analysis commands after
placing the files in `data/raw/`. The pipeline writes raw-derived counts and
coverage to `metadata.json`, historical metadata, and anomaly metadata.

Generated real-data outputs for this run include:

- `data/processed/observations.csv`
- `data/processed/exclusions.csv`
- Daily, weekly, and monthly summaries
- `data/processed/analysis/historical_spatial.csv`
- `data/processed/analysis/seasonal_baseline.csv`
- `data/processed/anomalies/anomaly_candidates.csv`

## Known blockers and limitations

1. A valid FIRMS MAP_KEY is required for authenticated downloads.
2. The area API is unsuitable for multi-year historical acquisition.
3. A verified Ghana boundary GeoJSON is required for the current processor.
4. No real-data temporal, baseline, or anomaly statistics can be claimed
   until archive/recent files are actually processed.
5. Raw data is intentionally ignored by Git; large source files must remain
   outside commits unless the team approves a storage strategy.
