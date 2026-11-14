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

from . import atomic
from .regions import COUNTRY_NAME, DEFAULT_ADM1, GhanaRegions

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


def _monthly_core(
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


PRODUCT_FOR_PLATFORM = {
    "Terra": "MODIS_SP", "Aqua": "MODIS_SP", "Suomi-NPP": "VIIRS_SNPP_SP",
    "NOAA-20": "VIIRS_NOAA20_SP", "NOAA-21": "VIIRS_NOAA21_SP",
}


def archive_coverage(
    months: pd.Series,
    covered_ranges: dict[str, list[list[str]]],
    platforms: tuple[str, ...] | None,
) -> pd.DataFrame:
    """Per month: is the data archive complete for MODIS and for VIIRS?

    A sensor is complete in a month when every selected product that already
    existed by the end of that month has downloaded windows covering the whole
    month, and at least one such product exists. This separates MISSING DATA
    from genuinely quiet days, which have no detections but are not gaps.
    """
    chosen = set(PRODUCT_FOR_PLATFORM.values()) if platforms is None else {
        PRODUCT_FOR_PLATFORM[p] for p in platforms
    }

    def complete(group: str, month: pd.Timestamp) -> bool:
        start, end = month, month + pd.offsets.MonthEnd(0)
        available, ok = 0, True
        for product in chosen:
            if not product.startswith(group):
                continue
            ranges = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in covered_ranges.get(product, [])]
            if not ranges or min(a for a, _ in ranges) > end:
                continue  # product did not exist yet
            available += 1
            ok &= any(a <= start and b >= end for a, b in ranges)
        return bool(available and ok)

    unique = pd.Series(months.unique())
    table = pd.DataFrame({"month": unique})
    table["modis_archive_ok"] = [complete("MODIS", m) for m in unique]
    table["viirs_archive_ok"] = [complete("VIIRS", m) for m in unique]
    return table.set_index("month")


COUNT_COLUMNS = [
    "active_cell_days", "both_cell_days", "modis_only_cell_days", "viirs_only_cell_days",
    "modis_detections", "viirs_detections", "modis_days_with_records", "viirs_days_with_records",
    "modis_cell_days", "viirs_cell_days",
]


def fill_missing_months(part: pd.DataFrame, months: pd.Series) -> pd.DataFrame:
    """Reindex a monthly table to ``months``, treating absent months as zero activity.

    A month with no detections produces no cell-day rows, so it silently vanishes from a
    group-by. For a region or area that is genuine zero activity (the archive covers the
    month) and must be part of its baseline and calendar, not a gap.
    """
    full_index = pd.Index(pd.Series(months).drop_duplicates().sort_values(), name="month")
    filled = part.set_index("month").reindex(full_index)
    for column in COUNT_COLUMNS:
        if column in filled:
            filled[column] = filled[column].fillna(0).astype("int64")
    return filled.reset_index()


def cell_centres(cells: pd.DataFrame, cell_size_km: float) -> pd.DataFrame:
    """Centre longitude/latitude of grid cells (inverse of ``assign_cells``)."""
    km_per_deg_lon = KM_PER_DEG_LON_EQUATOR * np.cos(np.radians(REFERENCE_LATITUDE))
    result = cells.copy()
    result["longitude"] = (result["grid_x"] + 0.5) * cell_size_km / km_per_deg_lon
    result["latitude"] = (result["grid_y"] + 0.5) * cell_size_km / KM_PER_DEG_LAT
    return result


def add_region(cell_days: pd.DataFrame, cell_size_km: float, regions: GhanaRegions) -> pd.DataFrame:
    """Label each cell with the region containing its centre (nearest if none).

    A cell straddling a border takes one region, so regional totals are
    approximate near borders; national totals are unaffected.
    """
    unique = cell_centres(cell_days[["grid_x", "grid_y"]].drop_duplicates(), cell_size_km)
    unique["region"] = regions.region_for(unique["longitude"].to_numpy(), unique["latitude"].to_numpy())
    return cell_days.merge(unique[["grid_x", "grid_y", "region"]], on=["grid_x", "grid_y"], how="left")


