"""On-demand analytics for any sensor view, region or custom bounding box.

Everything is derived from the harmonized cell-day table with the same code paths
as the precomputed national and regional calendars, so numbers stay consistent.

Sensor views:
  harmonized  active cell-days seen by either sensor (the default index)
  modis       cell-days seen by MODIS (Terra + Aqua)
  viirs       cell-days seen by VIIRS (the selected VIIRS platforms)
A single-sensor view uses that sensor's own archive coverage, so, for example,
January 2012 is complete for MODIS even though VIIRS only began on 20 January.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .calendar_analytics import build_calendar
from .harmonize import (
    KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR, REFERENCE_LATITUDE, fill_missing_months, monthly_summary,
)

VIEW_COLUMN = {"harmonized": "active_cell_days", "modis": "modis_cell_days", "viirs": "viirs_cell_days"}
CUSTOM_LABEL = "Custom area"
COVERAGE_COLUMNS = ["modis_days_with_records", "viirs_days_with_records", "days_in_month",
                    "modis_archive_ok", "viirs_archive_ok", "coverage_ok"]
MAX_DAILY_DAYS = 1100


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """Parse ``west,south,east,north`` in degrees and validate it."""
    try:
        west, south, east, north = (float(part) for part in text.split(","))
    except ValueError as exc:
        raise ValueError("bbox must be four numbers: west,south,east,north") from exc
    if not (-180 <= west < east <= 180):
        raise ValueError("bbox longitudes must satisfy -180 <= west < east <= 180")
    if not (-90 <= south < north <= 90):
        raise ValueError("bbox latitudes must satisfy -90 <= south < north <= 90")
    return west, south, east, north


def cell_centre_coordinates(frame: pd.DataFrame, cell_size_km: float) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude of each row's grid-cell centre."""
    km_per_deg_lon = KM_PER_DEG_LON_EQUATOR * np.cos(np.radians(REFERENCE_LATITUDE))
    lon = (frame["grid_x"].to_numpy() + 0.5) * cell_size_km / km_per_deg_lon
    lat = (frame["grid_y"].to_numpy() + 0.5) * cell_size_km / KM_PER_DEG_LAT
    return lon, lat


def select_cells(
    cell_days: pd.DataFrame, cell_size_km: float, *, region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """Rows inside a region (by label) or a bounding box (by cell centre)."""
    frame = cell_days
    if bbox is not None:
        west, south, east, north = bbox
        lon, lat = cell_centre_coordinates(frame, cell_size_km)
        frame = frame[(lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)]
    elif region and region != "Ghana":
        frame = frame[frame["region"] == region]
    return frame


def _zero_monthly(months: pd.Series) -> pd.DataFrame:
    zero = pd.DataFrame({"month": pd.Series(months).drop_duplicates().sort_values()})
    for column in ("active_cell_days", "both_cell_days", "modis_only_cell_days", "viirs_only_cell_days",
                   "modis_detections", "viirs_detections", "modis_days_with_records",
                   "viirs_days_with_records", "modis_cell_days", "viirs_cell_days"):
        zero[column] = 0
    return zero


def area_monthly(
    cell_days: pd.DataFrame, cell_size_km: float, national_monthly: pd.DataFrame, *,
    region: str | None = None, bbox: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """Monthly table for a region or bounding box, aligned to the national months.

    ``national_monthly`` is the national (region == Ghana) monthly table, which
    supplies the month list and the archive-coverage flags (coverage is a property
    of the data archive, not of the area).
    """
    national = national_monthly[national_monthly["region"] == "Ghana"]
    selected = select_cells(cell_days, cell_size_km, region=region, bbox=bbox)
    if selected.empty:
        monthly = _zero_monthly(national["month"])
    else:
        core = monthly_summary(selected.drop(columns=["region"], errors="ignore"))
        monthly = fill_missing_months(core.drop(columns=["region"]), national["month"])
    coverage = national.set_index("month")
    for column in COVERAGE_COLUMNS:
        if column in coverage:
            monthly[column] = monthly["month"].map(coverage[column])
    monthly["month"] = pd.to_datetime(monthly["month"])
    monthly.insert(0, "region", CUSTOM_LABEL if bbox is not None else (region or "Ghana"))
    return monthly


def apply_view(monthly: pd.DataFrame, view: str) -> pd.DataFrame:
    """Make ``active_cell_days`` the value of the chosen sensor view, with that view's coverage."""
    if view not in VIEW_COLUMN:
        raise ValueError(f"view must be one of {sorted(VIEW_COLUMN)}")
    result = monthly.copy()
    result["active_cell_days"] = result[VIEW_COLUMN[view]]
    archive = f"{view}_archive_ok"
    if view != "harmonized" and archive in result:
        result["coverage_ok"] = result[archive].astype(bool)
    result["view"] = view
    return result


def area_calendar(
    cell_days: pd.DataFrame, cell_size_km: float, national_monthly: pd.DataFrame, *,
    view: str = "harmonized", region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None, min_samples: int = 5,
) -> pd.DataFrame:
    monthly = apply_view(area_monthly(cell_days, cell_size_km, national_monthly, region=region, bbox=bbox), view)
    monthly["month"] = monthly["month"].dt.strftime("%Y-%m-%d")
    calendar = build_calendar(monthly, min_samples=min_samples)
    calendar["view"] = view
    return calendar


def activity_series(
    selected: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, interval: str, view: str = "harmonized",
) -> pd.DataFrame:
    """Daily or weekly cell-day counts between ``start`` and ``end`` (inclusive, UTC dates)."""
    if interval not in ("day", "week"):
        raise ValueError("interval must be 'day' or 'week'")
    if end < start:
        raise ValueError("end must not be earlier than start")
    days = pd.date_range(start, end, freq="D")
    if interval == "day" and len(days) > MAX_DAILY_DAYS:
        raise ValueError(f"daily series is limited to {MAX_DAILY_DAYS} days; use weekly for longer ranges")
    frame = selected[(selected["date"] >= start) & (selected["date"] <= end)]
    flags = pd.DataFrame({
        "date": frame["date"], "harmonized_cell_days": 1,
        "modis_cell_days": (frame["modis_detections"] > 0).astype(int),
        "viirs_cell_days": (frame["viirs_detections"] > 0).astype(int),
        "both_cell_days": (frame["occupied_by"] == "both").astype(int),
        "modis_detections": frame["modis_detections"], "viirs_detections": frame["viirs_detections"],
    })
    daily = flags.groupby("date").sum().reindex(days, fill_value=0)
    daily.index.name = "period_start"
    if interval == "week":
        weeks = daily.index.to_period("W-SUN").start_time
        daily = daily.groupby(weeks).sum()
        daily.index.name = "period_start"
        span = pd.Timedelta(days=6)
    else:
        span = pd.Timedelta(days=0)
    result = daily.reset_index()
    result["period_end"] = result["period_start"] + span
    result["value"] = result[VIEW_COLUMN[view].replace("active_cell_days", "harmonized_cell_days")]
    for column in ("period_start", "period_end"):
        result[column] = result[column].dt.strftime("%Y-%m-%d")
    return result
