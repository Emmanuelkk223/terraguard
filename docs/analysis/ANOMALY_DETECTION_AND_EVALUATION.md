# Anomaly detection and scientific evaluation

## Status and evidence

The implementation is in `ml/anomaly.py`. It provides numeric feature
construction, chronological train/test splitting, Isolation Forest scoring,
an expanding seasonal median/MAD baseline, method-overlap summaries, and
candidate explanations.

The first real-data experiment has now completed:

- Source: VIIRS Suomi-NPP standard processing.
- Retained observations: 109,229.
- Historical weekly rows: 205 calendar rows, of which 136 were excluded as
  `has_observations=False` coverage gaps.
- Observed weekly rows evaluated: 70.
- Training rows: 49.
- Held-out rows: 21, beginning 2023-10-02.
- Isolation Forest candidates: 1.
- Statistical-baseline candidates: 6.
- Overlap: 0.

This is not continuous historical coverage: the source contains only five
days at the start of each month. The results are an execution check and
exploratory comparison, not a validation of either method.

The tests use synthetic fixtures only to verify calculations and reproducibility.
They are not TerraGuard observations or experimental findings.

## Problem definition

The unit of analysis is one historical activity row, normally a time period
and sensor, optionally a grid cell. `observation_count` means the number of
satellite detection records in that unit, not the number of unique physical
fires. A candidate is a period that is unusual relative to its comparison
group; it is not a confirmed fire, emergency, or future prediction.

Temporal and spatial analyses remain sensor-specific. No MODIS and VIIRS
records are silently merged.

## Features

The current Isolation Forest features are:

- `observation_count`
- `frp_sum`, with missing FRP treated as zero only for the numeric model input
- `frp_mean`, with missing FRP treated as zero only for the numeric model input
- Sine and cosine encoding of calendar month

These features are derived from the Milestone 2 activity schema. Sensor identity
is retained in output rows and models are intended to be run on comparable
sensor groups; the current experiment does not encode sensor as an arbitrary
numeric value. Grid-cell identity is retained for explanations, not treated as
a numeric distance.

## Statistical reference

For each target row, the expanding baseline uses only earlier rows with the
same sensor, same grid cell when available, and same calendar month. With
comparison values \(G_t\), it calculates:

\[
m_t = \operatorname{median}(G_t)
\]

\[
MAD_t = \operatorname{median}(|x-m_t|:x \in G_t)
\]

\[
z_t = (x_t-m_t)/(1.4826 \times MAD_t)
\]

At least three earlier comparison values are required by default. A zero MAD
produces an infinite score only when the target exceeds the peer median.
Otherwise the statistical decision is unavailable or not flagged.

This expanding implementation is deliberately distinct from the Milestone 2
leave-one-out descriptive baseline: it prevents future periods from influencing
the evaluation period.

## Isolation Forest experiment

Isolation Forest is used as a candidate unsupervised method because the
available task has no trusted anomaly labels and the method can model
multivariate combinations of counts, FRP, and seasonality. It is not assumed
to be superior.

The runner fits and evaluates a separate model for each sensor. This prevents
the model from treating normal differences between MODIS and VIIRS detection
behavior as anomalies. Sensors with fewer than four activity rows are reported
as skipped rather than pooled into another sensor's model.

Default configuration:

- 200 trees.
- Contamination `0.05`.
- Fixed random seed `42`.
- Chronological 70% training and 30% evaluation split per sensor.
- No random train/test split.

The model is fitted only on earlier activity rows. Its anomaly score is the
negative scikit-learn decision function, so higher values indicate more
isolated/model-anomalous rows. The score is not a probability.

## Comparison and evaluation

The output reports counts flagged by Isolation Forest, the statistical
baseline, both methods, and each method alone. These overlap counts describe
method behavior; they do not establish accuracy.

No reliable ground-truth anomaly labels are currently available. Accuracy,
precision, recall, F1, and predictive performance are therefore not calculated
and must not be inferred from flags or overlap.

After genuine multi-year data is available, sensitivity should be evaluated
over reasonable contamination values, minimum baseline samples, thresholds,
and training cutoffs. Results should also be reviewed by sensor and cell.

For the acquired sample, contamination sensitivity produced:

| Contamination | ML flags | Statistical flags | Overlap |
|---:|---:|---:|---:|
| 0.01 | 0 | 6 | 0 |
| 0.05 | 1 | 6 | 0 |
| 0.10 | 5 | 6 | 0 |

Changing the statistical threshold to 2.5 while retaining contamination 0.05
also produced 1 ML flag, 6 statistical flags, and 0 overlap. This sensitivity
shows that ML flags depend materially on contamination and that neither method
has demonstrated superiority.

## Explanations and limitations

Each output row contains period, sensor, optional cell, observed counts, FRP
features, baseline statistics, both method flags, the method combination, and
an explanation. The explanation deliberately states “satellite-detected
activity” and not “confirmed fire.”

Limitations include sparse seasonal history, source-data gaps, sensor
detection differences, FRP availability, model sensitivity to contamination,
and the absence of validated labels. Imputing missing FRP as zero is a model
input convention, not evidence that emitted energy was zero. Empty activity
periods remain observations of zero records and do not prove no fire occurred.
For anomaly evaluation, rows explicitly marked `has_observations=False` are
excluded because this dataset's missing acquisition windows are not measured
zero activity.

## Reproduction

After Milestone 1 has produced genuine observations and Milestone 2 has
generated historical activity:

```powershell
python -m pip install -r data_pipeline\requirements.txt
python -m pip install -r ml\requirements.txt
python -m data_pipeline.historical `
  --observations data/processed/observations.csv `
  --output-dir data/processed/analysis
python -m ml.anomaly `
  --activity data/processed/analysis/historical_week.csv `
  --output-dir data/processed/anomalies
python -m pytest -q
```

Outputs are:

- `anomaly_candidates.csv`
- `anomaly_experiment_metadata.json`

They must remain separate from raw observations and historical aggregation
outputs. The CLI fails explicitly when the required real-data input is absent.

## Recommendation

Do not expose candidate anomalies through the backend until more complete
archive coverage has been acquired, sensitivity has been reviewed, and the
team has agreed how the output schema communicates method, coverage, and
uncertainty. In this experiment, Isolation Forest did not reproduce the six
statistical candidates and its single candidate was not independently
validated; no claim of added value is justified.
