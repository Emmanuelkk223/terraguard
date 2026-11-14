"""Strategy A harmonization: common grid, common UTC day, sensor-aware index.

The harmonized quantity is **active cell-days**: the number of (UTC day, grid
cell) pairs with at least one detection. A cell-day seen by both MODIS and
VIIRS counts once, so co-located detections are never double-counted and no
event-linking is claimed. Detection counts stay per sensor alongside it.

What this does NOT do: it does not make the sensors equivalent, does not count
unique fires, and does not calibrate FRP or confidence across sensors. See
docs/analysis/MODIS_VIIRS_HARMONIZATION_DESIGN.md.
"""

from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd

HARMONIZATION_VERSION = "A-0.1"
# Constant overpass opportunity across 2012-2025: NOAA-20 (2018) and NOAA-21
# (2023) add overpasses that would raise counts without any change in fire.
STABLE_PLATFORMS = ("Terra", "Aqua", "Suomi-NPP")
CONFIDENCE_RANK = {"low": 0, "nominal": 1, "high": 2}
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQUATOR = 111.32
REFERENCE_LATITUDE = 7.95  # Ghana centre; cells are approximately square there
LOAD_COLUMNS = [
    "latitude", "longitude", "acq_datetime", "sensor", "platform",
    "frp", "confidence_class", "is_presumed_vegetation_fire",
]


def select_observations(
    frame: pd.DataFrame,
    *,
    platforms: tuple[str, ...] | None = STABLE_PLATFORMS,
    min_confidence: str | None = None,
    vegetation_only: bool = False,
) -> pd.DataFrame:
    """Apply configurable platform and quality selection (all optional)."""
    result = frame
    if platforms is not None:
        result = result[result["platform"].isin(platforms)]
    if min_confidence is not None:
        # confidence_class is only comparable within a product; the threshold
        # is applied to each sensor's own class, not to a shared numeric scale.
        rank = result["confidence_class"].map(CONFIDENCE_RANK)
        result = result[rank >= CONFIDENCE_RANK[min_confidence]]
    if vegetation_only:
        result = result[result["is_presumed_vegetation_fire"].fillna(False).astype(bool)]
    return result


def assign_cells(
    frame: pd.DataFrame, cell_size_km: float = 1.0, reference_latitude: float = REFERENCE_LATITUDE
) -> pd.DataFrame:
    """Add integer ``grid_x``/``grid_y`` of a regular equirectangular grid."""
    if cell_size_km <= 0:
        raise ValueError("cell_size_km must be greater than zero")
    km_per_deg_lon = KM_PER_DEG_LON_EQUATOR * np.cos(np.radians(reference_latitude))
    result = frame.copy()
    result["grid_x"] = np.floor(result["longitude"] * km_per_deg_lon / cell_size_km).astype("int32")
    result["grid_y"] = np.floor(result["latitude"] * KM_PER_DEG_LAT / cell_size_km).astype("int32")
    return result


def sensor_cell_days(frame: pd.DataFrame, cell_size_km: float = 1.0) -> pd.DataFrame:
    """Aggregate to one row per (UTC day, cell, sensor), keeping detection counts."""
    cells = assign_cells(frame, cell_size_km)
    cells["date"] = cells["acq_datetime"].dt.floor("D")
    return (
        cells.groupby(["date", "grid_x", "grid_y", "sensor"], observed=True)
        .agg(detections=("acq_datetime", "size"), frp_sum=("frp", "sum"))
        .reset_index()
    )


def harmonized_cell_days(sensor_days: pd.DataFrame) -> pd.DataFrame:
    """One row per occupied (day, cell) with per-sensor counts and provenance."""
    wide = sensor_days.pivot_table(
        index=["date", "grid_x", "grid_y"], columns="sensor",
        values="detections", aggfunc="sum", fill_value=0,
    )
    for sensor in ("MODIS", "VIIRS"):
        if sensor not in wide:
            wide[sensor] = 0
    wide = wide[["MODIS", "VIIRS"]].rename(
        columns={"MODIS": "modis_detections", "VIIRS": "viirs_detections"}
    ).reset_index()
    wide.columns.name = None
    has_modis, has_viirs = wide["modis_detections"] > 0, wide["viirs_detections"] > 0
    wide["occupied_by"] = np.select(
        [has_modis & has_viirs, has_modis, has_viirs], ["both", "MODIS_only", "VIIRS_only"], "none"
    )
    return wide


