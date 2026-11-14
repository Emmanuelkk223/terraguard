# TerraGuard 🌍
### Understanding Earth. Protecting Tomorrow.

**An early-stage environmental intelligence project exploring satellite active-fire data harmonization, historical burning patterns, and explainable anomaly detection.**

TerraGuard is being developed in the context of the NASA International Space Apps Challenge 2026. The project explores how observations from different satellite instruments can be brought into a consistent analytical framework and presented through an interactive web application.

Our initial geographical focus is Ghana, with the potential to extend the approach to other parts of West Africa.

> **Project status:** Planning and research. The architecture, features, and methods described in this document represent our current direction and may change as development progresses.

---

## Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Approach](#our-approach)
- [Project Objectives](#project-objectives)
- [Planned Features](#planned-features)
- [Scientific and Technical Approach](#scientific-and-technical-approach)
- [Proposed Architecture](#proposed-architecture)
- [Technology Stack](#technology-stack)
- [Data Sources](#data-sources)
- [Machine Learning Approach](#machine-learning-approach)
- [Data Quality and Scientific Limitations](#data-quality-and-scientific-limitations)
- [Repository Structure](#repository-structure)
- [Team and Responsibilities](#team-and-responsibilities)
- [Development Roadmap](#development-roadmap)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing and Validation](#testing-and-validation)
- [Security and Data Management](#security-and-data-management)
- [Responsible Interpretation](#responsible-interpretation)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Overview

Satellite-based active-fire products provide valuable observations of thermal anomalies associated with fires around the world. These observations can help researchers and other users investigate where and when fire-related activity has been detected.

However, observations from different satellite instruments are not directly interchangeable. Differences in spatial resolution, observation timing, coverage, and detection characteristics can influence the patterns observed in their respective datasets.

TerraGuard aims to explore these differences and develop a practical way to analyze historical burning activity across a common spatial and temporal framework.

The proposed application will combine data processing, geospatial visualization, historical analysis, and machine learning to help users explore reported activity and investigate periods that differ from historical patterns.

### Our vision

To make satellite-derived fire observations easier to explore, compare, and interpret through transparent data processing and accessible analytical tools.

### Our guiding principles

- **Scientific rigor:** Make analytical assumptions explicit and evaluate methods before drawing conclusions.
- **Transparency:** Communicate data quality, uncertainty, and limitations.
- **Interpretability:** Help users understand analytical results rather than presenting unexplained scores.
- **Reproducibility:** Develop data-processing and analytical workflows that can be repeated.
- **Practicality:** Prioritize a working, useful application over unnecessary technical complexity.

---

## The Problem

TerraGuard is motivated by three related challenges.

### 1. Different satellites provide different observations

The Moderate Resolution Imaging Spectroradiometer (MODIS) and the Visible Infrared Imaging Radiometer Suite (VIIRS) provide satellite-derived active-fire observations.

Their spatial resolutions, observation schedules, coverage, and detection characteristics differ. Consequently, the same region and period may have different reported hotspot counts across products.

Simply adding the records together can create misleading summaries.

### 2. Historical observations are not immediately a burning activity calendar

Raw satellite observations contain dates, coordinates, sensor-specific attributes, and other fields that require appropriate processing before they can support consistent geographical and temporal comparisons.

Users need a way to explore the resulting patterns without having to process large satellite datasets themselves.

### 3. Unusual activity needs historical context

A high hotspot count does not necessarily mean an event is unusual for a particular location or season.

Meaningful analysis requires comparisons with an appropriate historical baseline, consideration of data availability, and a clear explanation of what the results can and cannot establish.

TerraGuard will investigate how these challenges can be addressed in a unified web application.

---

## Our Approach

The proposed system follows a data-to-insight workflow:

1. **Acquire:** Obtain suitable MODIS and VIIRS active-fire datasets.
2. **Inspect:** Examine product documentation, data fields, temporal coverage, and quality indicators.
3. **Prepare:** Validate and clean the observations while preserving relevant sensor information.
4. **Harmonize:** Aggregate observations into a documented common spatial and temporal framework.
5. **Analyze:** Investigate historical activity, seasonal patterns, and unusual observations.
6. **Visualize:** Present the processed information through an interactive map, burning activity calendar, and analytical dashboards.
7. **Evaluate:** Test the processing pipeline and analytical methods, document limitations, and examine the sensitivity of results to key assumptions.

The initial implementation will focus on Ghana. The architecture should allow the geographical scope to expand if the data and available development time permit.

---

## Project Objectives

TerraGuard's initial objectives are to:

- Investigate methods for comparing MODIS and VIIRS active-fire observations.
- Develop a reproducible workflow for processing satellite-reported hotspots.
- Explore historical burning activity across geographical areas and time periods.
- Build an interactive web application for exploring the processed observations.
- Investigate anomaly-detection methods that identify departures from historical activity patterns.
- Communicate uncertainty, data limitations, and analytical assumptions.
- Evaluate whether the resulting methods provide useful and interpretable insights.

The immediate goal is a scientifically defensible prototype rather than a production-grade fire-monitoring or emergency-response system.

---

## Planned Features

The following features describe the current project direction. Their implementation status will be updated as development progresses.

### 1. Historical Burning Activity Calendar

**Priority: Essential**

A central feature of TerraGuard will be an interactive calendar for exploring satellite-reported burning activity across different periods.

Planned capabilities include:

- Daily, weekly, and monthly activity summaries, where supported by the underlying data.
- Historical exploration by year and date range.
- Geographical selection and filtering.
- Identification of periods with elevated reported activity.
- Comparisons between selected historical periods.
- Access to the underlying summary information for a selected period.

The calendar will be built from processed observations rather than treating raw sensor records as direct measurements of unique fires.

**Why it matters:** It provides an accessible way to explore the temporal patterns that motivate the project.

### 2. Interactive Geospatial Map

**Priority: Essential**

The map will help users investigate the geographical distribution of reported activity.

Planned capabilities include:

- Displaying satellite-reported hotspot locations.
- Exploring aggregated activity across geographical grid cells.
- Filtering observations by date and sensor.
- Inspecting the information associated with a selected observation or aggregated area.
- Exploring regional differences in historical activity.

The map and calendar will share the same underlying filters and processed data.

**Why it matters:** Temporal summaries are more useful when users can also investigate where the reported activity occurred.

### 3. MODIS–VIIRS Data Harmonization

**Priority: Essential**

TerraGuard will investigate a common analytical framework for comparing observations from MODIS and VIIRS.

The initial approach will explore:

- Consistent spatial aggregation.
- Consistent temporal aggregation.
- Separate sensor-specific summaries.
- Comparisons over overlapping periods and geographical areas.
- The treatment of missing observations and data sufficiency.
- Sensitivity to spatial resolution and temporal binning.

The harmonization method will be documented and evaluated before its outputs are presented as combined activity estimates.

**Why it matters:** This is the central technical problem the project seeks to address.

### 4. Web Application

**Priority: Essential**

TerraGuard will be developed as a web application that connects the processed data, analytical methods, and interactive visualizations.

The proposed interface will bring together the burning activity calendar, geographical map, and analytical views.

**Why it matters:** It makes the project's work accessible through a usable interface rather than requiring users to run individual scripts.

### 5. Historical and Seasonal Pattern Analysis

**Priority: High**

The application will explore recurring patterns in reported activity across historical periods.

Potential analyses include:

- Comparing activity across years.
- Examining seasonal changes.
- Identifying recurring periods of elevated activity.
- Comparing patterns across geographical areas.

**Why it matters:** Historical context helps users interpret observations and provides the foundation for the anomaly-detection component.

### 6. Unusual-Activity Detection

**Priority: High**

TerraGuard plans to investigate machine-learning and statistical approaches for identifying activity that differs from historical patterns.

Potential outputs include:

- An anomaly score.
- An indicator that an observation or period meets a documented anomaly threshold.
- A comparison with a historical baseline.
- Context about data sufficiency.
- An explanation of the factors contributing to the result.

The initial approach will emphasize interpretable statistical methods and anomaly detection.

**Why it matters:** It extends the application beyond visualization by helping users identify periods that warrant closer investigation.

The results will represent unusual patterns in the available observations, not predictions of future fires or confirmation of emergencies.

### 7. Sensor Comparison Dashboard

**Priority: High**

The application will aim to make differences between MODIS and VIIRS visible and explorable.

Potential comparisons include:

- Reported activity by sensor.
- Differences across geographical grid cells.
- Differences across overlapping periods.
- Sensitivity to selected aggregation parameters.
- The effect of available observations on the interpretation of results.

**Why it matters:** It helps users understand the data being combined and makes the harmonization process more transparent.

### 8. Explainability and Data Quality Indicators

**Priority: High**

The application should communicate how much confidence users should place in a result, without suggesting that the data is more complete or precise than it is.

Potential indicators include:

- The number of contributing observations.
- The availability of relevant sensor data.
- The historical baseline used for comparison.
- The anomaly threshold or method applied.
- Relevant data limitations.

**Why it matters:** An analytical result is more useful when users can understand its context and limitations.

### 9. Harmonization Sensitivity Analysis

**Priority: Optional extension**

We plan to investigate whether the conclusions change when selected analytical parameters are varied.

Potential experiments include:

- Comparing different spatial grid sizes.
- Comparing daily and weekly aggregation.
- Evaluating appropriate sensor-specific quality filters.
- Examining the stability of historical patterns and anomaly results.

**Why it matters:** Sensitivity analysis can reveal whether the conclusions depend strongly on particular parameter choices.

### 10. Data Export and Reporting

**Priority: Optional extension**

If time permits, TerraGuard may support exporting selected summaries and analysis results.

Possible formats include CSV for tabular summaries and GeoJSON for suitable geographic outputs.

**Why it matters:** Export functionality could make the application more useful for further research and analysis.

### 11. Environmental Context

**Priority: Future exploration**

Additional datasets, such as rainfall, vegetation, or land-cover information, may be considered if they provide meaningful context and can be integrated reliably.

Any relationships identified would be presented as associations unless a suitable analysis supports stronger conclusions.

**Why it matters:** Environmental context may help users investigate patterns, but it is not necessary for the first working version.

---

## Scientific and Technical Approach

### Data harmonization

The initial investigation will use a common spatial grid and temporal aggregation scheme to make the datasets more comparable.

For example, the team may begin by evaluating approximately 5 km grid cells and weekly aggregation.

These values are starting points for experimentation, not finalized parameters.

The team will investigate alternative grid sizes and aggregation intervals and document the implications of each choice.

The processing workflow should preserve:

- Original sensor identity.
- Product identity and relevant version information.
- Observation date and time.
- Geographic coordinates.
- Available sensor-specific quality attributes.
- Processing and aggregation parameters.

The harmonized dataset should retain separate MODIS and VIIRS summaries wherever possible. This allows users to inspect sensor-specific contributions rather than seeing only a combined value.

### Historical baselines

Historical comparisons should account for seasonal differences where sufficient data is available.

For example, a period with elevated activity during a season that normally has high activity should not automatically be treated as equally unusual as the same count during a season with historically low activity.

The team will investigate appropriate seasonal baselines and robust measures of historical variability.

### Reproducibility

The analytical workflow should make it possible to determine:

- Which input datasets were used.
- Which preprocessing steps were applied.
- Which spatial and temporal parameters were selected.
- Which model and configuration produced an output.
- Which evaluation procedure was used.

This information should be documented alongside the results where practical.

---

## Proposed Architecture

The planned architecture separates data processing, machine learning, backend services, and frontend visualization.

```text
                 NASA FIRMS
                     |
                     v
          DATA INGESTION AND VALIDATION
                     |
                     v
          GEOSPATIAL DATA PROCESSING
                     |
                     v
             DATA HARMONIZATION
                     |
             +-------+-------+
             |               |
             v               v
      HISTORICAL ANALYSIS   ML PIPELINE
             |               |
             |          Model evaluation
             |          and inference
             |               |
             +-------+-------+
                     |
                     v
              PROCESSED OUTPUTS
                     |
                     v
                FASTAPI API
                     |
                     v
            REACT WEB APPLICATION
                     |
          +----------+----------+
          |          |          |
          v          v          v
       Calendar     Map     Analysis views
```

This architecture is provisional and will be refined as the team implements the system.

### Architectural principles

- **Separation of concerns:** Each component should have a clear responsibility.
- **Stable interfaces:** The frontend should consume documented API responses rather than depend on internal processing code.
- **Reproducible processing:** Data preparation and model evaluation should be repeatable.
- **Incremental integration:** Components should be integrated early rather than only at the end.
- **Testability:** Important processing functions and API behaviour should be testable independently.

---

## Technology Stack

The following technologies are under consideration for the initial implementation.

| Area | Proposed technology | Purpose |
|---|---|---|
| Frontend | React | Interactive user interface |
| Language | TypeScript | Frontend type safety |
| Frontend tooling | Vite | Development and build tooling |
| Styling | Tailwind CSS | Responsive interface styling |
| Mapping | Leaflet and React Leaflet | Geospatial visualization |
| Charts | Plotly.js | Interactive charts and historical analysis |
| Backend | FastAPI | HTTP API and application services |
| Data processing | Python, Pandas, NumPy | Tabular processing and numerical analysis |
| Geospatial processing | GeoPandas, Shapely, PyProj | Geographic data operations |
| Machine learning | scikit-learn | Statistical learning and anomaly detection |
| Data storage | Parquet, GeoJSON | Processed tabular and geographic outputs |
| Model persistence | Joblib, where appropriate | Saving compatible fitted models |
| Backend testing | pytest | Automated backend and analytical tests |
| Frontend testing | Vitest | Frontend unit testing |
| Version control | Git and GitHub | Collaboration and source management |
| Frontend hosting | Vercel, if suitable | Frontend deployment |
| Backend hosting | A Python-compatible hosting service | API deployment |

The final stack will be confirmed during implementation. Technologies listed here are proposed choices, not a claim that every dependency has already been installed or used.

---

## Data Sources

### NASA Fire Information for Resource Management System (FIRMS)

FIRMS is the primary planned source for active-fire observations.

Official resources:

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- [FIRMS Data Download](https://firms.modaps.eosdis.nasa.gov/download/)
- [FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/)
- [FIRMS Active Fire Data](https://firms.modaps.eosdis.nasa.gov/active_fire/)
- [FIRMS Data Descriptions](https://firms2.modaps.eosdis.nasa.gov/descriptions/)
- [NASA Earthdata](https://www.earthdata.nasa.gov/)

### Planned satellite products

The initial investigation will evaluate suitable products from:

- **MODIS:** Active-fire observations from the Terra and Aqua satellite instruments.
- **VIIRS:** Active-fire observations from appropriate available instruments, including Suomi-NPP and relevant NOAA platforms.

The selected products will depend on temporal coverage, data availability, product documentation, and suitability for the proposed analysis.

The team will verify product-specific fields, quality attributes, coverage, and licensing or usage requirements before finalizing the processing pipeline.

### Data handling principles

- Preserve sensor and product identity.
- Retain relevant quality information.
- Document the date range and geographic scope of each dataset.
- Avoid treating missing observations as proof that no fire occurred.
- Distinguish raw observations from aggregated summaries and model outputs.
- Keep raw and processed data separate.

---

## Machine Learning Approach

Machine learning is intended to support the analysis of historical activity. It is not a substitute for the data harmonization process.

### Initial objective

Investigate whether historical satellite-reported activity can be used to identify geographical and temporal patterns that differ from an appropriate historical baseline.

### Candidate approaches

#### 1. Seasonal statistical baseline

A statistical baseline will serve as the first reference method.

Potential techniques include:

- Seasonal medians.
- Median absolute deviation (MAD).
- Robust standardized deviations.
- Documented thresholds for flagging unusual observations.

This approach is relatively simple and can provide an interpretable reference for evaluating more complex methods.

#### 2. Isolation Forest

Isolation Forest is a candidate unsupervised anomaly-detection algorithm available through scikit-learn.

It may be evaluated using carefully selected features describing historical activity, seasonality, and relevant observation availability.

It will be retained only if its outputs provide useful value beyond the statistical baseline.

### Candidate features

Depending on the available data and results of the initial investigation, candidate features may include:

- Aggregated activity by grid cell and time period.
- Historical activity statistics.
- Seasonal position.
- Sensor-specific observation summaries.
- Relevant data-sufficiency indicators.
- Historical variability.

The final feature set will be documented and validated.

### Training and evaluation

The team intends to prepare the data, fit candidate models, and evaluate their behaviour before the hackathon where feasible.

Evaluation may include:

- Comparisons against the statistical baseline.
- Tests on historical periods not used to fit the model.
- Sensitivity to parameter changes.
- Stability of anomaly rankings.
- Inspection of representative results.
- Assessment of data sufficiency and interpretability.

Because reliable ground-truth labels for unusual burning activity may not be available, conventional classification accuracy may not be an appropriate metric. Any evaluation limitations will be documented.

The project will not claim predictive accuracy or emergency-detection capability without suitable evidence.

---

## Data Quality and Scientific Limitations

TerraGuard is intended to support exploration and analysis of satellite-derived observations. The following limitations are important to the interpretation of results.

### Hotspots are not unique fire counts

A satellite-reported hotspot is a thermal anomaly detection. Multiple observations may relate to the same fire, while a single fire may produce different numbers of observations across instruments and over time.

Hotspot counts must not automatically be interpreted as counts of unique fires.

### Satellite products differ

MODIS and VIIRS have different spatial resolutions, observation characteristics, and detection capabilities. Their records should not be assumed to be interchangeable.

Harmonization creates a common analytical framework; it does not eliminate every difference between instruments.

### No detection does not mean no fire

A fire may not be detected because of observation timing, cloud cover, fire size, temperature, location, or other factors.

The application should communicate the limits of the observations rather than interpreting an absence of detections as proof of no burning activity.

### Anomalies are not predictions

A period flagged by the model is unusual relative to the selected baseline and method.

It is not automatically evidence of a dangerous fire, an emergency, or a future event.

### Results depend on analytical choices

Spatial resolution, temporal aggregation, quality filters, baseline selection, and model parameters can influence the results.

Important choices should be documented, and sensitivity should be evaluated where practical.

### Data availability matters

Comparisons can be misleading when one sensor has insufficient observations or when the available records cover different periods.

Data sufficiency and relevant coverage information should be considered in the analysis.

---

## Repository Structure

The following is the proposed repository layout. Directories and files will be added as implementation progresses.

```text
teraguard/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   └── requirements.txt
│
├── ml/
│   ├── features.py
│   ├── train.py
│   ├── evaluate.py
│   └── predict.py
│
├── data/
│   ├── raw/
│   └── processed/
│
├── tests/
│   ├── test_data_pipeline.py
│   ├── test_model.py
│   └── test_api.py
│
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   └── api-contract.md
│
├── .env.example
├── .gitignore
└── README.md
```

The final structure may differ as the architecture evolves.

### Directory responsibilities

| Directory | Responsibility |
|---|---|
| `frontend/` | Web interface, map, calendar, and charts |
| `backend/` | API endpoints and application services |
| `ml/` | Feature preparation, model fitting, evaluation, and inference |
| `data/raw/` | Locally stored source datasets |
| `data/processed/` | Derived datasets prepared for analysis |
| `tests/` | Automated tests |
| `docs/` | Technical documentation and shared decisions |

Large raw datasets, secrets, and generated artifacts should not be committed to Git without an explicit team decision.

---

## Team and Responsibilities

TerraGuard is being developed by a five-person team.

The proposed division of responsibilities is:

| Role | Primary responsibilities |
|---|---|
| Team Lead and Scientific Coordination | Scope, harmonization methodology, coordination, integration, and technical review |
| Data Engineering and Geospatial Processing | Data acquisition, validation, preprocessing, aggregation, and geographic analysis |
| Machine Learning and Evaluation | Feature engineering, model fitting, anomaly detection, and evaluation |
| Backend Engineering | API design, data access, inference integration, and backend testing |
| Frontend Engineering | User interface, calendar, maps, charts, filters, and frontend integration |

These roles represent areas of ownership rather than isolated work. Team members should review one another's work, document their interfaces, and help resolve integration issues.

---

## Development Roadmap

The following roadmap describes the intended development sequence.

### Phase 1 — Research and Data Exploration

- Inspect the relevant FIRMS products.
- Select a representative dataset.
- Confirm data fields and product characteristics.
- Establish the initial analytical scope.

### Phase 2 — Data Processing and Harmonization

- Implement data validation and preprocessing.
- Establish the initial spatial and temporal aggregation method.
- Preserve sensor-specific summaries.
- Test the resulting dataset.

### Phase 3 — Core Web Application

- Establish the backend API.
- Build the initial map and activity calendar.
- Connect the frontend to the processed dataset.
- Implement basic geographic and temporal filters.

### Phase 4 — Historical Analysis and Machine Learning

- Establish a seasonal statistical baseline.
- Evaluate candidate anomaly-detection methods.
- Connect model outputs to the backend.
- Add historical and sensor-comparison views.

### Phase 5 — Validation and Refinement

- Test the complete application.
- Inspect representative results.
- Evaluate sensitivity to important analytical parameters.
- Document assumptions and limitations.
- Improve usability and prepare the demonstration.

The order may be adjusted based on data availability, implementation progress, and the time available.

---

## Getting Started

TerraGuard is currently in the planning and research stage. A complete installation workflow will be documented after the initial application structure and dependencies have been implemented.

The intended development environment consists of Python for data processing and the backend, and Node.js for the frontend.

### Prerequisites under consideration

- Git
- Python
- Node.js and npm
- Access to suitable NASA FIRMS datasets
- A supported development environment

### Planned local workflow

Once the initial implementation is available, the repository will provide instructions for:

1. Cloning the repository.
2. Installing backend dependencies.
3. Installing frontend dependencies.
4. Configuring required environment variables.
5. Preparing the selected dataset.
6. Starting the backend API.
7. Starting the frontend development server.
8. Running tests.

Commands will be added once they have been verified against the actual repository structure.

---

## Development Workflow

To make collaboration manageable, the team intends to use a shared Git workflow.

### Branches and pull requests

- Keep `main` as the integrated project branch.
- Develop individual features on separate branches.
- Submit changes through pull requests.
- Review important changes before merging.
- Test affected components before integration.

Example branch names:

```text
feature/data-pipeline
feature/harmonization
feature/anomaly-model
feature/backend-api
feature/frontend-dashboard
```

### Integration principles

The frontend, backend, data pipeline, and model should agree on shared data structures and API contracts.

These interfaces should be documented before major implementation begins.

Where temporary sample data is used to enable parallel development, it must be clearly identified as sample data and replaced or connected to verified outputs before the final demonstration.

### Definition of done

A task should not be considered complete merely because code has been written.

Where appropriate, a completed task should include:

- A working implementation.
- Relevant tests.
- Documentation of its inputs and outputs.
- Confirmation that it follows the agreed interfaces.
- A successful integration check.

---

## Testing and Validation

Testing will cover both software correctness and the scientific behaviour of the analysis.

### Data pipeline

Tests should examine:

- Missing or invalid fields.
- Invalid coordinates.
- Duplicate handling.
- Date and time processing.
- Aggregation correctness.
- Preservation of sensor identity.
- Handling of empty datasets.

### Machine learning

Tests and evaluation should examine:

- Feature preparation.
- Reproducibility where applicable.
- Handling of missing or insufficient data.
- Expected output formats.
- Behaviour under parameter changes.
- Representative anomaly results.

### API and frontend

Tests should examine:

- Endpoint responses.
- Input validation.
- Error handling.
- Frontend rendering of returned data.
- Filtering behaviour.
- Integration between the frontend and backend.

### Scientific validation

The team should verify that the application does not:

- Treat every hotspot as a unique fire.
- Automatically add sensor counts without a defensible method.
- Treat missing observations as proof of no fire.
- Present an anomaly score as a fire prediction.
- Claim a model is accurate without appropriate supporting evidence.

---

## Security and Data Management

TerraGuard is currently maintained in a private repository.

The team should follow these practices:

- Keep API keys and credentials out of source control.
- Store local secrets in environment variables.
- Maintain a `.env.example` containing placeholders rather than real credentials.
- Add local environment files and unnecessary generated artifacts to `.gitignore`.
- Avoid committing large datasets or fitted model files without agreeing on an appropriate storage strategy.
- Document the origin and processing history of datasets used in published results.

The repository's private status does not replace sound security practices.

---

## Responsible Interpretation

TerraGuard is intended as an exploratory environmental data and analysis application.

It is not currently designed or validated as:

- An emergency alert service.
- A replacement for official fire-monitoring systems.
- A source of confirmed fire boundaries or unique fire counts.
- A guaranteed predictor of future fires.
- A substitute for ground observations or expert assessment.

Any future expansion into operational monitoring would require additional validation, suitable data, and a clearly defined operational scope.

---

## Acknowledgements

TerraGuard is being explored in the context of the NASA International Space Apps Challenge 2026.

We acknowledge the work of NASA and the organizations responsible for providing the satellite observations and documentation that make this project possible.

Relevant resources:

- [NASA Space Apps Challenge](https://www.spaceappschallenge.org/)
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- [NASA Earthdata](https://www.earthdata.nasa.gov/)

---

## License

**License: To be determined.**

A license will be selected and added when the project owners decide how the source code and associated materials should be shared.

Until then, do not assume that this repository grants permission to reuse or redistribute its contents.

---

*TerraGuard — Understanding Earth. Protecting Tomorrow.*