def monthly_summary(
    cell_days: pd.DataFrame,
    *,
    min_coverage: float = 0.8,
    archive: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Monthly summary for all of Ghana plus each region when ``region`` exists.

    With ``archive`` (from :func:`archive_coverage`) a month is complete when both
    sensors' archives cover it. Without it, the weaker days-with-records rule is
    used, which wrongly treats quiet days as gaps and is meant for tests only.
    """
    national = _monthly_core(cell_days, min_coverage=min_coverage)
    if archive is not None:
        national["modis_archive_ok"] = national["month"].map(archive["modis_archive_ok"]).fillna(False).astype(bool)
        national["viirs_archive_ok"] = national["month"].map(archive["viirs_archive_ok"]).fillna(False).astype(bool)
        national["coverage_ok"] = national["modis_archive_ok"] & national["viirs_archive_ok"]
    national.insert(0, "region", COUNTRY_NAME)
    parts = [national]
    # Coverage is judged NATIONALLY: a quiet region legitimately has days with
    # no detections, which says nothing about whether satellites observed it.
    coverage_columns = [c for c in ["modis_days_with_records", "viirs_days_with_records", "days_in_month",
                                    "modis_archive_ok", "viirs_archive_ok", "coverage_ok"] if c in national]
    national_coverage = national.set_index("month")[coverage_columns]
    if "region" in cell_days:
        for name, group in cell_days.groupby("region", sort=True):
            part = fill_missing_months(_monthly_core(group, min_coverage=min_coverage), national["month"])
            for column in coverage_columns:
                part[column] = part["month"].map(national_coverage[column])
            part.insert(0, "region", name)
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def harmonize(
    observation_files: list[Path],
    output_dir: Path,
    *,
    cell_sizes_km: tuple[float, ...] = (1.0, 2.0, 5.0),
    platforms: tuple[str, ...] | None = STABLE_PLATFORMS,
    min_confidence: str | None = None,
    vegetation_only: bool = False,
    min_coverage: float = 0.8,
    regions: GhanaRegions | None = None,
    covered_ranges: dict[str, list[list[str]]] | None = None,
) -> dict[str, object]:
    selected = [
        select_observations(
            pd.read_parquet(path, columns=LOAD_COLUMNS), platforms=platforms,
            min_confidence=min_confidence, vegetation_only=vegetation_only,
        )
        for path in observation_files
    ]
    observations = pd.concat(selected, ignore_index=True)
    outside = 0
    if regions is not None:
        inside = regions.inside_country(observations["longitude"].to_numpy(), observations["latitude"].to_numpy())
        outside = int((~inside).sum())
        observations = observations[inside].reset_index(drop=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    grids: dict[str, object] = {}
    for size in cell_sizes_km:
        cell_days = harmonized_cell_days(sensor_cell_days(observations, size))
        if regions is not None:
            cell_days = add_region(cell_days, size, regions)
        archive = None
        if covered_ranges is not None:
            months = cell_days["date"].dt.to_period("M").dt.start_time
            archive = archive_coverage(months, covered_ranges, platforms)
        monthly = monthly_summary(cell_days, min_coverage=min_coverage, archive=archive)
        label = f"{size:g}km"
        atomic.to_parquet(cell_days, output_dir / f"cell_days_{label}.parquet", index=False)
        atomic.to_csv(monthly, output_dir / f"monthly_{label}.csv", index=False)
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
        "coverage_rule": "archive coverage of every selected product for the whole month" if covered_ranges is not None else "days with records (fallback)",
        "observations_used": int(len(observations)),
        "observations_outside_ghana_excluded": outside,
        "spatial_clip": "union of geoBoundaries ADM1 (simplified)" if regions is not None else "none (bounding box only)",
        "grids": grids,
        "notes": [
            "Active cell-days are not unique fires; co-detected cell-days count once.",
            "Sensors are not calibrated to each other; FRP and confidence are not harmonized.",
        ],
    }
    atomic.write_text(output_dir / "harmonization_metadata.json", json.dumps(metadata, indent=2))
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
    parser.add_argument("--boundary", type=Path, default=DEFAULT_ADM1,
                        help="ADM1 GeoJSON for clipping/regions; pass a missing path to skip")
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("*.parquet"))
    processing_meta = args.input_dir.parent / "metadata.json"
    covered = None
    if processing_meta.exists():
        products = json.loads(processing_meta.read_text(encoding="utf-8")).get("products", {})
        covered = {name: info.get("covered_ranges", []) for name, info in products.items()}
    if not files:
        raise SystemExit(f"No processed parquet files in {args.input_dir}")
    print(json.dumps(harmonize(
        files, args.output_dir, cell_sizes_km=tuple(args.cell_sizes_km),
        platforms=None if args.all_platforms else STABLE_PLATFORMS,
        min_confidence=args.min_confidence, vegetation_only=args.vegetation_only,
        min_coverage=args.min_coverage,
        regions=GhanaRegions(args.boundary) if args.boundary.exists() else None,
        covered_ranges=covered,
    ), indent=2))


if __name__ == "__main__":
    main()
