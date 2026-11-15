# TerraGuard

**Turning satellite fire observations into a consistent, honest history of burning activity.**

TerraGuard is a NASA Space Apps Challenge 2026 project for *Harmonization of MODIS and VIIRS Hot Spots*.
It takes the fire detections from two NASA instruments, makes them comparable, and presents the result as an
interactive **burning activity calendar**, a map and an analytics dashboard, from **2002 to the present**. **Ghana comes first and
in the most detail; the other fifteen countries of West Africa are covered too.**

> A detection is a satellite thermal anomaly, **not a unique fire**. TerraGuard describes unusual *history*;
> it does not predict fires or issue alerts. See [docs/limitations.md](docs/limitations.md).

---

## Contents

1. [The problem and the idea](#the-problem-and-the-idea)
2. [What you can do with it](#what-you-can-do-with-it)
3. [Technology stack](#technology-stack)
4. [Set it up and run it](#set-it-up-and-run-it) (clone, install, get data, start)
5. [Using the dashboard](#using-the-dashboard)
6. [How it works, step by step](#how-it-works-step-by-step)
7. [API quick reference](#api-quick-reference)
8. [Tests](#tests)
9. [Troubleshooting](#troubleshooting)
10. [Repository layout and documentation](#repository-layout-and-documentation)
11. [Built with AI assistance](#built-with-ai-assistance)
12. [Challenge compliance](#challenge-compliance)
13. [Credits and licences](#credits-and-licences)

---

## The problem and the idea

NASA has two families of instruments that watch the Earth for fire:

| | MODIS (Terra, Aqua) | VIIRS (Suomi-NPP, NOAA-20, NOAA-21) |
|---|---|---|
| Pixel size | about 1 km | 375 m |
| Confidence | a number, 0 to 100 | low, nominal or high |
| In the record since | 2000 | 2012 |

Because VIIRS sees smaller fires, it reports roughly **11 times more detections** than MODIS in an average month
in Ghana, and that ratio changes from month to month. Adding the raw counts would mix a change of instrument with
a change in fire.

TerraGuard's answer is to count a different unit, the **active cell-day**: a cell of a common grid (1, 2 or 5 km)
with at least one detection on a given UTC day. If both sensors see the same cell on the same day it counts once,
and each sensor's own numbers stay visible next to it.

## What you can do with it

- **Burning activity calendar**: one coloured square per month, 2002 to the present, with unusual months flagged
  and explained in plain language.
- **Map and drill-down**: click a month to see its days, its weeks and the exact grid cells that burned.
- **Ghana first, then West Africa**: Ghana (1, 2 and 5 km grids, 16 regions) is the default; Côte d'Ivoire, Togo and Burkina Faso
  come next, then the other twelve countries and a West Africa total (5 km grid, country level).
- **Any area, any sensor**: a named region or country, a box you draw, a town you search for, or a latitude and longitude you type;
  all satellites together (the default), the **steady set** (Terra, Aqua and Suomi-NPP only), MODIS only or VIIRS only.
- **All satellites, compared like with like**: every satellite is counted and shown, but "is this month unusual?" is judged on the steady set, so
  satellites that joined later cannot raise false alarms (see below).
- **Right now versus history**: the latest 14, 30 or 60 days, or the month so far, against the same dates in every earlier year.
- **Hotspots or harmonized**: the calendar can show the raw number of hotspots detected or the harmonized active cell-days, with a choice of
  colour ramps, including one designed for colour-blind readers.
- **Downloads**: calendar and cell CSVs, **individual hotspots** for a chosen area and dates, a printable report,
  and a PNG of every chart.
- **Honest checks**: sensor agreement, a comparison with machine learning, sensitivity to analysis choices, a
  back-test of the estimated years, and rainfall shown as context only.

### All satellites, and why unusual months are judged on a steady set

TerraGuard counts **every satellite** (Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21): more satellites mean more chances to see a fire. But NOAA-20 (from April 2018)
and NOAA-21 (from March 2023) add overpasses, so counts rise for reasons that have nothing to do with fire: in Ghana, yearly active cell-days are about 21%
higher in 2018, about 45% higher in 2019 to 2022 and 66 to 77% higher in 2023 to 2025 than the same data from Terra, Aqua and Suomi-NPP alone. Judging history
on all satellites produced **five false "unusually high" months**. So every cell-day also keeps its steady-set count: the counts, maps and hotspot downloads use all
satellites, while the comparison with history, the flags, the seasons and the 2002 to 2011 estimate use the **steady set**, and each month's panel shows both numbers.
The calendar marks the years the satellites joined (+N20, +N21), and the **Sensor view** menu lets you look at the steady set, MODIS or VIIRS alone.

### One thing to know about 2002 to 2011

VIIRS did not exist before 2012. For August 2002 to December 2011 the calendar is **estimated** from MODIS, using
the relationship measured from 2012 onwards. Those months are drawn with dashed outlines, carry a 90% range, and
the estimate was tested by hiding later years and predicting them (typical error about 20%). Months before
August 2002 (only Terra was observing) are shown but never compared. Details: [docs/methodology.md](docs/methodology.md).

## Technology stack

| Layer | Technology | Used for |
|---|---|---|
| Language | **Python 3.11** | data pipeline, analysis, API |
| Data handling | **pandas**, **NumPy** | cleaning, grouping, monthly and daily aggregation |
| File formats | **Apache Parquet** (via **PyArrow**), CSV, JSON, GeoJSON | fast processed tables; open exports with provenance headers |
| Geospatial | **Shapely** | clipping detections to Ghana and assigning the 16 regions (point-in-polygon) |
| Statistics | custom robust baselines (median / MAD, log scale), simulation-calibrated thresholds | unusual-month flags (`calendar_analytics.py`, `calibration.py`) |
| Machine learning | **scikit-learn** (Isolation Forest) | a comparison against the statistical baseline only; it is not used for the dashboard's flags |
| Backend | **FastAPI** + **Uvicorn** | read-only REST API, CSV and report exports, automatic docs at `/docs` |
| Frontend | **React 18**, **TypeScript**, **Vite** | the dashboard |
| Maps | **Leaflet** + **react-leaflet**, OpenStreetMap tiles | the interactive map |
| Charts | **Recharts** | all charts, each with PNG export |
| Testing | **pytest**, **httpx** (FastAPI test client), TypeScript type-checking | 154 automated tests |
| Presentation | an interactive slide deck (Claude Artifacts "Slides") | the pitch |

**Data sources:** NASA FIRMS (MODIS and VIIRS active fires) through its area API; NASA POWER (rainfall context);
geoBoundaries (Ghana outline and regions); GeoNames (place names); OpenStreetMap (basemap).

**Design choices worth knowing:** raw files are never modified and every step re-runs from them; writes are atomic
(temporary file then rename) so the API never reads a half-written file; the downloader is resumable and respects
NASA's request quota; the place search runs entirely offline from a local gazetteer, so what a user types is never
sent to another service.

---

## Set it up and run it

### What you need

| Requirement | Notes |
|---|---|
| **Python 3.11 or newer** | check with `python --version` |
| **Node.js 20 or newer** | check with `node --version` |
| **Git** | to clone the repository |
| **A free NASA FIRMS MAP_KEY** | request one at https://firms.modaps.eosdis.nasa.gov/api/map_key/ (it arrives by email) |
| **About 2 GB free disk** for Ghana, or **about 10 GB** with all of West Africa, and **a few hours** for the first download | the data is not stored in the repository |

> **Important:** the repository contains the code and small reference files only. The fire data (about 650 MB
> raw, 200 MB processed) is **not** included. You download it once with your own key (step 3), and the dashboard
> shows data only after steps 3 and 4 have finished.

### Step 1. Clone the repository

```bash
git clone https://github.com/Emmanuelkk223/terraguard.git
cd terraguard
```

### Step 2. Create the Python environment and install packages

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r data_pipeline\requirements.txt -r backend\requirements.txt -r ml\requirements.txt pytest httpx pyarrow shapely
cd frontend
npm install
cd ..
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r data_pipeline/requirements.txt -r backend/requirements.txt -r ml/requirements.txt pytest httpx pyarrow shapely
(cd frontend && npm install)
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip
activation and put `.venv\Scripts\python` in front of every `python` command below.

Keep this terminal (with the environment activated) for the next steps.

### Step 3. Download the NASA data

There are two datasets. **Ghana** (full detail) is the one to start with and is enough to run the whole app. **West Africa** is optional and
adds the other fifteen countries; without it the app works for Ghana exactly as before, and the Area menu simply lists Ghana and its regions.

The download scripts read your key from the `FIRMS_MAP_KEY` environment variable. A `.env` file is **not** loaded
automatically, and your key should never be committed to git (`.env` is already git-ignored; `.env.example` is only a template).

Windows (PowerShell):

```powershell
$env:FIRMS_MAP_KEY = "paste-your-key-here"
```

macOS / Linux:

```bash
export FIRMS_MAP_KEY="paste-your-key-here"
```

**3a. The historical record (2000 to the end of 2025).** Run this from the project folder:

```bash
python -m data_pipeline.bulk_download --sources MODIS_SP VIIRS_SNPP_SP VIIRS_NOAA20_SP VIIRS_NOAA21_SP
```

This is about 4,400 requests of 5 days each and takes roughly **2 to 3 hours**. NASA limits each key to 5,000
transactions per 10 minutes, and the script **pauses by itself** when it nears the limit. You can stop it with
`Ctrl+C` and run the same command again later: finished windows are skipped, and the raw files are never modified.

**3b. (Optional) catch up to today.** The newest weeks live in different NASA products. First look up where each
archive ends:

```bash
curl "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/$FIRMS_MAP_KEY/ALL"
```

Then download 2026 onwards, using the end dates that command printed (example for a standard archive ending
31 Aug 2026 for MODIS and 31 Jul 2026 for VIIRS, near-real-time products filling the rest):

```bash
python -m data_pipeline.bulk_download --sources MODIS_SP --start 2026-01-01 --end 2026-08-31
python -m data_pipeline.bulk_download --sources VIIRS_SNPP_SP VIIRS_NOAA20_SP VIIRS_NOAA21_SP --start 2026-01-01 --end 2026-07-31
python -m data_pipeline.bulk_download --sources MODIS_NRT --start 2026-09-01 --end 2026-11-14
python -m data_pipeline.bulk_download --sources VIIRS_SNPP_NRT --start 2026-08-01 --end 2026-11-02
python -m data_pipeline.bulk_download --sources VIIRS_NOAA20_NRT VIIRS_NOAA21_NRT --start 2026-08-01 --end 2026-11-14
```

Every satellite's product must cover a month for the month to count as complete, so download the near-real-time files for all of them. Near-real-time data may be revised by NASA, and the most recent month is shown as incomplete until it ends.

**3c. (Optional) the rest of West Africa.** A second, much larger download for the whole region (about 4,000 requests and tens of millions of
detections, several hours, about 6 GB). First fetch the national outlines (a few seconds), then download MODIS and all the VIIRS satellites for the region's
bounding box into a separate folder:

```bash
python -m data_pipeline.countries            # writes data/reference/WA_ADM0.geojson and prints the download area
python -m data_pipeline.bulk_download --sources MODIS_SP --start 2000-11-01 --end 2025-12-31 "--area=-25.61,4.02,16.25,27.61" --output-dir data/raw/firms_wa
python -m data_pipeline.bulk_download --sources VIIRS_SNPP_SP VIIRS_NOAA20_SP VIIRS_NOAA21_SP --end 2025-12-31 "--area=-25.61,4.02,16.25,27.61" --output-dir data/raw/firms_wa
```

(Add the 2026 commands from step 3b with the same `--area` and `--output-dir`.) Downloads run at NASA's quota limit (5,000 transactions per 10 minutes), so the
script pauses by itself and retries timeouts; you can run several copies on different date ranges to finish sooner while staying under the limit.
Each response covers the whole region, so they are large (about 6 MB per five days).

> **Want to try it quickly first?** Download a shorter record, for example
> `--sources MODIS_SP VIIRS_SNPP_SP --start 2018-01-01 --end 2025-12-31`, and carry on. The dashboard works, but
> it needs at least five other years of the same calendar month before it will flag a month as unusual, and the
> 2002 to 2011 estimate will not exist.

### Step 4. Process the data

```bash
python -m data_pipeline.run_all
```

This cleans the raw files, clips them to Ghana's outline and 16 regions, harmonizes the sensors, builds the
calendar and the unusual-month analysis, validates the result, runs the sensitivity checks and fetches rainfall
context from NASA POWER (that last step needs internet and is skipped with a warning if you are offline). Expect
roughly **10 to 20 minutes** on the full record. Outputs go to `data/processed/`. Re-run it whenever you download more data.
All satellites are used by default; `--steady-only` restricts the whole analysis to Terra, Aqua and Suomi-NPP, and `--skip-process` re-runs only
the later steps when the raw files have not changed.

**4b. (Optional) process West Africa:**

```bash
python -m data_pipeline.westafrica
```

It takes a while on the full record (tens of minutes). This assigns every detection to its country, harmonizes on a 5 km grid and builds the same calendar analytics for the 16 countries and a
West Africa total. It processes month by month, so memory stays modest, and it can be stopped and re-run. Outputs go to `data/processed/wa/`.

### Step 5. Start the app

Two terminals, both in the project folder.

**Terminal 1, the API** (environment activated):

```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2, the dashboard:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. The API's interactive documentation is at http://localhost:8000/docs.
The dashboard expects the API on port 8000.

### Step 6. (Optional) rebuild the place-search index

Place search ships with a prepared gazetteer in `data/reference/`. To rebuild it from GeoNames:
`python -m data_pipeline.gazetteer`.

---

## Using the dashboard

| Page | What it is for |
|---|---|
| **Start here** | the landing page: who it is for, four steps to start, what you can and cannot get, and tips for getting the most out of it |
| **Overview** | headline numbers, yearly totals, and the latest 30 days compared with earlier years |
| **Burning calendar** | the month-by-year calendar, a period picker, the map, daily or weekly activity, and downloads |
| **Historical analysis** | burning season, year-by-year comparison, regional comparison |
| **Sensor harmonization** | MODIS against VIIRS, orbit drift, the check on the estimated years, sensitivity analysis |
| **Unusual activity** | months flagged as unusually high or low, each with its reason and cross-sensor corroboration |
| **Data and downloads** | data-quality summary, CSV files, reports |
| **Methodology** | every formula, constant and decision with its reason, a calculator that recomputes any month in your browser, the column glossary, limits and credits |

Controls in the header: **Find a place** (type a town, city or country, or **latitude, longitude** such as `6.69, -1.62`; choose a 10, 25 or 50 km
area), **Area** (Ghana first, then its regions, then West Africa and its countries), **Sensor view** (all satellites, the steady set Terra, Aqua and Suomi-NPP, MODIS only, or VIIRS only) and **Grid** (1, 2 or 5 km;
outside Ghana only 5 km exists). Reading the calendar:

- Colour is the number of active cell-days; brighter means more.
- `▲` / `▼` mark months that are unusually high or low compared with the same month in other years.
- Hatched squares are incomplete; **dashed squares are estimated** (before VIIRS existed).
- **+N20** and **+N21** beside 2018 and 2023 mark when NOAA-20 and NOAA-21 joined: counts rise from those years because more satellites are looking, not because there was
  more fire. The ▲/▼ flags are judged on the steady set, so they are not affected.
- Click any month to see its details and a comparison with the same month in other years.
- The **Hotspots detected** switch shows raw satellite detections instead of active cell-days (not comparable across sensors).
- The **Colours** menu offers Inferno, Viridis and Cividis. Numbers and ▲/▼ symbols are always printed, so colour is never the only signal.

**Ghana first.** Ghana is the default area and has the most detail. Outside Ghana the app shows a note: country-level data on a 5 km grid, without the
rainfall context, sensor-agreement statistics or sensitivity analysis, which were produced for Ghana.

---

## How it works, step by step

```
NASA FIRMS (MODIS + VIIRS CSVs)
        |  bulk_download.py        resumable, respects the key's quota
        v
data/raw/firms/                    raw files, never modified
        |  process.py              validate, UTC time, remove exact duplicates, add confidence classes
        v
data/processed/observations/       one clean file per product
        |  harmonize.py            clip to Ghana, common grid + UTC day -> active cell-days
        v
data/processed/harmonized/         cell-days and monthly summaries (1, 2, 5 km)
        |  bridge.py               express MODIS-only months (2002-2011) on the combined scale
        |  calendar_analytics.py   same-month baselines, calibrated "unusual" threshold, explanations
        v
data/processed/analytics/          calendar, seasons, annual totals, validation, sensitivity
        |  backend/app (FastAPI)   read-only API and CSV exports
        v
frontend (React + Vite)            the dashboard
```

1. **Download** FIRMS detections for Ghana's bounding box in 5-day windows.
2. **Clean** them: required fields, valid coordinates, one UTC timestamp, exact duplicates removed (overlapping
   windows create some), and every exclusion logged with a reason.
3. **Clip** to Ghana's real outline and assign each detection to one of its 16 regions (geoBoundaries).
4. **Harmonize**: place both sensors on one grid and one UTC day, and count active cell-days. Every satellite is counted,
   and each cell-day also keeps its steady-set count (Terra, Aqua, Suomi-NPP only).
5. **Complete months only**: a month counts as complete only if the downloaded archive covers all of it for every
   selected sensor. A quiet day is not treated as missing data.
6. **Compare with history**: each month is scored against the same calendar month in other years (median and MAD
   on a log scale) **on the steady set**, so satellites that joined later cannot raise false alarms. The "unusual" threshold is calibrated so
   ordinary months are falsely flagged about 1% of the time.
7. **Bridge 2002 to 2011**: estimate the combined-scale value from MODIS, with a stated range and a back-test.

The full method, validation results and design decisions are in [docs/methodology.md](docs/methodology.md).

---

## API quick reference

The API is read-only. Most endpoints accept `grid` (`1km|2km|5km`), `region`, `sensor` (`harmonized|steady|modis|viirs`)
and an optional `bbox=west,south,east,north`. Full interactive documentation: http://localhost:8000/docs.

| Endpoint | Returns |
|---|---|
| `GET /api/calendar` | one row per month with baseline, difference, flag and explanation |
| `GET /api/calendar/anomalies` | unusually high or low months, with MODIS and VIIRS corroboration |
| `GET /api/seasonal`, `/api/annual` | seasonal pattern and yearly totals |
| `GET /api/map/cells` | grid cells for a date range (GeoJSON) |
| `GET /api/series` | daily or weekly activity |
| `GET /api/current-comparison` | the latest window against the same dates in earlier years |
| `GET /api/areas` | every selectable area, grouped and ordered: Ghana, its regions, West Africa, neighbours, other countries |
| `GET /api/places/search?q=Kumasi` | place search (West Africa) |
| `GET /api/quality`, `/api/validation`, `/api/sensitivity`, `/api/bridge-validation` | data quality and checks |
| `GET /api/export/calendar.csv`, `cells.csv`, `series.csv` | CSV with provenance header lines |
| `GET /api/export/hotspots.csv?start=2025-12-01&end=2025-12-31` | one row per satellite detection |
| `GET /api/export/report.html`, `report.md` | printable summary report |

Another country is the same call with its name (`region=Nigeria`, `grid=5km`); `region=West Africa` gives the regional total.

Example:

```bash
curl "http://localhost:8000/api/calendar?grid=5km&region=Ghana" | head -c 600
curl -o hotspots.csv "http://localhost:8000/api/export/hotspots.csv?start=2025-12-01&end=2025-12-31&sensor=harmonized"
```

Individual-hotspot downloads are limited to 300,000 rows; choose a shorter period or a smaller area for more.

---

## Hosting it for free

[DEPLOYMENT.md](DEPLOYMENT.md) explains how to put TerraGuard online with no cost and no login for visitors: one Docker container on Render's free plan serves the
website and the API, with the processed data packed by `deploy/make_bundle.py` and downloaded from a GitHub release. The container was tested under the free
plan's limits (512 MB of memory, half a CPU): peak memory about 300 MB. Individual-hotspot downloads on the hosted copy cover Ghana only.

## Tests

```bash
python -m pytest -q          # backend and pipeline (154 tests)
cd frontend && npm run build # type-checks and builds the dashboard
```

Tests use small, clearly labelled hand-written fixtures to verify code logic. They are not NASA measurements and
are never used to support scientific claims.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Dashboard shows an error like *Analytical dataset ... is not available* (HTTP 503) | The data has not been processed. Do steps 3 and 4, then refresh. |
| *Could not load data ... may be updating* | A pipeline run was rewriting files. Wait a moment; the dashboard retries on its own. |
| Download prints `quota ... waiting for reset` | Normal. NASA allows 5,000 transactions per 10 minutes per key; the script waits and continues. |
| Download fails with HTTP 400 *Invalid MAP_KEY* | The key is wrong, **or** the quota is exhausted (NASA uses the same message). Check the key, wait 10 minutes, re-run. Avoid running several downloads at once. |
| `FIRMS_MAP_KEY is required` | Set the environment variable in the same terminal (step 3). |
| `ModuleNotFoundError: pandas` | The environment is not activated, or step 2 was skipped. |
| Port 8000 or 5173 already in use | Another copy is running. Stop it, or start the API on another port and change the proxy target in `frontend/vite.config.ts`. |
| Only Ghana appears in the Area menu | West Africa has not been processed: do steps 3c and 4b. |
| Counts jump in 2018 and 2023 | Expected: NOAA-20 and NOAA-21 joined and add detections. Use *Sensor view: Steady set* to compare years like for like. |
| Recent months show as incomplete | A month is complete only when every satellite's product covers it: download the near-real-time files for all satellites (step 3b), then re-run step 4. |
| Calendar still starts in 2012 | The 2000 to 2011 MODIS data was not downloaded, or `run_all` was not re-run afterwards. |

---

## Repository layout and documentation

```
data_pipeline/    download, processing, regions, harmonization, bridge, calendar analytics, validation
backend/app/      FastAPI read-only API
frontend/         Vite + React + TypeScript dashboard
ml/               earlier Isolation Forest experiment (not used by the dashboard)
data/reference/   Ghana boundaries and the place gazetteer (committed; see ATTRIBUTION.md)
data/raw/         downloaded NASA files: firms/ (Ghana), firms_wa/ (West Africa) (generated, git-ignored)
data/processed/   pipeline outputs: Ghana in the root, West Africa in wa/ (generated, git-ignored)
docs/             methodology, limitations, architecture, data dictionary, demo script
tests/            automated tests
```

| Document | Contents |
|---|---|
| [docs/methodology.md](docs/methodology.md) | the method, the bridge for 2002 to 2011, validation results |
| [docs/limitations.md](docs/limitations.md) | what the results do and do not mean |
| [docs/architecture.md](docs/architecture.md) | how the pieces fit together |
| [docs/data_dictionary.md](docs/data_dictionary.md) | every column in the data files |
| [docs/demo_script.md](docs/demo_script.md) | a 2-minute pitch and a 4-minute live demo |
| [docs/PRESENTER_GUIDE.md](docs/PRESENTER_GUIDE.md) | how to use the app, why every decision was made, key numbers and judge Q&A |
| [docs/DEMO_DECK.md](docs/DEMO_DECK.md) | the 7-slide demo required by the challenge and a 30-second script |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | the challenge objectives and submission rules checked one by one |
| [docs/REFERENCES.md](docs/REFERENCES.md) | every data set and package used, with licences |
| [docs/SI_DISCLOSURE.md](docs/SI_DISCLOSURE.md) | the statement on AI tools, for the project form |
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | the original planning document |

## Built with AI assistance

The NASA Space Apps rules require teams to say how AI ("Super Intelligence") tools were used and to acknowledge AI-generated code and data. TerraGuard's
software, tests, documentation and demo slides were developed with the help of **Claude (Anthropic)**, used through Claude Code and the Claude desktop app,
working from the team's instructions and under its review. The charts are drawn by code from the data; no generative image or video model was used, and no
NASA branding appears. Exported files and reports carry a line saying so. The full statement is in [docs/SI_DISCLOSURE.md](docs/SI_DISCLOSURE.md).

## Challenge compliance

[docs/COMPLIANCE.md](docs/COMPLIANCE.md) compares the project, point by point, with the challenge's objectives, its "potential considerations", and the
submission and judging rules, and lists what is met, what is only partly met, and what the team still has to do.

## Credits and licences

Fire data: NASA FIRMS (LANCE / EOSDIS). Boundaries: geoBoundaries gbOpen (national outlines; Ghana regions CC BY-SA 2.0; per-country licences in `data/reference/ATTRIBUTION.md`).
Place names: GeoNames (CC BY 4.0). Rainfall context: NASA POWER (https://power.larc.nasa.gov/).
Basemap: OpenStreetMap contributors.
