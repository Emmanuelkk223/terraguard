"""Burning-activity calendar analytics on the harmonized monthly series.

For every region and calendar month, each year's value is compared with the
median/MAD of the SAME calendar month in OTHER years (leave-one-out), using
only months that passed the coverage rule. Every result carries its baseline
sample size, a reliability flag and a plain-language explanation.

These are descriptions of unusual HISTORICAL satellite-detected activity.
They are not fire counts, predictions or alerts.
"""

from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd

MAD_SCALE = 1.4826  # makes MAD comparable to a standard deviation for normal data
DEFAULT_THRESHOLD = 3.5  # conventional modified z-score cut-off (Iglewicz & Hoaglin)
VALUE = "active_cell_days"


def _status(value: float, median: float, mad: float, n: int, score: float,
            *, coverage_ok: bool, min_samples: int, threshold: float) -> tuple[str, bool]:
    if not coverage_ok:
        return "incomplete_coverage", False
    if n < min_samples:
        return "insufficient_baseline", False
    if mad == 0:
        if value == median:
            return "typical", True
        return ("above_flat_baseline" if value > median else "below_flat_baseline"), False
    if score >= threshold:
        return "unusually_high", True
    if score <= -threshold:
        return "unusually_low", True
    return "typical", True


def _explain(row: dict) -> str:
    month = calendar.month_name[int(row["month"])]
    where = row["region"] if row["region"] != "Ghana" else "all of Ghana"
    status = row["status"]
    if status == "incomplete_coverage":
        return (f"{month} {int(row['year'])} in {where} lacks sufficient satellite record coverage "
                "for one or both sensors, so it is not compared with history.")
    if status == "insufficient_baseline":
        return (f"Only {int(row['baseline_n'])} other complete years exist for {month} in {where}; "
                "too few for a reliable historical comparison.")
    base = (f"{row[VALUE]:,.0f} active cell-days in {month} {int(row['year'])} ({where}) vs a "
            f"historical median of {row['baseline_median']:,.0f} for {month} across "
            f"{int(row['baseline_n'])} other years (MAD {row['baseline_mad']:,.1f}); "
            f"{row['pct_diff']:+.0f}% ({row['abs_diff']:+,.0f}).")
    if status in ("above_flat_baseline", "below_flat_baseline"):
        return base + " Past years showed no variation, so a score cannot be computed."
    if status in ("unusually_high", "unusually_low"):
        return base + f" Robust score {row['robust_score']:+.1f} exceeds the ±{row['threshold']:g} threshold."
    return base + f" Robust score {row['robust_score']:+.1f}: within the usual range."


def build_calendar(
    monthly: pd.DataFrame, *, min_samples: int = 5, threshold: float = DEFAULT_THRESHOLD
) -> pd.DataFrame:
    """Return one row per region-month with baseline, difference and status."""
    frame = monthly.copy()
    frame["month_start"] = pd.to_datetime(frame["month"])
    frame["year"] = frame["month_start"].dt.year
    frame["month"] = frame["month_start"].dt.month
    frame["coverage_ok"] = frame["coverage_ok"].astype(bool)
    records: list[dict] = []
    for (_, _), group in frame.groupby(["region", "month"], sort=True):
        valid = group[group["coverage_ok"]]
        for _, row in group.sort_values("year").iterrows():
            peers = valid.loc[valid["year"] != row["year"], VALUE].to_numpy(float)
            n = len(peers)
            median = float(np.median(peers)) if n else np.nan
            mad = float(np.median(np.abs(peers - median))) if n else np.nan
            value = float(row[VALUE])
            score = (value - median) / (MAD_SCALE * mad) if n and mad > 0 else np.nan
            status, reliable = _status(
                value, median, mad, n, score, coverage_ok=bool(row["coverage_ok"]),
                min_samples=min_samples, threshold=threshold,
            )
            abs_diff = value - median if n else np.nan
            pct = abs_diff / median * 100 if n and median > 0 else np.nan
            record = {
                "region": row["region"], "year": int(row["year"]), "month": int(row["month"]),
                "month_start": row["month_start"].date().isoformat(),
                VALUE: int(row[VALUE]),
                "modis_cell_days": int(row["modis_cell_days"]),
                "viirs_cell_days": int(row["viirs_cell_days"]),
                "both_cell_days": int(row["both_cell_days"]),
                "modis_detections": int(row["modis_detections"]),
                "viirs_detections": int(row["viirs_detections"]),
                "coverage_ok": bool(row["coverage_ok"]),
                "baseline_n": n, "baseline_median": median, "baseline_mad": mad,
                "abs_diff": abs_diff, "pct_diff": pct, "robust_score": score,
                "threshold": threshold, "status": status, "reliable": reliable,
            }
            record["explanation"] = _explain(record)
            records.append(record)
    return pd.DataFrame(records).sort_values(["region", "year", "month"]).reset_index(drop=True)


