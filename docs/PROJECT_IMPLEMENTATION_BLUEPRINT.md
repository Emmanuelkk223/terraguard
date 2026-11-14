# TerraGuard Project Implementation Blueprint

## 1. Purpose and scope

This document records the repository assessment and a practical implementation
plan for TerraGuard. It is intentionally a planning document: it does not claim
that proposed features, datasets, model outputs, or API responses already exist.

### Milestone 1 implementation status

The data-engineering foundation is now implemented in `data_pipeline/`. It
provides an official FIRMS area-API downloader requiring `FIRMS_MAP_KEY`, CSV
loading with source provenance, validation and exclusion reporting, GeoJSON
boundary filtering, sensor-preserving daily/weekly/monthly aggregation, and
exploratory summary generation. Tests cover these behaviors. No genuine FIRMS
observations have been downloaded in this workspace because no credential or
boundary dataset was supplied; consequently, no observation totals or
scientific findings are reported as actual results yet.

The Milestone 2 historical analysis layer is now implemented in
`data_pipeline/historical.py`, with daily/weekly/monthly observation summaries,
sensor-preserving spatial summaries, leave-one-out seasonal median/MAD
baselines, candidate unusual-activity flags, reproducibility metadata, and
unit tests. It has not been run on real observations because the Milestone 1
processed dataset is still absent.

Milestone 3.5 acquisition validation confirmed that no FIRMS credential,
boundary file, raw observation, or processed dataset is present. The recent
area downloader was corrected to represent the official API accurately
(recent-day window only) and now refuses unsupported historical ranges; the
multi-year archive acquisition remains blocked pending a valid MAP_KEY and
official archive download.

The Milestone 3 anomaly layer is implemented in `ml/anomaly.py`. It builds
supported numeric features, fits a separate Isolation Forest per sensor using
chronological training data, compares held-out results with an expanding
seasonal median/MAD baseline, and writes explainable candidate outputs and
metadata. It has not produced real-data results because no Milestone 2
activity output is present.

The project objective is to provide an exploratory platform for examining
NASA FIRMS active-fire observations over Ghana, comparing sensor-specific
observations, studying historical patterns, and identifying unusual activity
relative to an explainable historical baseline. The platform is not an
emergency-alert system and must not present hotspot observations as unique fire
counts or anomaly results as confirmed fires.

## 2. Assessment basis

The assessment used:

- The root project documentation in `README.md`.
- All role and collaboration documents in `docs/team/`.
- Every source, configuration, dependency, data, and test path in the
  repository.
- File sizes and contents, to distinguish implemented code from placeholders.

The root README describes a planning and research project, a provisional
React/Vite and FastAPI architecture, NASA FIRMS as the planned primary source,
and a five-phase roadmap. The team documents consistently require inspection
before implementation, stable shared interfaces, no invented data or results,
and no unapproved architecture or dependency changes.

## 3. Current repository assessment

### 3.1 Implemented functionality

No executable application functionality is currently implemented.

The repository does contain:

- A substantive project and scientific direction in `README.md`.
- Role-specific ownership and workflow guidance in `docs/team/`.
- The intended directory layout for frontend, backend, ML, data, tests, and
  documentation.
- A minimal HTML file at `frontend/src/joshua-test/test.html`; it contains only
  document metadata and an empty body and is not an application UI.

### 3.2 Partially implemented functionality

The repository has structural placeholders but no partial runtime components:

- `backend/app/main.py` exists but is empty.
- `ml/features.py`, `ml/train.py`, `ml/predict.py`, and `ml/evaluate.py` exist
  but are empty.
- `frontend/vite.config.ts` and `frontend/package.json` exist but are empty.
- `backend/requirements.txt` exists but is empty.
- `tests/test_api.py`, `tests/test_data_pipeline.py`, and `tests/test_model.py`
  exist but are empty.
- `data/raw/` and `data/processed/` contain only `.gitkeep` files.
- `docs/architecture.md`, `docs/api-contract.md`, and `docs/methodology.md`
  exist but are empty.
