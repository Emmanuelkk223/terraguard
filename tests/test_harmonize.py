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
