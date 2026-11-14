"""Tests for the baseline vs Isolation Forest comparison.

The series below are hand-built TEST FIXTURES (a seasonal cycle with mild noise and, in one
case, a deliberately planted spike). They check the method's mechanics, not real fire behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data_pipeline.model_comparison import (
    CONTAMINATION, METHODS, compare, compare_area, feature_matrix, month_statistics, stat_scores,
)

SEASON = np.array([300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280], dtype=float)


def _series(region: str = "Test", spike: tuple[int, int, float] | None = None, years=range(2012, 2026)) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for year in years:
        for month in range(1, 13):
            level = SEASON[month - 1] * (1 + rng.normal(0, 0.05))
            if spike and (year, month) == spike[:2]:
                level *= spike[2]
            active = float(level)
            rows.append({"region": region, "year": year, "month": month, "coverage_ok": True,
                         "active_cell_days": active, "modis_cell_days": active * 0.3, "viirs_cell_days": active * 0.9})
    return pd.DataFrame(rows)


def test_month_statistics_and_scores_use_training_years_only() -> None:
    frame = _series()
    train = frame[frame["year"] <= 2019]
    stats = month_statistics(train)
    assert set(stats) == set(range(1, 13))
    assert abs(stats[1]["median"] - SEASON[0]) < 40
    scores, limits = stat_scores(np.array([SEASON[0] * 3, SEASON[0]]), np.array([1, 1]), stats)
    assert scores[0] > limits[0] and abs(scores[1]) < limits[1]  # tripled month exceeds its calibrated limit


def test_planted_spike_in_test_period_is_found_by_all_methods() -> None:
    result = compare_area(_series(spike=(2022, 1, 3.0)))
    assert result is not None and "2022-01" in result["flags"]["stat"]
    assert "2022-01" in result["flags"]["if_deseason"]
    assert result["test_months"] == 72 and result["train_months"] == 96


def test_ordinary_test_months_are_rarely_flagged() -> None:
    result = compare_area(_series())
    assert result is not None
    assert result["flag_counts"]["stat"] <= 2
    assert result["flag_counts"]["if_deseason"] / result["test_months"] <= 3 * CONTAMINATION


def test_methods_are_deterministic_for_a_seed_and_report_all_fields() -> None:
    a = compare_area(_series(spike=(2021, 7, 4.0)), seed=3)
    b = compare_area(_series(spike=(2021, 7, 4.0)), seed=3)
    assert a["flags"] == b["flags"] and a["flag_counts"] == b["flag_counts"]
    assert set(a["flags"]) == set(METHODS) and "_injection" in a


def test_insufficient_data_returns_none_and_incomplete_months_are_ignored() -> None:
    assert compare_area(_series(years=range(2012, 2016))) is None  # no test years
    frame = _series(spike=(2022, 1, 3.0))
    frame.loc[(frame["year"] == 2022) & (frame["month"] == 1), "coverage_ok"] = False
    result = compare_area(frame)
    assert result is not None and "2022-01" not in result["flags"]["stat"] and result["test_months"] == 71


def test_flat_baseline_is_unscorable_not_flagged() -> None:
    flat = _series()
    flat["active_cell_days"] = 100.0
    result = compare_area(flat)
    assert result is not None and result["unscorable_by_stat"] == result["test_months"]
    assert result["flag_counts"]["stat"] == 0


def test_synthetic_injection_detects_large_changes_better_than_chance() -> None:
    report = compare(pd.concat([_series("A"), _series("B")]))
    pooled = report["pooled"]
    assert pooled["areas"] == 2
    rates = pooled["synthetic_injection"]["detection_rate"]
    assert rates["x3"]["stat"] > 0.9 and rates["div3"]["stat"] > 0.9
    assert rates["x3"]["if_deseason"] > 0.5
    assert pooled["flag_rate_on_heldout_months"]["stat"] < 0.05
    assert any("No ground-truth" in n for n in report["notes"])  # the honesty note is always present


def test_feature_matrices_have_expected_shapes() -> None:
    frame = _series()
    stats = month_statistics(frame[frame["year"] <= 2019])
    assert feature_matrix(frame, stats, deseasonalise=False).shape == (len(frame), 5)
    assert feature_matrix(frame, stats, deseasonalise=True).shape == (len(frame), 3)


def test_auc_is_a_threshold_free_ranking_measure() -> None:
    from data_pipeline.model_comparison import _auc

    assert _auc(np.array([5.0, 6.0, 7.0]), np.array([1.0, 2.0, 3.0])) == 1.0
    assert _auc(np.array([1.0, 2.0, 3.0]), np.array([5.0, 6.0, 7.0])) == 0.0
    assert _auc(np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0])) == 0.5
    assert _auc(np.array([1.0]), np.array([1.0, 2.0, 3.0])) is None


def test_pooled_report_includes_auc_for_every_method() -> None:
    report = compare(pd.concat([_series("A"), _series("B")]))
    auc = report["pooled"]["synthetic_injection"]["auc"]
    assert set(auc) == {"x3", "x2", "div3"} and set(auc["x3"]) == set(METHODS)
    assert auc["x3"]["stat"] > 0.95 and auc["div3"]["stat"] > 0.95  # big, clean changes rank at the top