def monthly_summary(
    cell_days: pd.DataFrame, *, min_coverage: float = 0.8
) -> pd.DataFrame:
    """Monthly index, sensor contributions and an explicit coverage rule.

    ``coverage_ok`` is True only if BOTH sensors have at least one record on
    >= ``min_coverage`` of the calendar days in the month. A day with no
    records is ambiguous (no fire, no overpass, or missing data), so months
    failing the rule must not be compared as if complete.
    """
    frame = cell_days.copy()
    frame["month"] = frame["date"].dt.to_period("M").dt.start_time
    frame["is_both"] = frame["occupied_by"] == "both"
    frame["is_modis_only"] = frame["occupied_by"] == "MODIS_only"
    frame["is_viirs_only"] = frame["occupied_by"] == "VIIRS_only"
    monthly = frame.groupby("month").agg(
        active_cell_days=("occupied_by", "size"),
        both_cell_days=("is_both", "sum"),
        modis_only_cell_days=("is_modis_only", "sum"),
        viirs_only_cell_days=("is_viirs_only", "sum"),
        modis_detections=("modis_detections", "sum"),
        viirs_detections=("viirs_detections", "sum"),
    )
    modis_days = frame[frame["modis_detections"] > 0].groupby("month")["date"].nunique()
    viirs_days = frame[frame["viirs_detections"] > 0].groupby("month")["date"].nunique()
    monthly["modis_days_with_records"] = modis_days.reindex(monthly.index).fillna(0).astype(int)
    monthly["viirs_days_with_records"] = viirs_days.reindex(monthly.index).fillna(0).astype(int)
    monthly = monthly.reset_index()
    monthly["days_in_month"] = monthly["month"].map(
        lambda m: calendar.monthrange(m.year, m.month)[1]
    )
    monthly["modis_cell_days"] = monthly["modis_only_cell_days"] + monthly["both_cell_days"]
    monthly["viirs_cell_days"] = monthly["viirs_only_cell_days"] + monthly["both_cell_days"]
    monthly["agreement_jaccard"] = monthly["both_cell_days"] / monthly["active_cell_days"]
    monthly["raw_viirs_to_modis_ratio"] = monthly["viirs_detections"] / monthly["modis_detections"].replace(0, np.nan)
    monthly["cell_day_viirs_to_modis_ratio"] = monthly["viirs_cell_days"] / monthly["modis_cell_days"].replace(0, np.nan)
    needed = min_coverage * monthly["days_in_month"]
    monthly["coverage_ok"] = (monthly["modis_days_with_records"] >= needed) & (
        monthly["viirs_days_with_records"] >= needed
    )
    return monthly


def harmonize(
    observation_files: list[Path],
    output_dir: Path,
    *,
    cell_sizes_km: tuple[float, ...] = (1.0, 2.0, 5.0),
    platforms: tuple[str, ...] | None = STABLE_PLATFORMS,
    min_confidence: str | None = None,
    vegetation_only: bool = False,
    min_coverage: float = 0.8,
) -> dict[str, object]:
    selected = [
        select_observations(
            pd.read_parquet(path, columns=LOAD_COLUMNS), platforms=platforms,
            min_confidence=min_confidence, vegetation_only=vegetation_only,
        )
        for path in observation_files
    ]
    observations = pd.concat(selected, ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    grids: dict[str, object] = {}
    for size in cell_sizes_km:
        cell_days = harmonized_cell_days(sensor_cell_days(observations, size))
        monthly = monthly_summary(cell_days, min_coverage=min_coverage)
        label = f"{size:g}km"
        cell_days.to_parquet(output_dir / f"cell_days_{label}.parquet", index=False)
        monthly.to_csv(output_dir / f"monthly_{label}.csv", index=False)
        grids[label] = {
            "cell_days": int(len(cell_days)),
            "overall_agreement_jaccard": float((cell_days["occupied_by"] == "both").mean()) if len(cell_days) else None,
        }
    metadata = {
        "harmonization_method": "Strategy A: common grid, UTC day, active cell-days",
        "harmonization_version": HARMONIZATION_VERSION,
        "platforms": list(platforms) if platforms else "all",
        "min_confidence": min_confidence,
        "vegetation_only": vegetation_only,
        "min_coverage": min_coverage,
        "observations_used": int(len(observations)),
        "grids": grids,
        "notes": [
            "Active cell-days are not unique fires; co-detected cell-days count once.",
            "Sensors are not calibrated to each other; FRP and confidence are not harmonized.",
        ],
    }
    (output_dir / "harmonization_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/observations"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/harmonized"))
    parser.add_argument("--cell-sizes-km", type=float, nargs="+", default=[1.0, 2.0, 5.0])
    parser.add_argument("--all-platforms", action="store_true",
                        help="Include NOAA-20/21 (changes constellation over time)")
    parser.add_argument("--min-confidence", choices=list(CONFIDENCE_RANK))
    parser.add_argument("--vegetation-only", action="store_true")
    parser.add_argument("--min-coverage", type=float, default=0.8)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("*.parquet"))
    if not files:
        raise SystemExit(f"No processed parquet files in {args.input_dir}")
    print(json.dumps(harmonize(
        files, args.output_dir, cell_sizes_km=tuple(args.cell_sizes_km),
        platforms=None if args.all_platforms else STABLE_PLATFORMS,
        min_confidence=args.min_confidence, vegetation_only=args.vegetation_only,
        min_coverage=args.min_coverage,
    ), indent=2))


if __name__ == "__main__":
    main()
