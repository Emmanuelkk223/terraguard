import numpy as np
import pandas as pd

from data_pipeline.bridge import MIN_FIT_POINTS, backtest, bridge_monthly, fit_log_line, predict
from data_pipeline.calendar_analytics import build_calendar
from data_pipeline.harmonize import AQUA_FIRST_FULL_MONTH, archive_coverage


def make_monthly(first_year=2008, last_year=2025, factor=3.0, region="Ghana"):
    rows = []
    rng = np.random.default_rng(1)
    for year in range(first_year, last_year + 1):
        for month in range(1, 13):
            modis = int(200 + 150 * np.cos((month - 1) / 12 * 2 * np.pi) + rng.integers(0, 40))
            pre = year < 2012
            rows.append({
                "region": region, "month": f"{year}-{month:02d}-01",
                "modis_cell_days": modis, "viirs_cell_days": 0 if pre else int(modis * 2.5),
                "active_cell_days": modis if pre else int(modis * factor),
                "both_cell_days": 0, "modis_detections": modis * 2, "viirs_detections": 0 if pre else modis * 9,
                "viirs_expected": not pre, "overlap_ok": not pre, "coverage_ok": True,
                "modis_archive_ok": True, "viirs_archive_ok": not pre, "modis_terra_only": False,
            })
    return pd.DataFrame(rows)


def test_fit_recovers_a_known_relationship():
    modis = np.array([10, 50, 100, 400, 800, 1600, 3200, 5000, 100, 300])
    a, b, sigma = fit_log_line(modis, modis * 3)
    value, low, high = predict(np.array([1000]), a, b, sigma)
    assert 2700 < value[0] < 3300
    assert low[0] <= value[0] <= high[0]


def test_prediction_never_below_modis_itself():
    value, low, high = predict(np.array([500]), -3.0, 0.5, 0.2)
    assert value[0] >= 500 and low[0] >= 500


def test_pre_viirs_months_are_scaled_and_labelled():
    result = bridge_monthly(make_monthly())
    early = result[result["month"] < "2012-01-01"]
    assert (early["series_basis"] == "modis_scaled").all()
    assert (early["active_cell_days"] > early["observed_cell_days"] * 2).all()
    assert (result[result["month"] >= "2012-01-01"]["series_basis"] == "combined").all()
    assert (early["estimate_low"] <= early["active_cell_days"]).all()


def test_no_false_jump_at_the_sensor_boundary():
    result = bridge_monthly(make_monthly())
    annual = result.assign(year=pd.to_datetime(result["month"]).dt.year).groupby("year")["active_cell_days"].sum()
    assert abs(annual[2012] / annual[2011] - 1) < 0.2


def test_without_overlap_months_it_refuses_to_guess():
    monthly = make_monthly()
    monthly["overlap_ok"] = False
    result = bridge_monthly(monthly)
    assert not result[result["month"] < "2012-01-01"]["coverage_ok"].any()


def test_tables_without_coverage_columns_pass_through():
    plain = make_monthly().drop(columns=["viirs_expected", "overlap_ok"])
    result = bridge_monthly(plain)
    assert (result["active_cell_days"] == plain["active_cell_days"]).all()


def test_backtest_reports_small_error_on_clean_data():
    report = backtest(make_monthly())
    assert report["backtests"]
    assert report["backtests"][0]["median_absolute_error_pct"] < 25


def test_calendar_marks_estimated_months_and_explains_them():
    cal = build_calendar(make_monthly())
    early = cal[cal["year"] < 2012]
    assert early["estimated"].all() and not cal[cal["year"] >= 2012]["estimated"].any()
    assert "Estimated" in early.iloc[0]["explanation"]
    assert cal[cal["year"] == 2020]["baseline_estimated_n"].max() > 0


def test_terra_only_months_are_explained_not_scored():
    monthly = make_monthly(2001, 2012)
    early = pd.to_datetime(monthly["month"]) < AQUA_FIRST_FULL_MONTH
    monthly.loc[early, ["coverage_ok", "modis_terra_only"]] = [False, True]
    cal = build_calendar(monthly)
    row = cal[(cal["year"] == 2001) & (cal["month"] == 5)].iloc[0]
    assert row["status"] == "incomplete_coverage" and "Terra" in row["explanation"]


def test_archive_coverage_flags_terra_only_and_pre_viirs_months():
    months = pd.Series(pd.to_datetime(["2001-06-01", "2005-06-01", "2012-01-01", "2013-06-01"]))
    covered = {"MODIS_SP": [["2000-11-01", "2026-08-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2026-07-31"]]}
    table = archive_coverage(months, covered, ("Terra", "Aqua", "Suomi-NPP"))
    assert table.loc["2001-06-01", "modis_terra_only"] and not table.loc["2001-06-01", "modis_archive_ok"]
    assert table.loc["2005-06-01", "modis_archive_ok"] and not table.loc["2005-06-01", "viirs_expected"]
    assert table.loc["2012-01-01", "viirs_expected"] and not table.loc["2012-01-01", "viirs_archive_ok"]
    assert table.loc["2013-06-01", "viirs_archive_ok"]
