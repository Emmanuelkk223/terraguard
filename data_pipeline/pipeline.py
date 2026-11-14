"""FIRMS CSV validation, Ghana filtering, and reproducible aggregation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

GHANA_BBOX = (-3.26, 4.74, 1.20, 11.17)  # west, south, east, north
REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "acq_time")
CANONICAL_COLUMNS = (
    "latitude",
    "longitude",
    "acq_datetime",
    "acq_date",
    "acq_time",
    "sensor",
    "satellite",
    "instrument",
    "confidence",
    "frp",
    "source_product",
    "source_file",
)


def load_firms_csv(path: str | Path, source_product: str) -> pd.DataFrame:
    """Load one FIRMS CSV and add provenance without discarding source fields."""
    csv_path = Path(path)
    frame = pd.read_csv(csv_path, dtype={"acq_time": "string"})
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"{csv_path} is missing required FIRMS columns: {missing}")

    frame = frame.copy()
    frame["source_product"] = source_product
    frame["source_file"] = csv_path.name
    frame["sensor"] = sensor_for_product(source_product, frame)
    frame["acq_datetime"] = parse_acquisition_datetime(frame["acq_date"], frame["acq_time"])
    for column in ("latitude", "longitude", "frp"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def sensor_for_product(product: str, frame: pd.DataFrame) -> pd.Series:
    """Return a stable sensor label while retaining the source satellite field."""
    product_upper = product.upper()
    if "MODIS" in product_upper:
        return pd.Series("MODIS", index=frame.index, dtype="string")
    if "VIIRS" in product_upper:
        return pd.Series("VIIRS", index=frame.index, dtype="string")
    if "instrument" in frame:
        return frame["instrument"].astype("string")
    return pd.Series("UNKNOWN", index=frame.index, dtype="string")


def parse_acquisition_datetime(
    dates: Iterable[Any], times: Iterable[Any]
) -> pd.Series:
    """Parse FIRMS date and HHMM acquisition time as UTC-naive timestamps."""
    date_values = pd.Series(dates, copy=False).astype("string").str.strip()
    time_values = (
        pd.Series(times, copy=False)
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(4)
    )
    return pd.to_datetime(
        date_values + " " + time_values.str.slice(0, 2) + ":" + time_values.str.slice(2, 4),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None)


def validate_observations(
    frame: pd.DataFrame, *, drop_duplicates: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate observations and return ``(valid, exclusions)``.

    The exclusions table contains one row per rejected record and a machine-
    readable reason. Valid unusual values are retained; only invalid required
    fields and exact duplicate records are excluded.
    """
    if frame.empty:
        return frame.copy(), pd.DataFrame(columns=["row_index", "reason"])

    working = frame.copy()
    if "acq_datetime" not in working:
        working["acq_datetime"] = parse_acquisition_datetime(
            working["acq_date"], working["acq_time"]
        )
    for column in ("latitude", "longitude", "frp"):
        if column in working:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    reasons = pd.Series(pd.NA, index=working.index, dtype="string")
    rules = (
        ("invalid_latitude", working["latitude"].isna() | ~working["latitude"].between(-90, 90)),
        ("invalid_longitude", working["longitude"].isna() | ~working["longitude"].between(-180, 180)),
        ("invalid_acquisition_datetime", working["acq_datetime"].isna()),
    )
    for reason, invalid in rules:
        reasons = reasons.mask(reasons.isna() & invalid, reason)

    invalid_mask = reasons.notna()
    exclusions = pd.DataFrame(
        {"row_index": working.index[invalid_mask], "reason": reasons[invalid_mask].to_numpy()}
    )
    valid = working.loc[~invalid_mask].copy()

    if drop_duplicates and not valid.empty:
        duplicate_columns = [
            column
            for column in (
                "latitude",
                "longitude",
                "acq_datetime",
                "satellite",
                "instrument",
                "source_product",
            )
            if column in valid
        ]
        duplicate_mask = valid.duplicated(subset=duplicate_columns, keep="first")
        duplicate_rows = valid.loc[duplicate_mask]
        if not duplicate_rows.empty:
            exclusions = pd.concat(
                [
                    exclusions,
                    pd.DataFrame(
                        {
                            "row_index": duplicate_rows.index,
                            "reason": "duplicate_observation",
                        }
                    ),
                ],
                ignore_index=True,
            )
            valid = valid.loc[~duplicate_mask].copy()

    return valid.reset_index(drop=True), exclusions.reset_index(drop=True)


