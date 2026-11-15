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