def annual_summary(cal: pd.DataFrame) -> pd.DataFrame:
    """Annual totals; ``complete_year`` is True only when all 12 months have coverage."""
    grouped = cal.groupby(["region", "year"])
    annual = grouped.agg(
        **{VALUE: (VALUE, "sum"), "months_with_coverage": ("coverage_ok", "sum"),
           "modis_cell_days": ("modis_cell_days", "sum"), "viirs_cell_days": ("viirs_cell_days", "sum")}
    ).reset_index()
    annual["complete_year"] = annual["months_with_coverage"] == 12
    return annual


def seasonal_summary(cal: pd.DataFrame) -> pd.DataFrame:
    """Per region and calendar month: statistics over complete-coverage years."""
    valid = cal[cal["coverage_ok"]]
    rows = []
    for (region, month), g in valid.groupby(["region", "month"]):
        rows.append({
            "region": region, "month": month, "n_years": len(g),
            "median": float(g[VALUE].median()), "mean": float(g[VALUE].mean()),
            "min": int(g[VALUE].min()), "min_year": int(g.loc[g[VALUE].idxmin(), "year"]),
            "max": int(g[VALUE].max()), "max_year": int(g.loc[g[VALUE].idxmax(), "year"]),
        })
    return pd.DataFrame(rows)


def run(monthly_csv: Path, output_dir: Path, *, min_samples: int = 5,
        threshold: float = DEFAULT_THRESHOLD) -> dict[str, object]:
    label = monthly_csv.stem.removeprefix("monthly_")
    cal = build_calendar(pd.read_csv(monthly_csv), min_samples=min_samples, threshold=threshold)
    output_dir.mkdir(parents=True, exist_ok=True)
    cal.to_csv(output_dir / f"calendar_{label}.csv", index=False)
    annual_summary(cal).to_csv(output_dir / f"annual_{label}.csv", index=False)
    seasonal_summary(cal).to_csv(output_dir / f"seasonal_{label}.csv", index=False)
    flagged = cal[cal["status"].isin(["unusually_high", "unusually_low"])]
    flagged.to_csv(output_dir / f"anomalies_{label}.csv", index=False)
    return {
        "grid": label, "rows": int(len(cal)), "flagged": int(len(flagged)),
        "status_counts": {str(k): int(v) for k, v in cal["status"].value_counts().items()},
        "min_baseline_years": min_samples, "threshold": threshold, "mad_scale": MAD_SCALE,
        "baseline": "same calendar month in other years, coverage-complete months only (leave-one-out)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harmonized-dir", type=Path, default=Path("data/processed/harmonized"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/analytics"))
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    files = sorted(args.harmonized_dir.glob("monthly_*km.csv"))
    if not files:
        raise SystemExit(f"No monthly_*km.csv in {args.harmonized_dir}")
    summary = [run(f, args.output_dir, min_samples=args.min_samples, threshold=args.threshold) for f in files]
    (args.output_dir / "analytics_metadata.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
