"""Tests for calendar analytics. Rows are hand-written TEST FIXTURES (logic only)."""

from __future__ import annotations

import pandas as pd

from data_pipeline.calendar_analytics import annual_summary, build_calendar, seasonal_summary


def _monthly(values: dict[int, int], *, coverage_bad: tuple[int, ...] = ()) -> pd.DataFrame:
    rows = []
    for year, value in values.items():
        rows.append({
            "region": "Ghana", "month": f"{year}-01-01", "active_cell_days": value,
            "modis_cell_days": value // 2, "viirs_cell_days": value, "both_cell_days": value // 4,
            "modis_detections": value, "viirs_detections": value * 3,
            "coverage_ok": year not in coverage_bad,
        })
    return pd.DataFrame(rows)


def test_outlier_year_is_flagged_with_explanation_and_leave_one_out_baseline() -> None:
    cal = build_calendar(_monthly({2015: 100, 2016: 110, 2017: 90, 2018: 105, 2019: 95, 2020: 400}))
    row = cal[cal["year"] == 2020].iloc[0]
    assert row["status"] == "unusually_high" and row["reliable"]
    assert row["baseline_n"] == 5 and row["baseline_median"] == 100  # 2020 excluded from own baseline
    assert row["abs_diff"] == 300 and row["pct_diff"] == 300
    assert "historical median of 100" in row["explanation"] and "other years" in row["explanation"]
    assert (cal[cal["year"] != 2020]["status"] == "typical").all()


def test_incomplete_months_are_neither_scored_nor_used_as_baseline() -> None:
    cal = build_calendar(_monthly({2015: 100, 2016: 110, 2017: 90, 2018: 105, 2019: 95, 2020: 100, 2021: 5000},
                                  coverage_bad=(2021,)))
    bad = cal[cal["year"] == 2021].iloc[0]
    assert bad["status"] == "incomplete_coverage" and not bad["reliable"]
    assert cal[cal["year"] == 2015].iloc[0]["baseline_n"] == 5  # 2021 not in anyone's baseline
    assert bad[["abs_diff", "pct_diff", "robust_score"]].isna().all()  # no misleading difference or score


def test_too_few_years_gives_insufficient_baseline() -> None:
    cal = build_calendar(_monthly({2019: 100, 2020: 120, 2021: 500}))
    assert (cal["status"] == "insufficient_baseline").all() and not cal["reliable"].any()


def test_flat_baseline_is_not_given_a_made_up_score() -> None:
    cal = build_calendar(_monthly({2015: 50, 2016: 50, 2017: 50, 2018: 50, 2019: 50, 2020: 80}))
    row = cal[cal["year"] == 2020].iloc[0]
    assert row["status"] == "above_flat_baseline" and pd.isna(row["robust_score"]) and not row["reliable"]


def test_annual_and_seasonal_summaries() -> None:
    cal = build_calendar(_monthly({2015: 100, 2016: 110, 2017: 90, 2018: 105, 2019: 95, 2020: 400}))
    annual = annual_summary(cal)
    assert annual.loc[annual["year"] == 2020, "active_cell_days"].iloc[0] == 400
    assert not annual["complete_year"].any()  # only January present per year
    seasonal = seasonal_summary(cal).iloc[0]
    assert seasonal["max_year"] == 2020 and seasonal["min_year"] == 2017 and seasonal["n_years"] == 6


def _validation_frame(shared_anomaly: bool) -> pd.DataFrame:
    """MODIS and VIIRS share a seasonal cycle; optionally also a common anomaly in one year."""
    rows = []
    for year in range(2015, 2022):
        for month in range(1, 13):
            season = 100 + 80 * (month in (12, 1, 2))
            modis_boost = 3 if (year == 2018 and month in (12, 1, 2)) else 1
            viirs_boost = modis_boost if shared_anomaly else (3 if (year == 2020 and month in (12, 1, 2)) else 1)
            rows.append({
                "region": "Ghana", "month": f"{year}-{month:02d}-01", "coverage_ok": True,
                "modis_detections": season * modis_boost, "viirs_detections": season * viirs_boost * 5,
                "modis_cell_days": season * modis_boost // 2, "viirs_cell_days": season * viirs_boost * 2,
                "both_cell_days": 10, "active_cell_days": season * max(modis_boost, viirs_boost) * 2,
            })
    return pd.DataFrame(rows)


def test_validation_detects_shared_year_to_year_signal() -> None:
    from data_pipeline.validation import validate_grid

    shared = validate_grid(_validation_frame(shared_anomaly=True))
    independent = validate_grid(_validation_frame(shared_anomaly=False))
    assert shared["months"] == 84
    assert shared["raw_detections"]["spearman_raw_series"] > 0.7  # the common season dominates the raw series
    # After removing seasonality, only a genuinely shared anomaly keeps the sensors correlated.
    assert shared["cell_days"]["spearman_deseasonalised"] > independent["cell_days"]["spearman_deseasonalised"] + 0.2
    assert set(shared["agreement_share_both_by_year"]) == set(range(2015, 2022))
