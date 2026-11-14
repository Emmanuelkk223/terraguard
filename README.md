# TerraGuard

**Turning satellite fire observations into actionable environmental intelligence.**

TerraGuard is a NASA Space Apps Challenge 2026 project for *Harmonization of MODIS and VIIRS Hot Spots*.
It builds a consistent historical record of satellite-detected burning activity for Ghana from NASA FIRMS MODIS
and VIIRS data, and presents it as an interactive **burning activity calendar**, map, and analytics dashboard.

> Detections are satellite thermal anomalies, **not unique fires**, and TerraGuard describes unusual *history*;
> it does not predict fires or issue alerts. See [docs/limitations.md](docs/limitations.md).

## What it does

| Capability | Where |
|---|---|
| Resumable, quota-aware FIRMS download (MODIS, VIIRS SNPP / NOAA-20 / NOAA-21) | `data_pipeline/bulk_download.py` |
| Validation, UTC timestamps, de-duplication, per-product confidence classes | `data_pipeline/process.py`, `pipeline.py` |
| Ghana clipping and 16-region assignment (geoBoundaries) | `data_pipeline/regions.py` |
| **MODIS–VIIRS harmonization** (common grid + UTC day, active cell-days) | `data_pipeline/harmonize.py` |
| Same-month median/MAD baselines with a calibrated threshold, flags with explanations | `data_pipeline/calendar_analytics.py`, `calibration.py` |
| Baseline vs Isolation Forest comparison (no labels: agreement, stability, synthetic sensitivity) | `data_pipeline/model_comparison.py` |
| Read-only API, CSV exports with provenance headers | `backend/app/` |
| Dashboard: calendar with day/week drill-down and date ranges, map with pinned cell details, sensor views (harmonized / MODIS / VIIRS), custom area drawing, history, sensors, anomalies with cross-sensor corroboration, data-quality panel, downloads | `frontend/` |
| On-demand analytics for any sensor view, region or bounding box | `data_pipeline/area_analytics.py` |
| Sensitivity to grid size, platform set and quality filters | `data_pipeline/sensitivity.py` |
| Rainfall context (NASA POWER) and descriptive burning-rainfall association | `data_pipeline/environment.py` |
| Printable summary report (HTML / Markdown) and chart PNG export | `data_pipeline/report.py`, `frontend/src/components/ChartFrame.tsx` |

How the harmonization works, and why raw counts are never added, is in [docs/methodology.md](docs/methodology.md).

## Run it

Requirements: Python 3.11+, Node 20+, and a free NASA FIRMS MAP_KEY (https://firms.modaps.eosdis.nasa.gov/api/map_key/).

```powershell
# 1. Environment
python -m venv .venv
.venv\Scripts\python -m pip install -r data_pipeline\requirements.txt -r backend\requirements.txt -r ml\requirements.txt pytest httpx pyarrow shapely

# 2. Download Ghana 2012-2025 (about 2,800 requests; pauses automatically at the key's quota, takes ~1-2 h)
#    The scripts read the FIRMS_MAP_KEY environment variable (a .env file is NOT loaded automatically).
$env:FIRMS_MAP_KEY = "<your key>"
foreach ($s in "MODIS_SP","VIIRS_SNPP_SP","VIIRS_NOAA20_SP","VIIRS_NOAA21_SP") { .venv\Scripts\python -m data_pipeline.bulk_download --sources $s }

# 3. Process, harmonize, analyse, validate (about 6 minutes; the last step fetches rainfall from NASA POWER and is skipped with a warning if offline)
.venv\Scripts\python -m data_pipeline.run_all

# 4. API (port 8000) and frontend (port 5173), in two terminals
.venv\Scripts\python -m uvicorn backend.app.main:app --reload
cd frontend; npm install; npm run dev
```

Open http://localhost:5173. API docs are at http://localhost:8000/docs.

The download is safe to interrupt and re-run: finished 5-day windows are skipped. Raw files in `data/raw/` are never modified.

## Tests

```powershell
.venv\Scripts\python -m pytest -q
cd frontend; npm run build        # type-checks and builds
```

Tests use small, clearly labelled hand-written fixtures to verify code logic. They are not NASA measurements and are
never used to support scientific claims.

## Repository layout

```
data_pipeline/   download, processing, regions, harmonization, calendar analytics
backend/app/     FastAPI read-only API
frontend/        Vite + React + TypeScript dashboard
ml/              earlier Isolation Forest experiment (sensor-level; not used by the dashboard)
data/reference/  Ghana boundaries (committed; see ATTRIBUTION.md)
data/raw|processed/   generated, git-ignored
docs/            methodology, architecture, data dictionary, limitations, original project plan
tests/
```

## Credits and licences

Fire data: NASA FIRMS (LANCE / EOSDIS). Boundaries: geoBoundaries gbOpen (CC BY-SA 2.0 for ADM1).
Rainfall context: NASA POWER (https://power.larc.nasa.gov/). Basemap: OpenStreetMap contributors. The original planning document is kept in [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md).