- `.env.example` and `.gitignore` exist but are empty.

Therefore, there is currently no verified dataset, schema, API contract,
frontend build, model, test suite, dependency set, environment configuration,
or Git-backed implementation to preserve.

### 3.3 Planned but unimplemented functionality

The root documentation proposes, but the repository does not yet implement:

- FIRMS acquisition and provenance tracking.
- Validation, cleaning, duplicate handling, and Ghana filtering.
- Sensor-preserving spatial and temporal aggregation.
- Historical calendar, map, charts, and filters.
- A FastAPI service.
- Seasonal statistical baselines and candidate anomaly detection.
- Model evaluation and persisted outputs.
- Frontend/backend integration.
- Scientific validation and end-to-end testing.

### 3.4 Architectural decisions already documented

The current intended flow is:

```text
NASA FIRMS
  -> acquisition and validation
  -> geospatial processing
  -> sensor-aware harmonization
  -> historical analysis and anomaly pipeline
  -> processed outputs
  -> FastAPI
  -> React web application
```

The documented principles are separation of concerns, stable interfaces,
reproducible processing, incremental integration, and testability. These
principles should be treated as the current direction, not as evidence that
the corresponding components already exist.

### 3.5 Dependencies

No dependencies are declared: both `backend/requirements.txt` and
`frontend/package.json` are empty. The README lists Python, FastAPI, Pandas,
NumPy, GeoPandas, Shapely, PyProj, scikit-learn, React, TypeScript, Vite,
Leaflet/React Leaflet, Plotly.js, Vitest, and optional Joblib as candidates.
They must be confirmed and approved when the relevant implementation begins;
they must not be assumed to be installed.

### 3.6 Integration risks

The principal risks are:

1. **No shared contracts:** data, model, API, and frontend schemas are absent.
2. **No verified source sample:** product selection and field semantics are
   unresolved.
3. **Sensor conflation:** combining MODIS and VIIRS rows as unique fires would
   produce a scientifically misleading metric.
4. **Insufficient history:** seasonal baselines require coverage and explicit
   sufficiency rules.
5. **Missing-data ambiguity:** lack of a detection cannot be interpreted as
   proof that no fire occurred.
6. **Model overclaiming:** unsupervised anomalies have no automatic ground truth
   and must not be described as predictions or alerts.
7. **Parallel development drift:** the five owners could invent incompatible
   dates, identifiers, fields, or error formats unless contracts are agreed
   before implementation.
8. **Operational uncertainty:** there is no configured credential strategy,
   dataset storage policy, startup command, or deployment target.

## 4. Target system architecture

### 4.1 Data acquisition and provenance

The data engineering component should acquire a small, reproducible Ghana
sample first, then expand only after the workflow and contracts are verified.
Each acquisition should record:

- Provider and source URL or download mechanism.
- Product and sensor identity.
- Product/version metadata where available.
- Retrieval timestamp.
- Requested and actual date range.
- Geographic scope and filter used.
- Input file checksum or equivalent immutable identifier.
- Processing code/version and configuration.

Credentials, if required by the chosen FIRMS access method, must come from
environment configuration and never from source code. Raw files must remain
separate from derived files.

The initial product investigation should compare suitable MODIS products with
VIIRS Suomi-NPP and relevant NOAA VIIRS products. The team must document
temporal coverage, spatial resolution, observation characteristics, quality
fields, and product differences before selecting a comparison set. Product
selection must be based on actual FIRMS documentation and an inspected sample.

### 4.2 Validation and processing

Validation should distinguish invalid records from unusual but valid
observations. At minimum it should address:

- Required columns and data types.
- Longitude and latitude ranges.
- Parseable timestamps and an explicit timezone convention.
- Missing optional quality and FRP fields.
- Duplicate definition and handling.
- Empty input and all-invalid input.
- Sensor and product identity.

