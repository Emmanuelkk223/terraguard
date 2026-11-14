"""Sensitivity of the headline results to reasonable analysis choices.

TerraGuard's default choices (5 km grid, Terra + Aqua + Suomi-NPP, no quality filter) are one
defensible configuration, not the only one. This module re-runs the harmonization under
alternatives and reports whether the national conclusions move:

  grid size        1 km, 2 km, 5 km (default)
  platform set     default stable constellation vs all five platforms (adds NOAA-20/21 over time)
  quality filter   confidence >= nominal, confidence = high (each sensor's own classes, not comparable
                   across sensors), and presumed-vegetation-fire type only

For every scenario we report the national total, how closely its monthly series follows the default
(rank correlation, raw and after removing seasonality), how often the two sensors see the same cell-day,
the VIIRS/MODIS ratio, the burning season, and the nationally flagged months.

Monthly time intervals are not varied: the historical comparison is defined month against the same
calendar month, and daily/weekly views are exploratory. Reported descriptively; nothing here is validated
against ground truth.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import atomic
from .calendar_analytics import build_calendar, seasonal_summary
from .harmonize import STABLE_PLATFORMS, harmonize
from .regions import DEFAULT_ADM1, GhanaRegions

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEASON_FRACTION = 0.25

# name -> (group, label, harmonize keyword arguments)
FILTER_SCENARIOS: dict[str, tuple[str, str, dict]] = {
    "all_platforms": ("Platform set", "All five platforms (adds NOAA-20 from 2018, NOAA-21 from 2023)", {"platforms": None}),
    "confidence_nominal": ("Quality filter", "Confidence nominal or high only", {"min_confidence": "nominal"}),
    "confidence_high": ("Quality filter", "High confidence only", {"min_confidence": "high"}),
    "vegetation_only": ("Quality filter", "Presumed vegetation fires only (FIRMS type 0)", {"vegetation_only": True}),
}


def describe_months(months: list[int]) -> str:
    """Contiguous runs on a circular calendar, e.g. [11, 12, 1, 2] -> 'Nov-Feb' (matches the dashboard)."""
    present = set(months)
    if len(present) == 12:
        return "all year"
    runs: list[list[int]] = []
    for m in range(1, 13):
        if m in present and ((m - 2) % 12 + 1) not in present:
            run, nxt = [m], m % 12 + 1
            while nxt in present and nxt != m:
                run.append(nxt)
                nxt = nxt % 12 + 1
            runs.append(run)
    return ", ".join(MONTH_ABBR[r[0] - 1] if len(r) == 1 else f"{MONTH_ABBR[r[0] - 1]}-{MONTH_ABBR[r[-1] - 1]}" for r in runs)


def burning_season(seasonal: pd.DataFrame, fraction: float = SEASON_FRACTION) -> dict[str, object] | None:
    """Months whose typical activity is at least ``fraction`` of the busiest month's."""
    medians = seasonal.set_index("month")["median"]
    if medians.empty or medians.max() <= 0:
        return None
    months = sorted(int(m) for m in medians.index[medians >= fraction * medians.max()])
    return {
        "months": months, "label": describe_months(months), "peak_month": int(medians.idxmax()),
        "share_of_year": round(float(medians[months].sum() / medians.sum()), 3),
    }


def _deseasonalised(series: pd.Series) -> pd.Series:
    med = series.groupby(series.index.month).transform("median")
    return np.log1p(series) - np.log1p(med)


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    common = a.index.intersection(b.index)
    if len(common) < 12:
        return None
    return round(float(a[common].rank().corr(b[common].rank())), 3)


