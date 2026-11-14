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
