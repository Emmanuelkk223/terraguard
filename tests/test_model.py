import pandas as pd
import pytest

from ml.anomaly import (
    build_features,
    compare_methods,
    expanding_baseline,
    fit_isolation_forest,
    explain_candidates,
    run_experiment,
)


def _activity() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period_start": pd.date_range("2020-01-06", periods=12, freq="W-MON"),
            "sensor": ["VIIRS"] * 12,
            "cell_id": ["cell_a"] * 12,
            "observation_count": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 20],
            "frp_sum": [10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10, 200],
            "frp_mean": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        }
    )


def test_feature_construction_is_numeric_and_seasonal():
    features = build_features(_activity())
    assert {"month_sin", "month_cos"}.issubset(features.columns)
    assert features[["observation_count", "frp_sum", "month_sin"]].notna().all().all()


def test_invalid_feature_input_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        build_features(
            pd.DataFrame(
                {
                    "period_start": ["2024-01-01"],
                    "sensor": ["VIIRS"],
                    "observation_count": [-1],
                }
            )
        )


def test_expanding_baseline_uses_only_prior_periods():
    result = expanding_baseline(_activity(), min_samples=3)
    assert not result.iloc[0]["baseline_eligible"]
    assert result.iloc[-1]["baseline_sample_count"] >= 3
    assert result.iloc[-1]["baseline_score"] > 3.5


def test_isolation_forest_is_reproducible_with_fixed_seed():
    activity = _activity()
    train, test = activity.iloc[:8], activity.iloc[8:]
    first = fit_isolation_forest(train, test, random_state=7)
    second = fit_isolation_forest(train, test, random_state=7)
    assert first["ml_anomaly_score"].tolist() == second["ml_anomaly_score"].tolist()
    assert first["ml_anomaly_flag"].tolist() == second["ml_anomaly_flag"].tolist()


def test_explanations_and_comparison_preserve_method_identity():
    activity = _activity()
    train, test = activity.iloc[:8], activity.iloc[8:]
    scored = fit_isolation_forest(train, test, random_state=7)
    baseline = expanding_baseline(activity, min_samples=3).iloc[8:].reset_index(drop=True)
    results = explain_candidates(scored, baseline)
    summary = compare_methods(results)
    assert "explanation" in results
    assert set(results["flagged_by"]).issubset(
        {"both_methods", "isolation_forest_only", "statistical_baseline_only", "neither"}
    )
    assert summary["no_ground_truth_metrics"] is True


def test_experiment_evaluates_sensors_independently(tmp_path):
    activity = pd.concat(
        [_activity(), _activity().assign(sensor="MODIS", observation_count=lambda f: f["observation_count"] + 1)],
        ignore_index=True,
    )
    activity["has_observations"] = True
    activity.loc[0, "has_observations"] = False
    source = tmp_path / "historical_week.csv"
    activity.to_csv(source, index=False)
    metadata = run_experiment(source, tmp_path / "anomalies", random_state=11)
    assert metadata["sensors"] == ["MODIS", "VIIRS"]
    assert metadata["coverage_gap_rows_excluded"] == 1
    assert set(metadata["evaluation_start_by_sensor"]) == {"MODIS", "VIIRS"}
    assert (tmp_path / "anomalies" / "anomaly_candidates.csv").exists()