def summarise(monthly: pd.DataFrame, default_series: pd.Series | None) -> tuple[dict[str, object], pd.Series]:
    """Headline numbers for one scenario's monthly table (any table with a Ghana row set)."""
    national = monthly[monthly["region"] == "Ghana"].copy()
    calendar = build_calendar(national)
    complete = calendar[calendar["coverage_ok"]].copy()
    series = pd.Series(complete["active_cell_days"].to_numpy(float),
                       index=pd.to_datetime(complete["month_start"]), dtype=float)
    flagged = calendar[calendar["status"].isin(["unusually_high", "unusually_low"])]
    both = float(complete["both_cell_days"].sum())
    active = float(complete["active_cell_days"].sum())
    modis = float(complete["modis_cell_days"].sum())
    seasonal = seasonal_summary(calendar)
    result = {
        "complete_months": int(len(complete)),
        "total_active_cell_days": int(active),
        "share_seen_by_both_sensors": round(both / active, 3) if active else None,
        "viirs_to_modis_cell_day_ratio": round(float(complete["viirs_cell_days"].sum() / modis), 2) if modis else None,
        "burning_season": burning_season(seasonal),
        "flagged_months": [f"{int(r.year)}-{int(r.month):02d} ({'high' if r.status == 'unusually_high' else 'low'})"
                           for r in flagged.itertuples()],
        "correlation_with_default": None,
        "correlation_with_default_deseasonalised": None,
    }
    if default_series is not None:
        result["correlation_with_default"] = _spearman(series, default_series)
        result["correlation_with_default_deseasonalised"] = _spearman(_deseasonalised(series), _deseasonalised(default_series))
    return result, series


def run(
    observations_dir: Path, harmonized_dir: Path, covered_ranges: dict[str, list[list[str]]],
    boundary: Path = DEFAULT_ADM1,
) -> dict[str, object]:
    """Compute every scenario. The default and grid scenarios reuse the existing harmonized outputs."""
    files = sorted(observations_dir.glob("*.parquet"))
    regions = GhanaRegions(boundary)
    scenarios: dict[str, dict[str, object]] = {}

    default_monthly = pd.read_csv(harmonized_dir / "monthly_5km.csv")
    summary, default_series = summarise(default_monthly, None)
    scenarios["default_5km"] = {"group": "Default", "label": "5 km grid, Terra + Aqua + Suomi-NPP, no quality filter", **summary}

    for km in ("1km", "2km"):
        path = harmonized_dir / f"monthly_{km}.csv"
        if path.exists():
            summary, _ = summarise(pd.read_csv(path), default_series)
            scenarios[f"grid_{km}"] = {"group": "Grid size", "label": f"{km[:-2]} km grid (other choices as default)", **summary}

    for name, (group, label, options) in FILTER_SCENARIOS.items():
        with tempfile.TemporaryDirectory() as tmp:
            harmonize(
                files, Path(tmp), cell_sizes_km=(5.0,), regions=regions, covered_ranges=covered_ranges,
                platforms=options.get("platforms", STABLE_PLATFORMS),
                min_confidence=options.get("min_confidence"), vegetation_only=options.get("vegetation_only", False),
            )
            summary, _ = summarise(pd.read_csv(Path(tmp) / "monthly_5km.csv"), default_series)
        scenarios[name] = {"group": group, "label": label, **summary}

    default_flags = set(scenarios["default_5km"]["flagged_months"])
    return {
        "scenarios": scenarios,
        "default_flagged_months": sorted(default_flags),
        "notes": [
            "Each scenario re-runs the harmonization and the same calendar analysis; only the stated choice changes.",
            "Confidence classes are specific to each sensor and are not comparable across sensors.",
            "Rank correlations compare monthly national series over months complete in both scenarios.",
            "Monthly intervals are not varied: comparisons are month against the same calendar month.",
            "Descriptive only: there is no ground truth against which any scenario could be called correct.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/sensitivity.json"))
    args = parser.parse_args()
    meta = json.loads((args.processed_dir / "metadata.json").read_text(encoding="utf-8"))
    covered = {name: info["covered_ranges"] for name, info in meta["products"].items()}
    report = run(args.processed_dir / "observations", args.processed_dir / "harmonized", covered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(args.output, json.dumps(report, indent=2))
    for name, s in report["scenarios"].items():
        print(f"{name:20s} total={s['total_active_cell_days']:>9,} corr={s['correlation_with_default_deseasonalised']} "
              f"both={s['share_seen_by_both_sensors']} season={s['burning_season']['label'] if s['burning_season'] else None} "
              f"flags={len(s['flagged_months'])}")


if __name__ == "__main__":
    main()