def load_geojson_geometry(path: str | Path) -> list[list[tuple[float, float]]]:
    """Load Polygon/MultiPolygon rings as ``(longitude, latitude)`` tuples."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    geometries: list[dict[str, Any]] = []
    if payload.get("type") == "FeatureCollection":
        geometries = [
            feature["geometry"]
            for feature in payload.get("features", [])
            if feature.get("geometry")
        ]
    elif payload.get("type") == "Feature":
        geometries = [payload["geometry"]]
    else:
        geometries = [payload]

    rings: list[list[tuple[float, float]]] = []
    for geometry in geometries:
        if geometry["type"] == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geometry["type"] == "MultiPolygon":
            polygons = [polygon for polygon in geometry["coordinates"]]
        else:
            raise ValueError(f"Unsupported boundary geometry: {geometry['type']}")
        rings.extend(
            [
                [
                    (float(point[0]), float(point[1]))
                    for point in polygon[0]
                ]
                for polygon in polygons
                if polygon
            ]
        )
    return rings


def _point_in_ring(longitude: float, latitude: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[index - 1]
        intersects = (y1 > latitude) != (y2 > latitude)
        if intersects and longitude < (x2 - x1) * (latitude - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def filter_to_boundary(
    frame: pd.DataFrame,
    boundary_rings: list[list[tuple[float, float]]],
    *,
    bbox: tuple[float, float, float, float] = GHANA_BBOX,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter valid observations to a boundary after a Ghana bounding-box check."""
    west, south, east, north = bbox
    in_bbox = (
        frame["longitude"].between(west, east)
        & frame["latitude"].between(south, north)
    )
    in_boundary = pd.Series(False, index=frame.index)
    for index, row in frame.loc[in_bbox].iterrows():
        in_boundary.loc[index] = any(
            _point_in_ring(float(row["longitude"]), float(row["latitude"]), ring)
            for ring in boundary_rings
        )
    retained = frame.loc[in_boundary].copy().reset_index(drop=True)
    exclusions = frame.loc[~in_boundary].copy()
    exclusions = pd.DataFrame(
        {"row_index": exclusions.index, "reason": "outside_ghana_boundary"}
    )
    return retained, exclusions.reset_index(drop=True)


def add_temporal_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["observation_date"] = result["acq_datetime"].dt.date.astype("string")
    result["week_start"] = (
        result["acq_datetime"].dt.to_period("W-SUN").dt.start_time.dt.date.astype("string")
    )
    result["month"] = result["acq_datetime"].dt.to_period("M").astype("string")
    return result


def add_grid_cell(
    frame: pd.DataFrame, *, cell_size_km: float = 5.0, reference_latitude: float = 7.95
) -> pd.DataFrame:
    """Assign an equirectangular grid cell; retain original coordinates."""
    if cell_size_km <= 0:
        raise ValueError("cell_size_km must be greater than zero")
    result = frame.copy()
    km_per_degree_lon = 111.32 * math.cos(math.radians(reference_latitude))
    result["grid_x"] = (
        result["longitude"] * km_per_degree_lon / cell_size_km
    ).apply(math.floor)
    result["grid_y"] = (result["latitude"] * 110.574 / cell_size_km).apply(math.floor)
    result["cell_id"] = "grid_" + result["grid_x"].astype(str) + "_" + result["grid_y"].astype(str)
    return result


def aggregate_observations(
    frame: pd.DataFrame,
    *,
    period: str = "week",
    cell_size_km: float | None = 5.0,
) -> pd.DataFrame:
    """Aggregate observation counts and FRP by period and sensor."""
    if frame.empty:
        return pd.DataFrame()
    result = add_temporal_columns(frame)
    if cell_size_km is not None:
        result = add_grid_cell(result, cell_size_km=cell_size_km)
        group_columns = ["cell_id", "sensor"]
    else:
        group_columns = ["sensor"]
    period_column = {"day": "observation_date", "week": "week_start", "month": "month"}.get(period)
    if period_column is None:
        raise ValueError("period must be one of: day, week, month")
    group_columns.insert(0, period_column)
    aggregated = (
        result.groupby(group_columns, dropna=False)
        .agg(
            observation_count=("acq_datetime", "size"),
            frp_sum=("frp", "sum"),
            frp_mean=("frp", "mean"),
            latitude_mean=("latitude", "mean"),
            longitude_mean=("longitude", "mean"),
        )
        .reset_index()
        .sort_values(group_columns)
        .reset_index(drop=True)
    )
    return aggregated


def canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Return common fields first while retaining all original source columns."""
    ordered = [column for column in CANONICAL_COLUMNS if column in frame]
    remaining = [column for column in frame.columns if column not in ordered]
    return frame[ordered + remaining]
