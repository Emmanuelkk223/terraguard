"""Tests for Strategy A harmonization.

All rows are tiny hand-written TEST FIXTURES that exercise code logic. They
are not NASA measurements and support no scientific conclusion.
"""

from __future__ import annotations

import pandas as pd
import pytest

from data_pipeline.harmonize import (
    assign_cells, harmonized_cell_days, monthly_summary, select_observations, sensor_cell_days,
)


def _obs(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["latitude", "longitude", "acq_datetime", "sensor", "platform",
                 "frp", "confidence_class", "is_presumed_vegetation_fire"],
    ).assign(acq_datetime=lambda d: pd.to_datetime(d["acq_datetime"]))


def test_nearby_points_share_a_cell_and_far_points_do_not() -> None:
    frame = pd.DataFrame({"latitude": [7.0000, 7.0010, 7.5], "longitude": [-1.0000, -1.0010, -1.0]})
    cells = assign_cells(frame, 1.0)
    assert cells.loc[0, ["grid_x", "grid_y"]].tolist() == cells.loc[1, ["grid_x", "grid_y"]].tolist()
    assert cells.loc[0, "grid_y"] != cells.loc[2, "grid_y"]
    with pytest.raises(ValueError):
        assign_cells(frame, 0)


def test_cell_day_counts_once_when_both_sensors_detect() -> None:
    obs = _obs([
        (7.0, -1.0, "2024-01-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True),
        (7.0, -1.0, "2024-01-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True),
        (7.0, -1.0, "2024-01-10 13:31", "VIIRS", "Suomi-NPP", 1.2, "high", True),  # 2 VIIRS pixels, same cell
        (7.5, -1.0, "2024-01-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "low", True),
    ])
    cell_days = harmonized_cell_days(sensor_cell_days(obs, 1.0))
    assert len(cell_days) == 2  # co-detection is one cell-day, not two
    both = cell_days[cell_days["occupied_by"] == "both"].iloc[0]
    assert (both["modis_detections"], both["viirs_detections"]) == (1, 2)  # per-sensor counts preserved
    assert (cell_days["occupied_by"] == "VIIRS_only").sum() == 1


def test_utc_day_assignment_uses_date_of_acquisition() -> None:
    obs = _obs([
        (7.0, -1.0, "2024-01-10 23:59", "MODIS", "Terra", 5.0, "nominal", True),
        (7.0, -1.0, "2024-01-11 00:01", "MODIS", "Terra", 5.0, "nominal", True),
    ])
    days = sensor_cell_days(obs, 1.0)["date"].dt.strftime("%Y-%m-%d").tolist()
    assert sorted(days) == ["2024-01-10", "2024-01-11"]


def test_selection_filters_are_configurable_and_stable_by_default() -> None:
    obs = _obs([
        (7.0, -1.0, "2024-01-10 02:04", "MODIS", "Aqua", 5.0, "low", True),
        (7.0, -1.0, "2024-01-10 02:04", "VIIRS", "NOAA-20", 1.0, "high", True),
        (7.0, -1.0, "2024-01-10 02:04", "VIIRS", "Suomi-NPP", 1.0, "nominal", False),
    ])
    assert set(select_observations(obs)["platform"]) == {"Aqua", "Suomi-NPP"}  # NOAA-20 excluded
    assert len(select_observations(obs, platforms=None)) == 3
    assert set(select_observations(obs, platforms=None, min_confidence="nominal")["platform"]) == {"NOAA-20", "Suomi-NPP"}
    assert len(select_observations(obs, platforms=None, vegetation_only=True)) == 2


def test_monthly_summary_flags_insufficient_coverage() -> None:
    obs = _obs([
        (7.0, -1.0, "2024-01-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True),
        (7.0, -1.0, "2024-01-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True),
        (7.5, -1.0, "2024-01-11 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True),
    ])
    monthly = monthly_summary(harmonized_cell_days(sensor_cell_days(obs, 1.0)))
    row = monthly.iloc[0]
    assert row["active_cell_days"] == 2 and row["both_cell_days"] == 1
    assert row["agreement_jaccard"] == 0.5
    assert row["days_in_month"] == 31 and row["viirs_days_with_records"] == 2
    assert not row["coverage_ok"]  # 2 of 31 days is not a complete month


def test_regional_coverage_follows_national_coverage() -> None:
    """A quiet region with few detection days must not be marked incomplete by itself."""
    rows = []
    for day in range(1, 29):  # national records every day of Feb 2024 from both sensors
        stamp = f"2024-02-{day:02d} 10:00"
        rows.append((7.0, -1.0, stamp, "MODIS", "Aqua", 5.0, "nominal", True))
        rows.append((7.0, -1.0, stamp, "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
    rows.append((5.6, -0.2, "2024-02-05 10:00", "MODIS", "Aqua", 5.0, "nominal", True))  # quiet region: 1 day
    cell_days = harmonized_cell_days(sensor_cell_days(_obs(rows), 5.0))
    # lat 5.6 -> grid_y ~123 (the single-day cell); lat 7.0 -> grid_y ~154
    cell_days["region"] = ["Quiet" if y < 140 else "Busy" for y in cell_days["grid_y"]]
    assert set(cell_days["region"]) == {"Quiet", "Busy"}
    assert len(cell_days[cell_days["region"] == "Quiet"]) == 1  # only one day of detections
    monthly = monthly_summary(cell_days)
    quiet = monthly[monthly["region"] == "Quiet"].iloc[0]
    assert quiet["modis_days_with_records"] == 28 and bool(quiet["coverage_ok"])  # taken from national
    assert bool(monthly[monthly["region"] == "Ghana"].iloc[0]["coverage_ok"])


def test_archive_coverage_separates_missing_data_from_quiet_days() -> None:
    from data_pipeline.harmonize import archive_coverage

    covered = {
        "MODIS_SP": [["2012-01-01", "2012-03-31"]],
        "VIIRS_SNPP_SP": [["2012-01-20", "2012-02-29"]],  # product starts 20 Jan; ends 29 Feb
    }
    months = pd.Series(pd.to_datetime(["2012-01-01", "2012-02-01", "2012-03-01"]))
    table = archive_coverage(months, covered, ("Terra", "Aqua", "Suomi-NPP"))
    assert table.loc["2012-01-01", "viirs_archive_ok"] is False or not table.loc["2012-01-01", "viirs_archive_ok"]  # starts mid-month
    assert bool(table.loc["2012-02-01", "modis_archive_ok"]) and bool(table.loc["2012-02-01", "viirs_archive_ok"])
    assert not table.loc["2012-03-01", "viirs_archive_ok"]  # VIIRS files stop before month end
    assert bool(table.loc["2012-03-01", "modis_archive_ok"])


def test_monthly_summary_uses_archive_not_quiet_days() -> None:
    from data_pipeline.harmonize import archive_coverage

    obs = _obs([  # a single detection day each: quiet month, but archive is complete
        (7.0, -1.0, "2024-06-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True),
        (7.0, -1.0, "2024-06-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True),
    ])
    cell_days = harmonized_cell_days(sensor_cell_days(obs, 1.0))
    months = cell_days["date"].dt.to_period("M").dt.start_time
    covered = {"MODIS_SP": [["2024-01-01", "2024-12-31"]], "VIIRS_SNPP_SP": [["2024-01-01", "2024-12-31"]]}
    archive = archive_coverage(months, covered, ("Terra", "Aqua", "Suomi-NPP"))
    assert bool(monthly_summary(cell_days, archive=archive).iloc[0]["coverage_ok"])
    assert not monthly_summary(cell_days).iloc[0]["coverage_ok"]  # fallback rule would call it a gap


def test_region_months_without_detections_are_zero_not_missing() -> None:
    """A quiet region must have a zero row for months where only other regions had detections."""
    from data_pipeline.harmonize import fill_missing_months

    rows = [
        (7.0, -1.0, "2024-01-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True),   # busy region, January
        (7.0, -1.0, "2024-02-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True),   # busy region, February
        (5.6, -0.2, "2024-01-12 02:04", "MODIS", "Aqua", 5.0, "nominal", True),   # quiet region, January only
    ]
    cell_days = harmonized_cell_days(sensor_cell_days(_obs(rows), 5.0))
    cell_days["region"] = ["Quiet" if y < 140 else "Busy" for y in cell_days["grid_y"]]
    monthly = monthly_summary(cell_days)
    quiet = monthly[monthly["region"] == "Quiet"].sort_values("month")
    national = monthly[monthly["region"] == "Ghana"]
    assert len(quiet) == len(national) == 2  # February exists for Quiet, with zero activity
    assert quiet.iloc[1]["active_cell_days"] == 0 and quiet.iloc[0]["active_cell_days"] == 1
    assert quiet["days_in_month"].notna().all()
    filled = fill_missing_months(national.iloc[:1].drop(columns="region"), national["month"])
    assert len(filled) == 2