Processing should preserve raw observations and produce documented derived
outputs. A first experiment may evaluate approximately 5 km grid cells and
weekly periods, but neither parameter is scientifically final. The pipeline
must preserve sensor-specific summaries rather than adding MODIS and VIIRS
records into a purported unique-fire count.

### 4.3 Historical analysis

The initial analytical outputs should support:

- Daily and weekly observation summaries.
- Monthly and seasonal summaries where coverage permits.
- Year-over-year comparisons.
- Sensor-specific activity and coverage.
- Spatial distribution by grid cell.
- FRP summaries only where the source product provides a valid FRP field.
- Counts of observations and coverage/data-sufficiency indicators.

Every summary must identify whether it represents observations, aggregated
activity, or a model-derived result.

### 4.4 Statistical baseline and ML

The first anomaly method should be a transparent seasonal baseline:

1. Define the unit of analysis, such as `cell_id` and weekly period.
2. Define the historical comparison population and season representation.
3. Compute a seasonal median and robust dispersion, such as MAD.
4. Produce a documented robust deviation score and threshold.
5. Suppress or label results when historical coverage is insufficient.

Isolation Forest may be evaluated only after the baseline and features are
stable. It should be retained only if it provides a defensible benefit in
stability, useful separation, or interpretability. With no reliable anomaly
labels, evaluation should use holdout periods, sensitivity analysis, stability
checks, representative-case review, and comparison with the statistical
baseline rather than invented accuracy metrics.

An anomaly output should explain the cell and period, observed activity,
baseline, score, threshold/flag rule, contributing sensor summaries, coverage
status, and the limitations of the result.

### 4.5 API

The backend should expose processed outputs and model results without
duplicating data or ML logic. The initial contract should be agreed before
implementation, with candidate routes:

| Route | Purpose |
|---|---|
| `GET /api/health` | Service health and version/status information |
| `GET /api/metadata` | Dataset, product, coverage, provenance, and limitations |
| `GET /api/calendar` | Time-period summaries and activity indicators |
| `GET /api/hotspots` | Filtered observations or spatially aggregated activity |
| `GET /api/sensors/compare` | Sensor-specific comparable summaries |
| `GET /api/anomalies` | Explainable anomaly results and sufficiency status |
| `GET /api/critical-periods` | Optional derived periods, only after its criteria are agreed |

These are proposed routes, not an existing API. Date ranges, geographic
filters, sensor values, pagination/limits, and empty-result behavior must be
specified before route implementation. Invalid parameters should receive
predictable validation errors; missing datasets and unavailable model outputs
should not be disguised as successful empty responses.

### 4.6 Frontend

The React application should consume the API contract through a service layer.
The first usable interface should prioritize:

- A date/sensor filter bar.
- A map for observations or grid summaries with a clear legend.
- A calendar or timeline for daily/weekly activity.
- A small set of historical charts with labeled units.
- An anomaly view showing baseline context and limitations.
- Loading, empty, error, and data-quality states.

The visual language should remain restrained and accessible. Avoid fabricated
KPI cards, decorative effects, and claims stronger than the underlying
observations support.

## 5. Feature roadmap

### Essential first version

1. Select and document a manageable Ghana FIRMS product sample.
2. Implement validation, provenance, and reproducible sensor-aware processing.
3. Produce a minimal documented processed dataset and metadata manifest.
4. Agree and implement the health, metadata, hotspots, and calendar API.
5. Build a functional map/calendar frontend against real processed outputs.
6. Add basic date, geographic, and sensor filters.
7. Add automated tests for validation, aggregation, API validation, and core UI
   states.

The first version should deliberately exclude unvalidated alerts, unique-fire
claims, and complex model-driven UX.

### Important subsequent improvements

- Longer historical coverage and seasonal summaries.
- Sensor comparison views with coverage indicators.
- Robust seasonal baseline and explainable anomaly endpoint.
- Historical charts and anomaly timeline.
- Data export with provenance metadata.
- Sensitivity analysis for grid size, period length, thresholds, and product
  selection.
