"""West Africa extension: the same harmonization, country by country, on a 5 km grid.

Ghana keeps its own full-detail pipeline (``run_all.py``: 1, 2 and 5 km grids, 16 regions). This module repeats the
method for all sixteen West African countries so the dashboard can show any of them, Ghana included, on the same
5 km grid. Raw files are read in month-sized pieces so memory stays bounded for the ~38 million detections.

Outputs (under ``data/processed/wa``):
  observations/<product>/<yyyy-mm>.parquet   one clean detection table per product and month (for hotspot downloads)
  work/agg_*.parquet                         per-month cell-day counts by country (intermediate)
  harmonized/cell_days_5km.parquet           one row per occupied (day, cell), region = country
  harmonized/monthly_5km.csv                 monthly summary: "West Africa" plus each country
  analytics/calendar_5km.csv, ...            the calendar analytics (same code as Ghana)
  metadata.json                              counts, exclusions and covered date ranges

A cell takes the country that holds most of its detections, so country totals add up to the West Africa total and
cells that straddle a border are approximate (the same convention Ghana uses for its regions).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import atomic
from .calendar_analytics import run as run_analytics
from .countries import DEFAULT_BOUNDARIES, ORDER, REGION_NAME, Countries
from .harmonize import (
    COUNT_COLUMNS, STABLE_PLATFORMS, archive_coverage, assign_cells, fill_missing_months, harmonized_cell_days,
    monthly_summary, select_observations,
)
from .pipeline import add_derived_fields, canonicalize, load_firms_csv, validate_observations
from .process import covered_ranges, group_files_by_product

CELL_KM = 5.0
KEEP = ["acq_datetime", "latitude", "longitude", "sensor", "satellite", "platform", "confidence",
        "confidence_class", "frp", "daynight", "source_product", "country"]


def month_groups(files: list[Path]) -> dict[str, list[Path]]:
    """Group raw 5-day files by the month in which their window starts."""
    groups: dict[str, list[Path]] = {}
    for path in files:
        start = path.stem.split("_")[-2]
        groups.setdefault(start[:7], []).append(path)
    return dict(sorted(groups.items()))


def process_group(files: list[Path], product: str, countries: Countries) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Clean one month of raw files; return (detections, per-day cell counts, statistics)."""
    loaded = pd.concat([load_firms_csv(p, product) for p in files], ignore_index=True)
    valid, exclusions = validate_observations(loaded)
    frame = canonicalize(add_derived_fields(valid))
    frame["confidence"] = frame["confidence"].astype("string")
    frame["country"] = countries.country_for(frame["longitude"].to_numpy(), frame["latitude"].to_numpy())
    outside = int((frame["country"] == "").sum())
    frame = frame[frame["country"] != ""].reset_index(drop=True)
    cells = assign_cells(frame, CELL_KM)
    cells["date"] = cells["acq_datetime"].dt.floor("D")
    cells["steady"] = cells["platform"].isin(STABLE_PLATFORMS)
    agg = (cells.groupby(["date", "grid_x", "grid_y", "sensor", "country"], observed=True)
           .agg(detections=("steady", "size"), steady_detections=("steady", "sum")).reset_index())
    stats = {
        "loaded": int(len(loaded)), "invalid_or_duplicate": int(len(exclusions)),
        "outside_the_sixteen_countries": outside, "kept": int(len(frame)),
        "by_country": {str(k): int(v) for k, v in frame["country"].value_counts().items()},
        "by_platform": {str(k): int(v) for k, v in frame["platform"].value_counts().items()},
        "exclusions_by_reason": {str(k): int(v) for k, v in exclusions["reason"].value_counts().items()} if len(exclusions) else {},
        "first": frame["acq_datetime"].min().isoformat() if len(frame) else None,
        "last": frame["acq_datetime"].max().isoformat() if len(frame) else None,
    }
    return frame[KEEP], agg, stats


def build_mapping(work_dir: Path) -> pd.DataFrame:
    """The country of each cell: the one with most of its detections over the whole record."""
    parts = []
    for path in sorted(work_dir.glob("agg_*.parquet")):
        agg = pd.read_parquet(path, columns=["grid_x", "grid_y", "country", "detections"])
        parts.append(agg.groupby(["grid_x", "grid_y", "country"], observed=True)["detections"].sum().reset_index())
    totals = pd.concat(parts, ignore_index=True).groupby(["grid_x", "grid_y", "country"], observed=True)["detections"].sum().reset_index()
    winner = totals.sort_values("detections", ascending=False).drop_duplicates(["grid_x", "grid_y"])
    return winner[["grid_x", "grid_y", "country"]].rename(columns={"country": "region"}).reset_index(drop=True)


def complete_regions(monthly: pd.DataFrame, national_name: str) -> pd.DataFrame:
    """Every region gets every month: a month with no detections is zero activity, not a gap."""
    national = monthly[monthly["region"] == national_name]
    months = national["month"]
    coverage = [c for c in monthly.columns if c not in COUNT_COLUMNS and c not in ("region", "month")]
    pieces = [national]
    for name, part in monthly[monthly["region"] != national_name].groupby("region", sort=False):
        filled = fill_missing_months(part.drop(columns=["region"]), months)
        for column in coverage:
            filled[column] = filled["month"].map(national.set_index("month")[column])
        filled.insert(0, "region", name)
        pieces.append(filled)
    return pd.concat(pieces, ignore_index=True)


