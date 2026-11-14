# TerraGuard Analytical API

## Architecture

The backend is a read-only FastAPI service. It loads immutable generated CSV
and JSON artifacts under `data/processed/` through a cached data-access service.
It does not acquire data, rerun analysis, mutate raw observations, or combine
sensor records.

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Interactive documentation is available at `/docs`; the OpenAPI schema is at
`/openapi.json`.

## Endpoints

All list endpoints return `data` and `pagination` (`page`, `page_size`, `total`,
and `pages`). `page_size` is limited to 1,000.

| Method and path | Purpose |
|---|---|
| `GET /api/health` | Service and analytical-data availability |
| `GET /api/metadata` | FIRMS source, coverage, model, and scientific metadata |
| `GET /api/temporal/{interval}` | Daily, weekly, or monthly sensor-specific activity |
| `GET /api/spatial` | 5 km nominal grid summaries as GeoJSON points |
| `GET /api/baselines` | Seasonal median/MAD baseline rows |
| `GET /api/anomalies` | ML/statistical anomaly candidates and explanations |
| `GET /api/hotspots` | Validated source observations, paginated |

Temporal, baseline, anomaly, and hotspot endpoints support inclusive
`start_date`, `end_date`, and `sensor` filters. Baselines additionally support
`cell_id` and `candidates_only`; anomalies support `method`; spatial summaries
support `cell_id`.

Dates represent UTC acquisition or analytical period starts. A reversed date
range returns HTTP 422. Empty valid filters return an empty `data` list with
`total: 0`; they are not errors.

## Scientific semantics

`observation_count` counts satellite detection records, not unique physical
fires. `frp_sum` and `frp_mean` are in megawatts where source FRP is present.
Sensors remain separate and must not be added together without a scientific
normalization decision.

Spatial responses are GeoJSON `FeatureCollection` objects with point geometry
at the aggregate mean coordinate and CRS `EPSG:4326`. The point is a
visualization representative, not a boundary or a physical-fire location.

Anomaly records are candidates from the existing statistical and Isolation
Forest experiments. They are not confirmed fires, emergency alerts, or
predictions. The API exposes existing method labels and scores without
inventing severity categories.

## Errors and security

- `422`: invalid query parameters or reversed date range.
- `503`: the requested generated analytical file or metadata is unavailable.
- `200` with empty data: valid query with no matching records.

The service does not expose filesystem paths, credentials, or raw FIRMS keys.
It is unauthenticated for local development; production deployment must add
approved authentication, HTTPS, rate limiting, and network policy.

## Traceability and limitations

`/api/metadata` reports the FIRMS product, source files, actual coverage,
boundary, CRS, baseline configuration, and anomaly experiment configuration.
The current real dataset contains VIIRS Suomi-NPP observations sampled during
the first five days of each month from 2021 through 2024. Missing periods are
coverage gaps, not evidence of zero fire activity. No ground-truth anomaly
labels exist, so the API does not expose classification performance metrics.

## Testing

```powershell
python -m pytest -q
```

API unit tests use temporary analytical fixtures only. Real-data integration
checks against repository outputs must not be interpreted as synthetic
scientific findings.

## Harmonized endpoints (dashboard)

These read `data/processed/harmonized/` and `data/processed/analytics/`. `grid` is `1km`, `2km` or `5km` (default `5km`);
`region` is `Ghana` or one of the 16 regions from `/api/regions`. Unknown regions or grids return 422; missing generated data
returns 503.

| Method and path | Purpose |
|---|---|
| `GET /api/harmonization` | Method, version, platforms, coverage rule, clip and per-grid summary |
| `GET /api/regions` | Region names available for a grid |
| `GET /api/calendar` | Monthly rows with baseline, differences, status, reliability and explanation (`start_year`, `end_year` optional) |
| `GET /api/calendar/anomalies` | Flagged months ordered by score magnitude (`region`, `direction=high|low`) |
| `GET /api/seasonal`, `GET /api/annual` | Seasonal statistics and annual totals (`complete_year` marks full-coverage years) |
| `GET /api/map/cells` | Cell centres for one `year`/`month` (and optional `region`) with active days and per-sensor detections, as GeoJSON points; capped at 20,000 cells with `truncated` set |
| `GET /api/boundaries` | Simplified Ghana ADM1 outline (geoBoundaries, CC BY-SA 2.0) |
| `GET /api/export/calendar.csv` | Calendar rows as CSV with `#` provenance header lines |
| `GET /api/export/cells.csv` | One month's cells as CSV with `#` provenance header lines |

CORS allows the Vite dev origins (`localhost:5173`); the dev server also proxies `/api`.

## Sensor views, custom areas, periods and series

All analytic endpoints accept `sensor=harmonized|modis|viirs` and an area: either `region=<name>` or a custom
`bbox=west,south,east,north` (degrees; a bbox overrides `region`). The default view of a named region is served from
precomputed files; every other combination is computed on demand from the same cell-day table with the same code, then cached.
A single-sensor view uses that sensor's own archive coverage (for example January 2012 is complete for MODIS).

| Endpoint | Added behaviour |
|---|---|
| `GET /api/calendar`, `/api/seasonal`, `/api/annual` | `sensor`, `bbox` |
| `GET /api/calendar/anomalies` | `sensor`, `bbox`; each row adds `modis_status` and `viirs_status`, the status of the same month in each sensor's own series (cross-sensor corroboration) |
| `GET /api/map/cells` | `start`/`end` dates (or `year`/`month`), `sensor`, `bbox`; `active_days` counts days with a detection in the chosen view |
| `GET /api/series` | Daily (up to 1,100 days) or weekly active cell-days for `start`..`end`, with per-sensor columns and a `value` for the chosen view |
| `GET /api/quality` | Records per product, exclusions by reason, missing values per field, sensor mix, incomplete months |
| `GET /api/export/calendar.csv`, `/cells.csv`, `/series.csv` | Same parameters; headers record area, sensor view, grid and period |

Invalid `bbox`, unknown region or sensor, reversed dates, or a daily range that is too long return 422. A valid area with no
detections returns zero-valued rows, not an error.

## Reports, sensitivity, model comparison and rainfall

| Endpoint | Purpose |
|---|---|
| `GET /api/export/report.html`, `/api/export/report.md` | Summary report for an area, sensor view and optional `start`/`end` period (HTML is self-contained and printable) |
| `GET /api/sensitivity` | National results under each sensitivity scenario |
| `GET /api/model-comparison` | Baseline versus Isolation Forest comparison |
| `GET /api/environment/rainfall?region=` | Monthly rainfall with percentile for Ghana or a named region (422 otherwise) |
| `GET /api/environment/association` | Descriptive burning-rainfall rank correlations (association, not causation) |
| `GET /api/seasonal/regions` | Seasonal statistics for every region at once |

## Place search

| Endpoint | Purpose |
|---|---|
| `GET /api/places/search?q=&limit=` | Matches for a town, city, region or country across West Africa, best first (`limit` 1-20, `q` up to 80 characters, at least 2 to match). Accent- and case-insensitive; a trailing country restricts the search (`Kumasi, Ghana`, `Abidjan Ivory Coast`). Each match has `kind` (city, town, place, region, country), `admin1`, `country`, coordinates, `covered` (TerraGuard has fire data there), the Ghana `region` where relevant, and a `bbox` for countries and regions |
| `GET /api/places/coverage` | Which countries have fire data and which are searchable |

Search runs against a local gazetteer; what a user types is not sent to any other service. 503 if the gazetteer file is missing.