- Integration and regression tests across the API and frontend.

### Advanced or optional capabilities

- Isolation Forest comparison after baseline evaluation.
- Additional NOAA VIIRS products and broader West Africa coverage.
- Environmental context layers, only after source, licensing, and semantics
  are agreed.
- More advanced spatial clustering or event-oriented analysis.
- Operational deployment and monitoring.

Advanced work must not delay a reproducible core pipeline and usable explorer.

## 6. Component responsibilities

| Owner | Initial responsibility | Must not independently change |
|---|---|---|
| Team lead/scientific coordinator | Resolve scope, approve assumptions, coordinate contracts, review scientific claims and integration | Other owners' implementations without agreement |
| Data engineering/geospatial | FIRMS investigation, acquisition, validation, provenance, spatial/temporal aggregation, processed outputs | API, frontend, or ML implementation |
| ML/evaluation | Features from agreed data, seasonal baseline, candidate model evaluation, inference/output artifact | Raw ingestion, API routes, or frontend |
| Backend | FastAPI startup, data access, validation, response schemas, model-output serving, API tests | Raw pipeline, model internals, or frontend |
| Frontend | React/Vite shell, map, calendar, filters, charts, states, API integration, UI tests | Backend, ML, data schema, or root configuration without approval |

The coordinator should review cross-component pull requests for scope,
scientific validity, interface compatibility, and tests.

## 7. Shared technical contracts to agree before coding

### 7.1 Observation contract

The team should agree on canonical names and types for at least:

- `observation_id` or a documented source-key strategy.
- `sensor` and `product`.
- `observed_at` and date/timezone semantics.
- `latitude` and `longitude`.
- Sensor-specific quality/confidence fields.
- Optional `frp`.
- Provenance fields such as source file/version.

The contract must define whether duplicate handling is exact-row, source-key,
or another rule and must preserve enough information for auditability.

### 7.2 Aggregated activity contract

Agree on:

- `cell_id` generation and coordinate reference system.
- Grid size and whether it is configurable.
- Period start/end and timezone.
- Sensor-specific observation counts.
- FRP aggregation semantics.
- Coverage/availability fields.
- Product/version and processing configuration references.

Avoid an ambiguous field such as `fire_count`; use terminology that makes clear
whether a value counts satellite observations or an explicitly defined derived
event.

### 7.3 Model output contract

At minimum, agree on:

```text
cell_id
period_start
period_end
observed_activity
baseline_activity
dispersion
anomaly_score
anomaly_flag
method
sensor_summary
data_sufficiency
explanation
```

The exact field types, score direction, threshold rule, insufficient-data
behavior, and version/configuration metadata must be documented. The backend
must be able to serve a result without importing model-training internals.

### 7.4 API contract

For each route, agree on query parameters, defaults, maximum range/limit,
response envelope, date format, sensor enumeration, pagination, empty-result
behavior, and error shape. The frontend must consume these names exactly.

### 7.5 Configuration and artifacts

Agree on environment variable names for credentials and paths, local versus
committed data, generated artifact policy, and whether Parquet/GeoJSON support
is required. Do not make a format a hard dependency until the team has
selected it based on the actual data and available runtime dependencies.

## 8. Testing strategy

### Data and geospatial tests

Use small, clearly labeled fixtures to test:

- Required-field and type validation.
- Invalid coordinates and timestamps.
- Duplicate behavior.
- Missing optional fields.
- Empty input.
- Ghana boundary filtering.
- Deterministic cell assignment and period aggregation.
- Preservation of sensor/product identity.
- Separate MODIS and VIIRS summaries.
- Provenance and output schema.

### ML tests and evaluation

Test feature construction, deterministic baseline calculations, MAD-zero
behavior, insufficient-history handling, missing-value handling, output schema,
and reproducibility. Use time-based holdouts where possible. Report sensitivity
and representative cases; do not report classification metrics without labels.

### Backend tests

Test startup, health, metadata, valid and invalid filters, response schemas,
empty results, missing datasets, unavailable model artifacts, and internal
errors without leaking paths or secrets.

