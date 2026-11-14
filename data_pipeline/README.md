# TerraGuard data foundation

This package downloads and processes genuine NASA FIRMS CSV observations. It
does not generate observations and it does not infer unique fires.

## Data products and access

Install the data-pipeline dependency from the repository root:

```powershell
python -m pip install -r data_pipeline\requirements.txt
```

FIRMS documents MODIS C6.1 from November 2000 (Terra) and July 2002 (Aqua),
VIIRS 375 m Suomi-NPP from 1 April 2018, and VIIRS 375 m NOAA-21 from
17 January 2024 onward. NOAA-20 and other product availability must be checked
against the current FIRMS documentation before acquisition.

The acquisition command uses the official FIRMS area API, which requires a
FIRMS `MAP_KEY` associated with NASA Earthdata access. The area API accepts a
number of recent days (at most five); it does not accept arbitrary historical
start/end dates. Historical standard-quality data older than the recent API
window must be obtained through the official FIRMS Archive Download service;
this repository does not guess an archive URL or bypass its authentication
requirements.

Set the key only in the process environment:

```powershell
$env:FIRMS_MAP_KEY = "<your FIRMS MAP_KEY>"
python -m data_pipeline.acquire --source VIIRS_SNPP_NRT --days 5
```

The downloaded filename includes the retrieval timestamp. Existing raw files
are preserved; historical archive files should likewise retain their original
names and source metadata.

For dated standard-processing windows supported by the API:

```powershell
python -m data_pipeline.acquire --source VIIRS_SNPP_SP `
  --start 2024-01-01 --end 2024-01-05 --days 5
```

The default area is the Ghana bounding box
`(-3.26, 4.74, 1.20, 11.17)` in WGS84 longitude/latitude order. A bounding-box
download is not treated as Ghana data until the processing step applies a
Ghana boundary GeoJSON.

## Processing

Provide a GeoJSON Polygon or MultiPolygon boundary sourced from a documented
Ghana administrative-boundary dataset:

```powershell
python -m data_pipeline.process --input-dir data/raw `
  --boundary path\to\ghana_boundary.geojson `
  --product VIIRS_SNPP_NRT
```

The processor writes:

- `observations.csv`: validated original observations with common fields and
  preserved source columns.
- `exclusions.csv`: every excluded row and its reason.
- `summary_day.csv`, `summary_week.csv`, `summary_month.csv`: sensor-specific
  observation and FRP summaries.
- `metadata.json`: provenance, counts, coverage, and processing configuration.

The initial spatial aggregation uses a nominal 5 km equirectangular grid in
EPSG:4326 coordinates. This is an explicit experiment, not a validated global
equal-area grid. Original latitude and longitude are retained so alternative
methods can be evaluated.

Generate the requested exploratory report after processing:

```powershell
python -m data_pipeline.analyze
```

This writes `exploratory_summary.json` with observation totals, sensor/year/
month counts, confidence distributions, FRP descriptive statistics, and
earliest/latest timestamps. These are counts of satellite observations, not
unique fire counts.

## Validation

From the repository root:

```powershell
python -m pytest tests\test_data_pipeline.py
```

The tests use synthetic fixtures only to verify processing behavior; they are
not satellite observations and must not be used as analytical results.
