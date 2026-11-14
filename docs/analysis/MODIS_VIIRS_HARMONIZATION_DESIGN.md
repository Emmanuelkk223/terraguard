# MODIS–VIIRS Harmonization Design

## 1. Scope and evidence status

This document is the Milestone 3.6 challenge-alignment audit and technical
design for TerraGuard. It is a design document, not evidence that
MODIS–VIIRS harmonization has been completed.

The official 2026 Space Apps Challenge page was requested during this audit,
but the page could not be retrieved from the available environment because of
a transport-level DNS/TLS failure. Its Details and Resources tabs therefore
could not be independently inspected. No challenge-specific resource list or
recommendation is inferred from that failure. The requirements table below
separates requirements supplied in the milestone brief from facts verified in
the repository and official NASA FIRMS sources.

## 2. Current project status

The repository now contains a working FIRMS-to-analysis pipeline and a
read-only analytical API:

1. `data_pipeline/` acquires, validates, filters, and aggregates FIRMS CSV
   observations.
2. `data_pipeline/historical.py` produces daily, weekly, monthly, spatial,
   and seasonal median/MAD outputs.
3. `ml/anomaly.py` performs a chronological Isolation Forest experiment and
   compares it with an expanding seasonal statistical baseline.
4. `backend/app/` serves generated outputs through FastAPI.
5. The frontend remains a placeholder; `frontend/package.json` is empty.

The real processed sample contains only VIIRS Suomi-NPP standard-processing
records (`VIIRS_SNPP_SP`), covering Ghana on the first five days of each month
from 2021 through 2024. It contains 109,229 retained observations from 48
five-day requests. MODIS, NOAA-20, and NOAA-21 observations have not been
acquired or compared. The current outputs are therefore not a harmonized
MODIS–VIIRS record.

## 3. Requirements traceability

| Challenge/design requirement | Current implementation | Evidence | Gap | Recommended action |
|---|---|---|---|---|
| Use MODIS and VIIRS hotspot observations | FIRMS acquisition and validation are implemented, but the acquired sample is VIIRS Suomi-NPP only | `data_pipeline/acquire.py`; `data/processed/metadata.json` | No MODIS observations and no cross-sensor overlap dataset | Acquire standard MODIS and VIIRS products for a common overlap period |
| Harmonize detections into a consistent activity record | Sensor-specific aggregation exists; no harmonization transform exists | `data_pipeline/historical.py`; analysis documentation | Counts remain sensor-specific and cannot be summed defensibly | Add a versioned harmonization stage after validation and before baselines |
| Preserve source/product traceability | Source product, file, sensor, satellite, and instrument fields are retained | `data_pipeline/pipeline.py`; processed schema | Harmonized rows have no harmonization version or source contribution fields | Add method/version, source products, and contribution counts to the derived schema |
| Use standard science-quality data where possible | Historical dated standard FIRMS windows were used for VIIRS SNPP | `docs/data/DATA_ACQUISITION_AND_VALIDATION.md`; FIRMS documentation | Other sensors and complete archive coverage are absent | Prefer standard products for the overlap experiment; document NRT separately |
| Account for spatial and temporal sensor differences | A nominal 5 km grid and daily/weekly/monthly summaries exist | `data_pipeline/historical.py` | Grid/time choices were not validated across both sensors | Evaluate common-grid and common-window sensitivity on overlapping data |
| Build a burning-activity calendar | Temporal outputs and API endpoints exist | `/api/temporal/{interval}`; historical CSV outputs | No frontend calendar and no harmonized activity index | Define a calendar contract over harmonized daily records, with sensor contributions |
| Explain unusual activity | Statistical and ML candidate outputs include scores and explanations | `ml/anomaly.py`; `/api/anomalies` | Current anomalies are based on VIIRS-only activity | Run the existing methods on the harmonized record and retain sensor diagnostics |
| Provide geographic exploration | 5 km grid summaries are served as GeoJSON point features | `/api/spatial` | No user-selected AOI model or AOI-specific recalculation | Introduce validated AOI geometry and derive summaries by AOI/grid intersection |
| Validate the proposed method | Unit tests and VIIRS-only execution evidence exist | `tests/`; milestone reports | No MODIS–VIIRS agreement, bias, or stability validation | Use overlap-period holdouts and predeclared comparison measures |
| Align with the 2026 challenge resources | Official challenge page was inaccessible in this environment | Access failure recorded above | Details/Resources content remains unverified | Re-run the resource audit from a networked environment before implementation |