### Frontend tests

Test rendering, API loading/error/empty states, date and sensor filters,
response-field handling, map/chart integration boundaries, accessible labels,
and responsive layout behavior.

### Integration and scientific checks

At least one integration fixture should flow from processed data through the
API to the frontend contract. A review checklist should verify that:

- A hotspot is described as an observation, not automatically a unique fire.
- MODIS and VIIRS are not silently summed as equivalent measurements.
- Missing detections are not described as no fire.
- Anomaly outputs are not presented as predictions or alerts.
- Dataset coverage, product identity, and analytical configuration are visible.

## 9. Scientific validation plan

1. **Product review:** inspect official FIRMS documentation and a real sample;
   record product, version, fields, coverage, resolution, and quality meaning.
2. **Data audit:** quantify invalid rows, duplicates, missing fields, geographic
   coverage, temporal gaps, and sensor representation.
3. **Processing checks:** compare hand-calculated examples with pipeline
   aggregation and verify invariants such as sensor conservation.
4. **Parameter sensitivity:** compare candidate grid sizes and daily/weekly
   intervals without presenting one as validated prematurely.
5. **Baseline review:** inspect seasonal baseline behavior in high- and
   low-activity periods and record insufficient-history cases.
6. **Anomaly review:** compare flagged periods with source observations and
   baseline context; document false-positive-like and unstable cases without
   inventing ground truth.
7. **Reproducibility:** retain input identifiers, configuration, code version,
   method, and evaluation procedure alongside derived outputs.
8. **Communication review:** ensure labels and explanatory text match what
   satellite observations and the method can establish.

## 10. Dependency-aware implementation milestones

### Milestone 0 — Contract and product decision

- **Objective:** Agree on the first FIRMS products, Ghana scope, time window,
  canonical fields, date convention, cell identifier, and output terminology.
- **Responsible:** Scientific coordinator with data, ML, backend, and frontend
  owners.
- **Prerequisites:** Repository assessment completed.
- **Deliverables:** Approved observation/aggregation/model/API contracts and a
  selected small real-data sample plan.
- **Acceptance criteria:** Every owner can identify the fields and formats they
  consume or produce; no route or field remains “proposed” without an owner.

### Milestone 1 — Reproducible data foundation

- **Objective:** Acquire and process a small real Ghana sample.
- **Responsible:** Data engineering.
- **Prerequisites:** Milestone 0 product and observation decisions.
- **Deliverables:** Acquisition/provenance procedure, validation functions,
  sensor-preserving aggregation, metadata manifest, fixtures, and tests.
- **Acceptance criteria:** A documented command or procedure reproducibly
  produces outputs with validated schema, provenance, coverage indicators, and
  separate sensor summaries.
- **Dependencies:** ML receives the agreed processed fixture; backend receives
  the output location/format.

### Milestone 2 — Minimal API

- **Objective:** Make verified processed data discoverable and queryable.
- **Responsible:** Backend.
- **Prerequisites:** Milestone 0 API contract and Milestone 1 output fixture.
- **Deliverables:** FastAPI app, health/metadata/hotspots/calendar routes,
  validation, error handling, and tests.
- **Acceptance criteria:** Startup succeeds; documented valid requests return
  real fixture-derived data; invalid requests and missing data have predictable
  responses.
- **Dependencies:** Frontend consumes only the agreed API; data engineering
  supplies stable fixture/output semantics.

### Milestone 3 — Core explorer

- **Objective:** Provide the first usable map and calendar.
- **Responsible:** Frontend.
- **Prerequisites:** Milestone 2 response contract and available API.
- **Deliverables:** React/Vite shell, filters, map, calendar/timeline,
  loading/error/empty states, and UI tests.
- **Acceptance criteria:** A user can select the supported period/sensor filters,
  inspect returned activity, and distinguish sensor observations and limitations.
- **Dependencies:** Backend route behavior and data field names must remain
  stable after contract approval.