def run(raw_dir: Path, output_dir: Path, boundaries: Path = DEFAULT_BOUNDARIES, *, limit_months: int | None = None) -> dict:
    countries = Countries(boundaries)
    obs_dir, work_dir, harm_dir = output_dir / "observations", output_dir / "work", output_dir / "harmonized"
    for folder in (obs_dir, work_dir, harm_dir, output_dir / "analytics"):
        folder.mkdir(parents=True, exist_ok=True)
    groups = group_files_by_product(raw_dir)
    covered = {product: covered_ranges(files) for product, files in groups.items()}
    totals: dict[str, dict] = {}
    done = 0
    for product, files in groups.items():
        (obs_dir / product).mkdir(exist_ok=True)
        stats_path = work_dir / f"stats_{product}.json"
        product_stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
        for month, month_files in month_groups(files).items():
            out_obs, out_agg = obs_dir / product / f"{month}.parquet", work_dir / f"agg_{product}_{month}.parquet"
            signature = len(month_files)
            if out_obs.exists() and out_agg.exists() and product_stats.get(month, {}).get("files") == signature:
                continue  # already processed with the same inputs
            frame, agg, stats = process_group(month_files, product, countries)
            atomic.to_parquet(frame, out_obs, index=False)
            atomic.to_parquet(agg, out_agg, index=False)
            stats["files"] = signature
            product_stats[month] = stats
            atomic.write_text(stats_path, json.dumps(product_stats))
            done += 1
            print(f"{product} {month}: {stats['kept']:,} kept", flush=True)
            if limit_months and done >= limit_months:
                break
    for product in groups:
        stats_path = work_dir / f"stats_{product}.json"
        if stats_path.exists():
            per_month = json.loads(stats_path.read_text(encoding="utf-8"))
            by_country: dict[str, int] = {}
            by_platform: dict[str, int] = {}
            for entry in per_month.values():
                for k, v in entry["by_country"].items():
                    by_country[k] = by_country.get(k, 0) + v
                for k, v in entry["by_platform"].items():
                    by_platform[k] = by_platform.get(k, 0) + v
            totals[product] = {
                "loaded_records": sum(e["loaded"] for e in per_month.values()),
                "invalid_or_duplicate": sum(e["invalid_or_duplicate"] for e in per_month.values()),
                "outside_the_sixteen_countries": sum(e["outside_the_sixteen_countries"] for e in per_month.values()),
                "kept_records": sum(e["kept"] for e in per_month.values()),
                "records_by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])),
                "records_by_platform": by_platform, "covered_ranges": covered.get(product, []),
                "months_processed": len(per_month),
            }

    mapping = build_mapping(work_dir)
    all_months = pd.Series(sorted({p.stem.split("_")[-1] for p in work_dir.glob("agg_*.parquet")}))
    years = sorted({m[:4] for m in all_months})
    cell_parts, monthly_parts = [], []
    for year in years:
        # A 5-day window that starts in December ends in January, so read the previous December too and
        # keep only the days that belong to this year.
        names = sorted(work_dir.glob(f"agg_*_{year}-*.parquet")) + sorted(work_dir.glob(f"agg_*_{int(year) - 1}-12.parquet"))
        agg = pd.concat([pd.read_parquet(p) for p in names], ignore_index=True)
        agg = agg[agg["date"].dt.year == int(year)]
        if agg.empty:
            continue
        sensor_days = agg.groupby(["date", "grid_x", "grid_y", "sensor"], observed=True)[["detections", "steady_detections"]].sum().reset_index()
        cell_days = harmonized_cell_days(sensor_days).merge(mapping, on=["grid_x", "grid_y"], how="left")
        cell_days["region"] = cell_days["region"].astype("category")
        cell_days["occupied_by"] = cell_days["occupied_by"].astype("category")
        cell_parts.append(cell_days)
        print(f"harmonized {year}: {len(cell_days):,} cell-days", flush=True)
    cell_days = pd.concat(cell_parts, ignore_index=True)
    month_starts = cell_days["date"].dt.to_period("M").dt.start_time
    archive = archive_coverage(month_starts, covered, None)  # all satellites
    for part in cell_parts:
        monthly_parts.append(monthly_summary(part, archive=archive, national_name=REGION_NAME))
    monthly = pd.concat(monthly_parts, ignore_index=True)
    # Each yearly piece holds its own months, so the pieces never overlap.
    monthly = monthly.sort_values(["region", "month"]).reset_index(drop=True)
    monthly = complete_regions(monthly, REGION_NAME)
    order = {name: i for i, name in enumerate([REGION_NAME] + ORDER)}
    monthly = monthly.sort_values(by=["region", "month"], key=lambda col: col.map(order) if col.name == "region" else col).reset_index(drop=True)
    atomic.to_parquet(cell_days, harm_dir / "cell_days_5km.parquet", index=False)
    atomic.to_csv(monthly, harm_dir / "monthly_5km.csv", index=False)
    meta = {
        "harmonization_method": "Strategy A: common 5 km grid, UTC day, active cell-days (West Africa, country level)",
        "platforms": "all (Terra, Aqua, Suomi-NPP, NOAA-20, NOAA-21)", "steady_set": list(STABLE_PLATFORMS), "cell_km": CELL_KM, "countries": ORDER,
        "cell_days": int(len(cell_days)), "cells": int(len(mapping)),
        "country_rule": "each cell takes the country holding most of its detections; border cells are approximate",
        "products": totals,
    }
    atomic.write_text(output_dir / "metadata.json", json.dumps(meta, indent=2))
    summary = run_analytics(harm_dir / "monthly_5km.csv", output_dir / "analytics")
    return {"metadata": meta, "analytics": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/firms_wa"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/wa"))
    parser.add_argument("--boundaries", type=Path, default=DEFAULT_BOUNDARIES)
    parser.add_argument("--limit-months", type=int, default=None, help="process only this many new months (testing)")
    args = parser.parse_args()
    result = run(args.raw_dir, args.output_dir, args.boundaries, limit_months=args.limit_months)
    print(json.dumps(result["analytics"], indent=2))


if __name__ == "__main__":
    main()