## 4. Verified NASA resources

The following resources were reachable and used for this design:

- [NASA FIRMS active-fire products](https://firms.modaps.eosdis.nasa.gov/content/active_fire/)
  describes active-fire downloads, FIRMS web services, archive access, and
  the distinction between near-real-time and standard processing.
- [FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/) lists the area,
  data-availability, missing-data, and map-key services.
- [FIRMS download service](https://firms.modaps.eosdis.nasa.gov/download/)
  provides older-than-seven-day CSV, JSON, and shapefile downloads and links
  the MODIS and VIIRS user guides.
- [NASA Earthdata FIRMS tools](https://www.earthdata.nasa.gov/data/tools/firms)
  provides the NASA Earthdata context for FIRMS access and product use.
- [FIRMS Fire Data Academy](https://firms.modaps.eosdis.nasa.gov/academy/)
  provides NASA examples using Python, Jupyter, and Google Colab.
- [MODIS C6 Active Fire Product User Guide](https://www.earthdata.nasa.gov/sites/default/files/imported/MODIS_C6_Fire_User_Guide_B.pdf)
  documents the MODIS active-fire algorithm and product fields.
- [VIIRS 375 m Active Fire Algorithm User Guide](https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_User_Guide.pdf)
  documents the VIIRS active-fire algorithm and product fields.
- [MOD14A1](https://www.earthdata.nasa.gov/data/catalog/lpcloud-mod14a1-061)
  is the MODIS/Terra thermal-anomaly/fire daily Level 3 global 1 km product.
- [VNP14IMG](https://www.earthdata.nasa.gov/data/catalog/lpcloud-vnp14img-002),
  [VJ114IMG](https://www.earthdata.nasa.gov/data/catalog/lpcloud-vj114img-002),
  and [VJ214IMG](https://www.earthdata.nasa.gov/data/catalog/lpcloud-vj214img-002)
  are NASA VIIRS Version 2 375 m active-fire products for Suomi-NPP,
  NOAA-20, and NOAA-21 respectively.
- The [VIIRS User Guide for burned area](https://ladsweb.modaps.eosdis.nasa.gov/archive/Document%20Archive/Science%20Data%20Product%20Documentation/VIIRS_C2_BA_User_Guide_1.1.pdf)
  is relevant only if TerraGuard later adds burned-area products; it is not
  an active-fire hotspot substitute.

The FIRMS active-fire page reports these availability facts at audit time:

- MODIS Collection 6.1: November 2000 to present for the service listing.
- VIIRS 375 m NOAA-20: April 2018 to present.
- VIIRS 375 m NOAA-21: the FIRMS download page reports coverage beginning in
  March 2023; the exact archive availability must be checked before use.
- VIIRS Suomi-NPP 375 m: available through FIRMS, with the exact archive
  availability to be checked using the service's data-availability endpoint
  before requesting a study period.

Availability text and product archives can change. Acquisition metadata must
record the actual product, version, date range, and retrieval time rather than
relying on a planned availability statement.

NASA's VNP14IMG catalog currently states that Suomi-NPP VIIRS science-data
delivery ceased on 2 November 2026 and recommends transitioning to NOAA-20 or
NOAA-21 products for current work. TerraGuard should preserve the historical
Suomi-NPP product where it is needed for overlap, but should not assume that
new Suomi-NPP data will continue to arrive.

## 5. Sensor differences that affect comparison

### Spatial resolution and detection behavior

MODIS active-fire products are based on approximately 1 km nominal
observations, while VIIRS I-band active-fire products use approximately 375 m
pixels. NASA's VIIRS product documentation describes the finer resolution as
supporting improved response to relatively small fires and mapping of large
fire perimeters. A larger VIIRS detection count is not, by itself, evidence
of more fire or greater burned area.

The VIIRS 750 m M-band product and 375 m I-band product must not be treated as
the same observation geometry. The initial harmonization experiment should use
the FIRMS 375 m VIIRS product consistently and document which MODIS product
and nominal resolution are being compared.

### Temporal coverage and overpass timing

The satellites have different orbital tracks, viewing geometry, equator
crossing/overpass times, swath widths, and revisit opportunities. A fire can be
observable to one platform and absent from another because of timing, cloud,
smoke, viewing angle, or short duration. Same-day records are not necessarily
coincident observations of one physical fire.

The calendar should therefore represent an observation window and data
availability, not imply continuous monitoring. Daily aggregation is useful for
the user-facing calendar, but comparison must retain per-sensor availability
and contribution fields.

### Detection confidence and quality

Confidence fields are product-specific and are not automatically calibrated
probabilities across sensors. TerraGuard must preserve the original confidence
field and its product meaning, apply documented product-specific quality
filters, and avoid using the same numeric threshold across MODIS and VIIRS
without validation.

### FRP

Fire Radiative Power is a source-derived estimate associated with a detected
thermal anomaly. Spatial resolution, viewing geometry, atmospheric effects,
cloud contamination, retrieval quality, and sensor characteristics affect FRP.
FRP from MODIS and VIIRS should not be directly added or treated as identical
measurements without an overlap-period calibration study. The first practical
index should expose sensor-specific FRP summaries and use calibrated values
only if a held-out comparison supports the calibration.

### Standard processing versus NRT

FIRMS states that NRT data are replaced by standard science-quality data as
they become available, with a lag that can be several months. NRT and standard
records are therefore different processing states and must not be mixed as
independent detections. The harmonization study should use standard products
for historical comparison and label any NRT-only period as provisional.

## 6. Proposed harmonization strategies

### Strategy A: common-grid, common-window sensor-aware index

Map each valid detection to a documented common grid, retain sensor-specific
rows, and aggregate into UTC daily windows. For each sensor and grid cell,
calculate detection count, FRP summaries, confidence-quality counts, and
availability. Produce a harmonized activity index only when both the product
and window meet the declared minimum data requirements.

**Solves:** incompatible point locations, unequal pixel sizes, and inconsistent
raw record granularity.

**Required data:** overlapping standard MODIS and VIIRS observations,
coordinates, timestamps, product/sensor identity, quality fields, FRP where
available, and a documented grid.

**Assumptions:** the chosen grid is a comparison unit rather than a physical
fire boundary; daily windows are adequate for the calendar; availability can
be measured separately from zero detections.

**Limitations:** residual sensitivity and overpass differences remain; nearby
detections may still be different fires; a common grid does not make sensors
equivalent.

**Validation:** compare sensor-specific rates and ratios in held-out overlap
periods, stratified by month, activity level, confidence, and grid cell.

**Complexity:** linear in the number of observations plus the number of
occupied grid-window groups.

### Strategy B: empirical sensor calibration to a reference index

Use an overlap period to estimate a sensor-specific conversion to a reference
activity scale. Candidate models include robust regression or ratio estimates
for count and FRP features, with month, observation opportunity, and region
as covariates. Apply the calibration only to held-out periods and preserve the
uncalibrated values alongside it.

**Solves:** systematic scale differences in detection counts or FRP.

**Required data:** sufficiently long overlapping coverage, matched grid-window
aggregates, availability indicators, and enough observations for seasonal
stratification.

**Assumptions:** the relationship is stable enough within the chosen strata
and the reference index is meaningful. These assumptions must be tested, not
assumed.

**Limitations:** calibration can encode the overlap period's fire regime,
break under changing product versions, and hide genuine sensor-specific
information.

**Validation:** blocked time holdout, residual analysis, calibration stability
by month and activity level, and comparison against an uncalibrated index.

**Complexity:** modest for robust regression; higher only if many regional
strata are introduced.

### Strategy C: probabilistic latent activity model

Treat observed sensor counts as imperfect measurements of a latent activity
level, with sensor-specific detection rates and observation opportunities.
Estimate the latent index using a hierarchical count model and retain
uncertainty intervals.

**Solves:** unequal detection processes and missing observation opportunities
more explicitly.

**Required data:** substantial overlapping history, reliable availability
covariates, sensor/product quality information, and a validated model design.

**Assumptions:** the observation model and distributional choices are
adequate; parameters are identifiable from available overlap.

**Limitations:** greater complexity, difficult interpretation, sensitivity to
model misspecification, and likely too much scope for the immediate milestone.

**Validation:** blocked predictive checks are diagnostic only; compare
calibrated uncertainty and stability across sensors and regions without
claiming fire-prediction performance.

**Complexity:** substantially higher than Strategies A and B and likely
requires additional statistical dependencies and review.

### Recommended initial approach

Use Strategy A as the first harmonization release, with an optional
carefully-validated Strategy B count index after overlap data are available.
Do not use Strategy C in the next implementation task. Strategy A is
transparent, computationally simple, preserves sensor contributions, and
makes it possible to discover whether a calibration is needed rather than
assuming one.

The output should not be called a harmonized fire count. Use a name such as
`harmonized_activity_index` and expose:

- `aoi_id`, `grid_id`, `period_start`, and `period_end`;
- `sensor_activity` records for each sensor/product;
- `observation_count`, `frp_sum`, `frp_mean`, and quality summaries;
- `observation_opportunity` and `coverage_status`;
- `index_value` only when the minimum data rule is satisfied;
- `harmonization_method`, `harmonization_version`, and source products.

## 7. Duplicate and co-location policy

Spatially and temporally close MODIS and VIIRS detections are not automatically
duplicates or the same physical fire. The default record-level policy is:

1. remove only exact source duplicates using source identity, timestamp,
   coordinates, product, and satellite fields;
2. retain cross-sensor records as separate contributions;
3. optionally produce a clearly labelled co-location diagnostic using a
   distance/time tolerance;
4. never subtract or merge co-located records into a unique-fire count unless
   a separately validated event-linking method is approved.

## 8. Calendar and AOI design

### AOI model

An AOI should be represented by:

```text
aoi_id
name
geometry (GeoJSON Polygon or MultiPolygon)
crs (EPSG:4326 at the API boundary)
source
created_at
```

Ghana is the initial demonstration AOI, identified by a stored boundary
resource rather than a hard-coded backend condition. Future AOIs must pass
geometry validity, coordinate-range, and maximum-complexity checks. The
backend should accept an AOI identifier or a previously registered AOI; it
should not silently accept arbitrary unvalidated geometry in the first
release.

### Calendar record

The central daily record should contain:

```text
aoi_id
period_start
period_end
harmonized_activity_index
coverage_status
sensor_activity[]
historical_percentile_or_baseline
candidate_anomaly
source_products[]
```

Weekly and monthly views should be derived from daily harmonized records using
the same coverage rules. They should show sensor-specific contributions and
the number of observed versus unavailable sensor-days.

### User experience

The future frontend should provide:

- AOI selection with Ghana as the initial example;
- daily calendar heatmap with explicit unavailable-period styling;
- weekly/monthly aggregation controls;
- sensor/product contribution toggles;
- historical seasonal comparison;
- map selection of grid cells and periods;
- anomaly candidate details with baseline, coverage, and explanation;
- a persistent notice that detections are satellite observations, not unique
  fire counts or emergency alerts.

## 9. Relationship to anomaly detection

The existing statistical baseline and Isolation Forest work should be retained
as reusable method components, but their input contract must change from
sensor-only activity to the harmonized activity table:

1. Calculate anomalies on `harmonized_activity_index` only when coverage is
   sufficient.
2. Preserve sensor-specific features as explanatory diagnostics, not as an
   arbitrary sensor-number feature.
3. Keep the existing chronological split and expanding baseline.
4. Add coverage status, sensor contribution, and harmonization version to every
   candidate.
5. Re-run sensitivity analysis after adding a second sensor.
6. Do not compare anomaly flags as accuracy without validated labels.

Sensor-specific anomaly runs may remain useful for diagnosing product
behavior, but they must be labelled diagnostics and not substituted for the
harmonized calendar.

## 10. Validation plan

Before claiming harmonization:

1. Acquire a common overlap period for MODIS, VIIRS Suomi-NPP, NOAA-20, and
   NOAA-21 only where actual product availability supports it.
2. Process standard products with a shared schema and immutable provenance.
3. Quantify per-sensor observation opportunity and missing-data periods.
4. Compare sensor-specific activity by grid, day, month, confidence, and FRP.
5. Use blocked time splits; never randomly mix future periods into calibration.
6. Test grid sizes and daily/weekly windows as sensitivity analyses.
7. Evaluate Strategy A against the uncalibrated sensor-specific view.
8. If Strategy B is attempted, reserve a final time block for calibration
   validation and report residual bias and stability.
9. Inspect representative disagreements; do not turn overlap into labels for
   actual fires.
10. Record the exact product versions, acquisition dates, filtering rules,
    and harmonization version in output metadata.

No conventional accuracy, precision, recall, or F1 score is justified without
validated labels for the target concept.

## 11. Implementation roadmap

### Next task: overlap acquisition and schema extension

Implement a small, reproducible acquisition run for Ghana covering a common
standard-processing period, beginning with MODIS and VIIRS Suomi-NPP and adding
NOAA-20/NOAA-21 only when the official availability service confirms coverage.
Extend provenance metadata and validation to record product-specific quality
fields. Do not yet create a calibrated index.

### Following task: harmonized daily aggregation

Implement Strategy A in a separate harmonization module. Produce sensor
contribution tables, coverage status, and a versioned daily activity index.
Add synthetic unit tests and one real-data execution report.

### Following task: validation and baseline migration

Run blocked overlap comparisons, grid/time sensitivity, and quality-field
review. Only then decide whether a count calibration is justified. Update the
historical baseline and anomaly runner to consume the harmonized table while
retaining sensor diagnostics.

### Later task: calendar integration

Add backend endpoints for AOI-aware harmonized calendar records and update the
frontend only after the output contract is reviewed. This milestone does not
redesign the frontend.

## 12. Risks and unresolved questions

- The official challenge Details and Resources tabs could not be accessed in
  this environment and must be rechecked before final submission.
- The project has no acquired MODIS observations, so no sensor bias estimate
  exists.
- FIRMS product availability and archive coverage can change.
- A five-day-per-month VIIRS sample is inadequate for a continuous activity
  calendar.
- Product confidence fields are not necessarily cross-sensor comparable.
- FRP calibration may require more overlap data than the current project has.
- The suitable common grid is a design choice requiring sensitivity analysis.
- A calendar index can represent observed activity opportunity, but cannot
  establish unique fire identity or complete absence of fire.
- The frontend is not implemented and must not be treated as evidence of
  calendar completion.
- API contracts must be extended only after the harmonized output schema is
  reviewed by data engineering, machine learning, backend, and scientific
  coordination owners.

## 13. Audit conclusion

TerraGuard has a functioning sensor-preserving FIRMS processing and analytical
foundation, but it does not yet solve the central MODIS–VIIRS harmonization
problem. The practical next step is a small standard-product overlap dataset
and a transparent common-grid/common-window activity index with explicit
coverage and sensor contributions. Until that work is executed and validated,
the project should describe itself as a VIIRS-based analytical prototype with
a harmonization design, not as a completed harmonized burning-activity
calendar.