### Milestone 4 — Historical baseline

- **Objective:** Add an interpretable anomaly baseline.
- **Responsible:** ML, with scientific coordination.
- **Prerequisites:** Sufficient processed history and stable aggregation/model
  contracts.
- **Deliverables:** Seasonal baseline, robust score/flag logic, sufficiency
  rules, evaluation fixture, explanation fields, and tests.
- **Acceptance criteria:** Results are reproducible, time-aware, labeled as
  anomalies rather than predictions, and include baseline and data context.
- **Dependencies:** Data coverage and cell/period definitions from Milestone 1;
  backend output contract before serving results.

### Milestone 5 — Integrated analysis and validation

- **Objective:** Connect anomaly results and historical comparisons end to end.
- **Responsible:** All owners; coordinator leads acceptance.
- **Prerequisites:** Milestones 2–4.
- **Deliverables:** Anomaly API/UI, sensor comparison view, end-to-end fixture,
  sensitivity report, limitations text, and release checklist.
- **Acceptance criteria:** A clean environment can run the documented workflow;
  tests pass; source provenance and method limitations are visible; no
  unsupported scientific claim appears in the UI.

### Milestone 6 — Optional improvements

- **Objective:** Evaluate additional sensors, Isolation Forest, exports,
  environmental context, or expanded geography.
- **Responsible:** Assigned owner after coordinator approval.
- **Prerequisites:** Stable core workflow and evidence that the improvement
  addresses a demonstrated need.
- **Deliverables:** Focused proposal, implementation, evaluation, and updated
  contracts/documentation.
- **Acceptance criteria:** The capability provides measurable, documented value
  without weakening interpretability or reproducibility.

## 11. First milestone work allocation

During the first implementation milestone, after contract decisions:

- **Scientific coordinator:** chair the product/field decision, approve
  terminology and limitations, and review the sample plan.
- **Data engineer:** inspect the selected FIRMS sample, implement validation and
  provenance, and produce the first sensor-aware processed fixture.
- **ML engineer:** specify the minimum feature requirements, review aggregation
  fields, and prepare baseline test cases without claiming trained results.
- **Backend engineer:** turn the agreed output and metadata fields into the
  initial API contract and a startup/test skeleton after the fixture shape is
  known.
- **Frontend engineer:** map the agreed API fields to the first explorer
  wireframe/component boundaries and define loading, empty, and limitation
  states without inventing data.

## 12. Recommendation

### What to implement first?

Implement the first real FIRMS sample, its validation/provenance pipeline, and
the shared observation and aggregation contracts.

### Why first?

Every later component depends on the meaning, coverage, identifiers, and fields
of processed observations. Building the UI, API, or model before that decision
would create integration rework and could encode scientifically misleading
assumptions.

### What must be agreed before coding?

Agree on the initial FIRMS products and date range, Ghana filtering, sensor and
product fields, timestamp convention, duplicate rule, cell/period definitions,
observation terminology, data-sufficiency semantics, output format, and the
initial API/model response envelopes.

### What should each member do in the first milestone?

The coordinator resolves and documents decisions; data engineering produces and
tests the real processed fixture; ML defines feature needs and baseline
evaluation cases; backend defines the API around the verified output; and
frontend defines the first map/calendar integration against that contract.

## 13. Open decisions and blockers

The following decisions remain before implementation can be considered
integrated:

1. Exact FIRMS product(s), versions, and historical window.
2. Access mechanism and credential handling for the selected data source.
3. Canonical observation and aggregate schemas.
4. Storage format and generated-artifact policy.
5. Spatial grid and temporal interval for the first experiment.
6. Duplicate policy and data-quality flag semantics.
7. API route and error envelopes.
8. Baseline threshold and insufficient-history rule.
9. Whether Isolation Forest is justified after baseline evaluation.
10. Local startup, dependency installation, and test commands.

Until these are resolved, the empty source and test files should remain
placeholders rather than being filled with speculative implementations.
