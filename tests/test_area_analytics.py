"""Tests for sensor views, bounding boxes and daily/weekly series.

Fixtures are tiny hand-written TEST DATA pushed through the real pipeline functions.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.area_analytics import (
    activity_series, apply_view, area_calendar, area_monthly, parse_bbox, select_cells,
)
from data_pipeline.calendar_analytics import build_calendar
from data_pipeline.harmonize import archive_coverage, harmonized_cell_days, monthly_summary, sensor_cell_days

COVERED = {"MODIS_SP": [["2012-01-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-12-31"]]}
PLATFORMS = ("Terra", "Aqua", "Suomi-NPP")


def _observations() -> pd.DataFrame:
    rows = []
    for year in range(2013, 2021):
        for month in (1, 2, 7):
            n_north = 4 + (year % 3) + (100 if (year == 2018 and month == 1) else 0)
            for i in range(n_north):  # northern cells, both sensors
                stamp = f"{year}-{month:02d}-10 02:04"
                rows.append((9.0 + i * 0.1, -1.0, stamp, "MODIS", "Aqua", 5.0, "nominal", True))
                rows.append((9.0 + i * 0.1, -1.0, stamp.replace("02:04", "13:30"), "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
            if month != 7:  # southern region is silent in July: zero, not missing
                rows.append((5.6, -0.2, f"{year}-{month:02d}-12 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
    obs = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform",
                                      "frp", "confidence_class", "is_presumed_vegetation_fire"])
    obs["acq_datetime"] = pd.to_datetime(obs["acq_datetime"])
    return obs


@pytest.fixture(scope="module")
def tables():
    cell_days = harmonized_cell_days(sensor_cell_days(_observations(), 5.0))
    cell_days["region"] = ["South" if y < 140 else "North" for y in cell_days["grid_y"]]
    months = cell_days["date"].dt.to_period("M").dt.start_time
    archive = archive_coverage(months, COVERED, PLATFORMS)
    monthly = monthly_summary(cell_days, archive=archive)
    return cell_days, monthly


def test_parse_bbox_validates_input() -> None:
    assert parse_bbox("-3.3,4.7,1.2,11.2") == (-3.3, 4.7, 1.2, 11.2)
    for bad in ("1,2,3", "a,b,c,d", "5,0,1,10", "0,10,1,5", "-200,0,1,1", "0,0,1,95"):
        with pytest.raises(ValueError):
            parse_bbox(bad)


def test_select_cells_by_region_and_bbox(tables) -> None:
    cell_days, _ = tables
    north = select_cells(cell_days, 5.0, region="North")
    assert set(north["region"]) == {"North"} and len(north) < len(cell_days)
    boxed = select_cells(cell_days, 5.0, bbox=(-3.0, 8.0, 1.0, 25.0))
    assert set(boxed["region"]) == {"North"}
    assert select_cells(cell_days, 5.0, bbox=(10.0, 40.0, 11.0, 41.0)).empty


def test_on_demand_region_calendar_matches_precomputed_pipeline(tables) -> None:
    """Consistency: the on-demand path must reproduce the precomputed regional calendar."""
    cell_days, monthly = tables
    precomputed = build_calendar(monthly[monthly["region"] == "North"])
    on_demand = area_calendar(cell_days, 5.0, monthly, region="North")
    keys = ["year", "month"]
    a = precomputed.set_index(keys)[["active_cell_days", "status", "baseline_median", "coverage_ok"]]
    b = on_demand.set_index(keys)[["active_cell_days", "status", "baseline_median", "coverage_ok"]]
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())


def test_bbox_area_includes_zero_months_and_flags_the_outlier(tables) -> None:
    cell_days, monthly = tables
    cal = area_calendar(cell_days, 5.0, monthly, bbox=(-3.0, 8.0, 1.0, 25.0))
    assert (cal["region"] == "Custom area").all()
    assert len(cal) == monthly[monthly["region"] == "Ghana"]["month"].nunique()
    flagged = cal[cal["status"] == "unusually_high"]
    assert set(zip(flagged["year"], flagged["month"])) == {(2018, 1)}
    south = area_calendar(cell_days, 5.0, monthly, bbox=(-1.0, 5.0, 1.0, 6.0))
    july = south[south["month"] == 7]
    assert (july["active_cell_days"] == 0).all() and len(july) == 8  # zero, present, and counted in the baseline


def test_empty_bbox_gives_zero_calendar_not_an_error(tables) -> None:
    cell_days, monthly = tables
    cal = area_calendar(cell_days, 5.0, monthly, bbox=(10.0, 40.0, 11.0, 41.0))
    assert (cal["active_cell_days"] == 0).all() and len(cal) > 0


def test_single_sensor_views_use_their_own_value_and_coverage(tables) -> None:
    cell_days, monthly = tables
    modis = apply_view(area_monthly(cell_days, 5.0, monthly, region="North"), "modis")
    assert (modis["active_cell_days"] == modis["modis_cell_days"]).all()
    viirs = apply_view(area_monthly(cell_days, 5.0, monthly, region="North"), "viirs")
    assert (viirs["active_cell_days"] == viirs["viirs_cell_days"]).all()
    harmonized = apply_view(area_monthly(cell_days, 5.0, monthly, region="North"), "harmonized")
    assert harmonized["active_cell_days"].sum() >= max(modis["active_cell_days"].sum(), viirs["active_cell_days"].sum())
    with pytest.raises(ValueError):
        apply_view(modis, "radar")
    january_2012 = area_calendar(cell_days, 5.0, monthly, view="modis", region="North")
    assert (january_2012["view"] == "modis").all()


def test_daily_and_weekly_series(tables) -> None:
    cell_days, _ = tables
    start, end = pd.Timestamp("2018-01-01"), pd.Timestamp("2018-01-31")
    daily = activity_series(cell_days, start, end, "day")
    assert len(daily) == 31 and daily["harmonized_cell_days"].sum() > 0
    assert daily.loc[daily["period_start"] == "2018-01-03", "harmonized_cell_days"].iloc[0] == 0  # quiet day is a zero row
    weekly = activity_series(cell_days, start, end, "week")
    assert weekly["harmonized_cell_days"].sum() == daily["harmonized_cell_days"].sum()  # same totals, coarser grain
    assert weekly["period_start"].iloc[0] == "2018-01-01"  # Monday
    only_viirs = activity_series(cell_days, start, end, "day", view="viirs")
    assert only_viirs["value"].sum() == daily["viirs_cell_days"].sum()
    with pytest.raises(ValueError):
        activity_series(cell_days, start, pd.Timestamp("2025-12-31"), "day")  # too long for daily
    with pytest.raises(ValueError):
        activity_series(cell_days, end, start, "day")
