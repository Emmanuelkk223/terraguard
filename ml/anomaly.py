"""Time-aware Isolation Forest experiments against the robust baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURE_COLUMNS = (
    "observation_count",
    "frp_sum",
    "frp_mean",
    "month_sin",
    "month_cos",
)
BASELINE_SCALE = 1.4826
EXPLANATION = (
    "Unusually high satellite-detected activity relative to the available "
    "historical comparison group; this is not a confirmed fire, emergency "
    "alert, or prediction."
)


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"anomaly analysis requires columns: {missing}")


def build_features(activity: pd.DataFrame) -> pd.DataFrame:
    """Build deterministic numeric features supported by Milestone 2 outputs."""
    _require_columns(activity, ("period_start", "sensor", "observation_count"))
    frame = activity.copy()
    frame["period_start"] = pd.to_datetime(frame["period_start"], errors="coerce")
    if frame["period_start"].isna().any():
        raise ValueError("period_start contains invalid timestamps")
    frame["observation_count"] = pd.to_numeric(
        frame["observation_count"], errors="coerce"
    )
    if frame["observation_count"].isna().any() or (frame["observation_count"] < 0).any():
        raise ValueError("observation_count must contain non-negative numbers")
    for column in ("frp_sum", "frp_mean"):
        if column not in frame:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    month = frame["period_start"].dt.month
    frame["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    frame["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)
    return frame


def chronological_split(
    activity: pd.DataFrame, *, train_fraction: float = 0.7
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Split by timestamp, never by random row selection."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    ordered = activity.sort_values("period_start").reset_index(drop=True)
    split_index = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    train = ordered.iloc[:split_index].copy()
    test = ordered.iloc[split_index:].copy()
    return train, test, pd.Timestamp(test["period_start"].min())


def _comparison_values(
    frame: pd.DataFrame,
    row: pd.Series,
    *,
    history_end: pd.Timestamp,
) -> pd.Series:
    peers = frame.loc[frame["period_start"] < history_end]
    peers = peers.loc[peers["sensor"] == row["sensor"]]
    if "cell_id" in frame and "cell_id" in row:
        peers = peers.loc[peers["cell_id"] == row["cell_id"]]
    peers = peers.loc[peers["period_start"].dt.month == row["period_start"].month]
    return peers["observation_count"].dropna().astype(float)


def expanding_baseline(
    activity: pd.DataFrame, *, min_samples: int = 3
) -> pd.DataFrame:
    """Calculate a chronological seasonal baseline using only earlier periods."""
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1")
    frame = build_features(activity)
    records: list[dict[str, object]] = []
    for index, row in frame.iterrows():
        values = _comparison_values(
            frame,
            row,
            history_end=pd.Timestamp(row["period_start"]),
        )
        median = float(values.median()) if len(values) else np.nan
        mad = float(np.median(np.abs(values - median))) if len(values) else np.nan
        eligible = len(values) >= min_samples and not np.isnan(median)
        if not eligible:
            score = np.nan
        elif mad > 0:
            score = (float(row["observation_count"]) - median) / (BASELINE_SCALE * mad)
        elif float(row["observation_count"]) > median:
            score = np.inf
        else:
            score = 0.0
        records.append(
            {
                "row_index": index,
                "baseline_sample_count": len(values),
                "baseline_median": median,
                "baseline_mad": mad,
                "baseline_eligible": eligible,
                "baseline_score": score,
            }
        )
    return pd.DataFrame(records)


def fit_isolation_forest(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 200,
) -> pd.DataFrame:
    """Fit on chronological training rows and score later rows."""
    if len(train) < 2:
        raise ValueError("at least two training rows are required")
    if not 0 < contamination <= 0.5:
        raise ValueError("contamination must be in (0, 0.5]")
    train_features = build_features(train)
    test_features = build_features(test)
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    model.fit(train_features[list(FEATURE_COLUMNS)])
    result = test_features.copy()
    result["ml_anomaly_score"] = -model.decision_function(
        result[list(FEATURE_COLUMNS)]
    )
    result["ml_anomaly_flag"] = model.predict(result[list(FEATURE_COLUMNS)]) == -1
    result["ml_method"] = "isolation_forest"
    result["ml_contamination"] = contamination
    result["ml_random_state"] = random_state
    return result


def explain_candidates(
    scored: pd.DataFrame, baseline: pd.DataFrame, *, threshold: float = 3.5
) -> pd.DataFrame:
    """Join leakage-safe baseline facts and provide human-readable explanations."""
    result = scored.reset_index(drop=True).copy()
    baseline_values = baseline.reset_index(drop=True)
    for column in baseline_values.columns:
        if column != "row_index":
            result[column] = baseline_values[column]
    result["statistical_anomaly_flag"] = (
        result["baseline_eligible"]
        & (result["baseline_score"] >= threshold)
    )
    result["flagged_by"] = np.select(
        [
            result["ml_anomaly_flag"] & result["statistical_anomaly_flag"],
            result["ml_anomaly_flag"],
            result["statistical_anomaly_flag"],
        ],
        ["both_methods", "isolation_forest_only", "statistical_baseline_only"],
        default="neither",
    )
    result["explanation"] = np.where(
        result["flagged_by"] == "neither",
        "No anomaly method flagged this period.",
        EXPLANATION,
    )
    return result


def compare_methods(results: pd.DataFrame) -> dict[str, object]:
    """Summarize overlap without treating flags as accuracy."""
    ml = results["ml_anomaly_flag"].astype(bool)
    statistical = results["statistical_anomaly_flag"].astype(bool)
    both = ml & statistical
    return {
        "rows_evaluated": int(len(results)),
        "isolation_forest_flags": int(ml.sum()),
        "statistical_baseline_flags": int(statistical.sum()),
        "overlap_flags": int(both.sum()),
        "ml_only_flags": int((ml & ~statistical).sum()),
        "statistical_only_flags": int((statistical & ~ml).sum()),
        "no_ground_truth_metrics": True,
    }


def run_experiment(
    activity_path: Path,
    output_dir: Path,
    *,
    train_fraction: float = 0.7,
    contamination: float = 0.05,
    min_samples: int = 3,
    threshold: float = 3.5,
    random_state: int = 42,
) -> dict[str, object]:
    """Run the time-aware ML/baseline comparison and write traceable outputs."""
    if not activity_path.exists():
        raise FileNotFoundError(
            f"Historical activity not found: {activity_path}. "
            "Run Milestone 2 with genuine FIRMS data first."
        )
    activity = pd.read_csv(activity_path)
    coverage_gap_rows = 0
    if "has_observations" in activity:
        coverage = activity["has_observations"].astype(str).str.lower()
        available = coverage.isin({"true", "1", "yes"})
        coverage_gap_rows = int((~available).sum())
        activity = activity.loc[available].copy()
    if activity.empty:
        raise ValueError("historical activity contains no observed periods")
    activity = build_features(activity)
    if len(activity) < 4:
        raise ValueError("at least four chronological activity rows are required")
    scored_parts: list[pd.DataFrame] = []
    split_times: dict[str, str] = {}
    skipped_sensors: dict[str, str] = {}
    for sensor, sensor_activity in activity.groupby("sensor", sort=True):
        sensor_activity = sensor_activity.reset_index(drop=True)
        if len(sensor_activity) < 4:
            skipped_sensors[str(sensor)] = "fewer than four activity rows"
            continue
        train, test, split_time = chronological_split(
            sensor_activity, train_fraction=train_fraction
        )
        scored = fit_isolation_forest(
            train,
            test,
            contamination=contamination,
            random_state=random_state,
        )
        baseline = expanding_baseline(sensor_activity, min_samples=min_samples)
        test_baseline = baseline.iloc[test.index].reset_index(drop=True)
        scored_parts.append(
            explain_candidates(scored, test_baseline, threshold=threshold)
        )
        split_times[str(sensor)] = split_time.isoformat()
    if not scored_parts:
        raise ValueError(
            "no sensor has at least four activity rows for time-aware evaluation"
        )
    results = pd.concat(scored_parts, ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_dir / "anomaly_candidates.csv", index=False)
    comparison = compare_methods(results)
    metadata = {
        "source_activity": str(activity_path),
        "rows_available": int(len(activity)),
        "coverage_gap_rows_excluded": coverage_gap_rows,
        "rows_train": int(len(train)),
        "rows_evaluated": int(len(test)),
        "evaluation_start_by_sensor": split_times,
        "features": list(FEATURE_COLUMNS),
        "sensors": sorted(activity["sensor"].dropna().astype(str).unique()),
        "skipped_sensors": skipped_sensors,
        "model": {
            "name": "IsolationForest",
            "contamination": contamination,
            "random_state": random_state,
            "n_estimators": 200,
        },
        "baseline": {
            "method": "expanding seasonal median and MAD",
            "minimum_samples": min_samples,
            "threshold": threshold,
            "mad_scale": BASELINE_SCALE,
            "uses_only_prior_periods": True,
        },
        "comparison": comparison,
        "ground_truth_available": False,
        "interpretation": EXPLANATION,
    }
    (output_dir / "anomaly_experiment_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--activity",
        type=Path,
        default=Path("data/processed/analysis/historical_week.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/anomalies"),
    )
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=3.5)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run_experiment(
        args.activity,
        args.output_dir,
        train_fraction=args.train_fraction,
        contamination=args.contamination,
        min_samples=args.min_samples,
        threshold=args.threshold,
        random_state=args.random_state,
    ), indent=2))


if __name__ == "__main__":
    main()
