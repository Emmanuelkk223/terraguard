# Architecture

```mermaid
flowchart LR
    FIRMS[NASA FIRMS area API<br/>MODIS_SP, VIIRS SNPP / NOAA-20 / NOAA-21] -->|bulk_download.py<br/>quota-aware, resumable| RAW[(data/raw/firms<br/>immutable CSV)]
    RAW -->|process.py<br/>validate, UTC, dedupe, derived fields| OBS[(data/processed/observations<br/>per-product parquet)]
    BND[(data/reference<br/>geoBoundaries ADM0/ADM1)] --> HARM
    OBS -->|harmonize.py<br/>Ghana clip, common grid, UTC day,<br/>active cell-days, coverage| HARM[(data/processed/harmonized<br/>cell_days_*.parquet, monthly_*.csv)]
    HARM -->|calendar_analytics.py<br/>same-month median/MAD| AN[(data/processed/analytics<br/>calendar, annual, seasonal, anomalies)]
    HARM --> API
    AN --> API[FastAPI read-only API<br/>backend/app]
    API -->|/api proxy| UI[Vite + React dashboard<br/>calendar, map, charts, exports]
```

## Principles

- **Raw data are immutable.** Each stage reads the previous stage's files and writes new ones; the whole chain reruns with
  `python -m data_pipeline.run_all`.
- **Sensor provenance is preserved** in every table (sensor, platform, source product, per-sensor counts).
- **The API is read-only.** It serves generated artifacts and never acquires data or recomputes analytics.
- **Every table states its caveats.** Exports begin with `#` comment lines giving source, method version, area and grid.

## Components

| Component | Responsibility |
|---|---|
| `data_pipeline/bulk_download.py` | Windowed download with retry and FIRMS quota awareness |
| `data_pipeline/process.py` | Validation, timestamps, de-duplication, derived fields, covered date ranges |
| `data_pipeline/regions.py` | Vectorised Ghana clip and region assignment |
| `data_pipeline/harmonize.py` | Strategy A harmonization and monthly series with coverage |
| `data_pipeline/calendar_analytics.py` | Baselines, flags, explanations, annual and seasonal summaries |
| `backend/app/main.py`, `harmonized_routes.py` | API (`/docs` for the live schema) |
| `frontend/src` | Pages, calendar heatmap, map, charts |

## API summary

`/api/health`, `/api/metadata`, `/api/harmonization`, `/api/regions`, `/api/calendar`, `/api/calendar/anomalies`, `/api/seasonal`,
`/api/annual`, `/api/map/cells`, `/api/boundaries`, `/api/export/calendar.csv`, `/api/export/cells.csv`, plus the earlier
sensor-level endpoints (`/api/temporal/{interval}`, `/api/spatial`, `/api/baselines`, `/api/anomalies`, `/api/hotspots`) which
read outputs of the original VIIRS-only analysis and are not used by the dashboard.
