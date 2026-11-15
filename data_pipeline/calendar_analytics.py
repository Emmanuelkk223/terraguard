"""Burning-activity calendar analytics on the harmonized monthly series.

For every region and calendar month, each year's value is compared with the
median/MAD of the SAME calendar month in OTHER years (leave-one-out), using
only months that passed the coverage rule. Scores are computed on a log scale
(activity varies multiplicatively and is right-skewed) and compared with a
threshold CALIBRATED to the baseline size, so ordinary months are falsely flagged
about 1% of the time (see calibration.py). Every result carries its baseline
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

from . import atomic
from .bridge import bridge_monthly
from .calibration import MAD_SCALE, TARGET_FALSE_FLAG_RATE, threshold_for

DEFAULT_THRESHOLD = None  # None = calibrated to the baseline size; a number forces a fixed threshold
VALUE = "active_cell_days"
SMALL_COUNT = 30  # below this typical level, percentage swings are routine


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


def _estimate_note(row: dict) -> str:
    if row.get("series_basis") != "modis_scaled":
        return ""
    return (f" Estimated: VIIRS did not exist yet, so this month is MODIS expressed on the combined scale "
            f"(90% range {row['estimate_low']:,.0f} to {row['estimate_high']:,.0f}); MODIS alone saw {row['observed_cell_days']:,.0f}.")


def _explain(row: dict) -> str:
    return _explain_core(row) + _estimate_note(row)


def _explain_core(row: dict) -> str:
    month = calendar.month_name[int(row["month"])]
    where = row["region"] if row["region"] != "Ghana" else "all of Ghana"
    status = row["status"]
    if status == "incomplete_coverage" and row.get("limited_reason") == "terra_only":
        return (f"{month} {int(row['year'])} predates the full MODIS constellation: only Terra was observing "
                "(Aqua began delivering fire data in mid-2002), so this month is not compared with history.")
    if status == "incomplete_coverage":
        return (f"{month} {int(row['year'])} in {where} lacks sufficient satellite record coverage "
                "for one or both sensors, so it is not compared with history.")
    if status == "insufficient_baseline":
        return (f"Only {int(row['baseline_n'])} other complete years exist for {month} in {where}; "
                "too few for a reliable historical comparison.")
    shown = row.get("scored_cell_days", row[VALUE])
    base = (f"{shown:,.0f} active cell-days in {month} {int(row['year'])} ({where}) vs a "
            f"historical median of {row['baseline_median']:,.0f} for {month} across "
            f"{int(row['baseline_n'])} other years (MAD {row['baseline_mad']:,.1f}); "
            f"{row['pct_diff']:+.0f}% ({row['abs_diff']:+,.0f}).")
    if row.get("scored_cell_days", row[VALUE]) != row[VALUE]:
        base += (f" This comparison uses the steady set of satellites (Terra, Aqua, Suomi-NPP) so that NOAA-20 and NOAA-21, which joined in 2018 and 2023, "
                 f"cannot create a false alarm; counting all satellites there were {row[VALUE]:,.0f}.")
    if status in ("above_flat_baseline", "below_flat_baseline"):
        return base + " Past years showed no variation, so a score cannot be computed."
    if status in ("unusually_high", "unusually_low"):
        text = base + (f" Robust score {row['robust_score']:+.1f} (log scale) exceeds ±{row['threshold']:.1f}, the threshold "
                       f"calibrated for a {int(row['baseline_n'])}-year baseline so that ordinary months are falsely flagged about "
                       f"{TARGET_FALSE_FLAG_RATE:.0%} of the time.")
        if row["baseline_median"] < SMALL_COUNT:
            text += " Counts are small here, so large percentage changes are common; treat this flag with extra caution."
        return text
    return base + f" Robust score {row['robust_score']:+.1f} (log scale), within the usual range (±{row['threshold']:.1f})."


def build_calendar(
    monthly: pd.DataFrame, *, min_samples: int = 5, threshold: float | None = DEFAULT_THRESHOLD
) -> pd.DataFrame:
    """Return one row per region-month with baseline, difference and status."""
    # Only the combined series is bridged; a single-sensor view is already homogeneous.
    if "view" in monthly and not monthly["view"].isin(["harmonized", "steady"]).all():
        frame = monthly.copy()
        frame["observed_cell_days"] = frame["active_cell_days"]
        frame["series_basis"] = "single_sensor"
        frame["estimate_low"] = frame["estimate_high"] = frame["active_cell_days"].astype(float)
    else:
        frame = bridge_monthly(monthly)
    # Flags compare like with like. With all satellites counted, NOAA-20 (2018) and NOAA-21 (2023) raise counts for reasons that
    # have nothing to do with fire, so the history comparison is made on the steady set (Terra, Aqua, Suomi-NPP). The counts
    # shown still include every satellite.
    views = set(monthly["view"].unique()) if "view" in monthly else {"harmonized"}
    if "steady_cell_days" in frame.columns and views <= {"harmonized", "steady"}:
        score_column = "steady_cell_days"
    elif views == {"viirs"} and "viirs_steady_cell_days" in frame.columns:
        score_column = "viirs_steady_cell_days"  # VIIRS alone: Suomi-NPP is the one VIIRS satellite present for the whole record
    else:
        score_column = VALUE
    frame["month_start"] = pd.to_datetime(frame["month"])
    frame["year"] = frame["month_start"].dt.year
    frame["month"] = frame["month_start"].dt.month
    frame["coverage_ok"] = frame["coverage_ok"].astype(bool)
    records: list[dict] = []
    for (_, _), group in frame.groupby(["region", "month"], sort=True):
        valid = group[group["coverage_ok"]]
        for _, row in group.sort_values("year").iterrows():
            others = valid[valid["year"] != row["year"]]
            peers = others[score_column].to_numpy(float)
            peers_basis = others["series_basis"].to_numpy()
            n = len(peers)
            median = float(np.median(peers)) if n else np.nan
            mad = float(np.median(np.abs(peers - median))) if n else np.nan
            value = float(row[score_column])
            # Score on the log scale; median/MAD above stay in cell-days for display.
            log_peers = np.log1p(peers)
            log_median = float(np.median(log_peers)) if n else np.nan
            log_mad = float(np.median(np.abs(log_peers - log_median))) if n else np.nan
            score = (np.log1p(value) - log_median) / (MAD_SCALE * log_mad) if n and log_mad > 0 else np.nan
            limit = threshold if threshold is not None else threshold_for(n)
            status, reliable = _status(
                value, median, log_mad, n, score, coverage_ok=bool(row["coverage_ok"]),
                min_samples=min_samples, threshold=limit,
            )
            abs_diff = value - median if n else np.nan
            pct = abs_diff / median * 100 if n and median > 0 else np.nan
            if not row["coverage_ok"]:
                # A partial month is not comparable; never publish a difference or score for it.
                abs_diff = pct = score = np.nan
            record = {
                "region": row["region"], "year": int(row["year"]), "month": int(row["month"]),
                "month_start": row["month_start"].date().isoformat(),
                VALUE: int(row[VALUE]),
                "scored_cell_days": int(row[score_column]),
                "modis_cell_days": int(row["modis_cell_days"]),
                "viirs_cell_days": int(row["viirs_cell_days"]),
                "both_cell_days": int(row["both_cell_days"]),
                "modis_detections": int(row["modis_detections"]),
                "viirs_detections": int(row["viirs_detections"]),
                "viirs_steady_cell_days": int(row["viirs_steady_cell_days"]) if "viirs_steady_cell_days" in row.index and pd.notna(row["viirs_steady_cell_days"]) else int(row["viirs_cell_days"]),
                "viirs_steady_detections": int(row["viirs_steady_detections"]) if "viirs_steady_detections" in row.index and pd.notna(row["viirs_steady_detections"]) else int(row["viirs_detections"]),
                "steady_cell_days": int(row["steady_cell_days"]) if "steady_cell_days" in row.index and pd.notna(row["steady_cell_days"]) else int(row["active_cell_days"]),
                "coverage_ok": bool(row["coverage_ok"]),
                "series_basis": row["series_basis"], "estimated": bool(row["series_basis"] == "modis_scaled"),
                "observed_cell_days": int(row["observed_cell_days"]),
                "estimate_low": float(row["estimate_low"]), "estimate_high": float(row["estimate_high"]),
                "limited_reason": "terra_only" if bool(row.get("modis_terra_only", False)) else "",
                "baseline_estimated_n": int((peers_basis == "modis_scaled").sum()) if n else 0,
                "baseline_n": n, "baseline_median": median, "baseline_mad": mad,
                "abs_diff": abs_diff, "pct_diff": pct, "robust_score": score,
                "threshold": limit, "status": status, "reliable": reliable,
            }
            record["explanation"] = _explain(record)
            records.append(record)
    return pd.DataFrame(records).sort_values(["region", "year", "month"]).reset_index(drop=True)


def annual_summary(cal: pd.DataFrame) -> pd.DataFrame:
    """Annual totals; ``complete_year`` is True only when all 12 months have coverage."""
    grouped = cal.groupby(["region", "year"])
    annual = grouped.agg(
        **{VALUE: (VALUE, "sum"), "months_with_coverage": ("coverage_ok", "sum"),
           "estimated_months": ("estimated", "sum"),
           "modis_cell_days": ("modis_cell_days", "sum"), "viirs_cell_days": ("viirs_cell_days", "sum")}
    ).reset_index()
    annual["complete_year"] = annual["months_with_coverage"] == 12
    return annual


def seasonal_summary(cal: pd.DataFrame) -> pd.DataFrame:
    """Per region and calendar month: statistics over complete-coverage years."""
    valid = cal[cal["coverage_ok"]]
    basis = "scored_cell_days" if "scored_cell_days" in valid else VALUE  # the like-for-like series, so no satellite step distorts the season
    rows = []
    for (region, month), g in valid.groupby(["region", "month"]):
        rows.append({
            "region": region, "month": month, "n_years": len(g),
            "median": float(g[basis].median()), "mean": float(g[basis].mean()),
            "min": int(g[basis].min()), "min_year": int(g.loc[g[basis].idxmin(), "year"]),
            "max": int(g[basis].max()), "max_year": int(g.loc[g[basis].idxmax(), "year"]),
        })
    return pd.DataFrame(rows)


def run(monthly_csv: Path, output_dir: Path, *, min_samples: int = 5,
        threshold: float | None = DEFAULT_THRESHOLD) -> dict[str, object]:
    label = monthly_csv.stem.removeprefix("monthly_")
    cal = build_calendar(pd.read_csv(monthly_csv), min_samples=min_samples, threshold=threshold)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic.to_csv(cal, output_dir / f"calendar_{label}.csv", index=False)
    atomic.to_csv(annual_summary(cal), output_dir / f"annual_{label}.csv", index=False)
    atomic.to_csv(seasonal_summary(cal), output_dir / f"seasonal_{label}.csv", index=False)
    flagged = cal[cal["status"].isin(["unusually_high", "unusually_low"])]
    atomic.to_csv(flagged, output_dir / f"anomalies_{label}.csv", index=False)
    return {
        "grid": label, "rows": int(len(cal)), "flagged": int(len(flagged)),
        "status_counts": {str(k): int(v) for k, v in cal["status"].value_counts().items()},
        "min_baseline_years": min_samples, "threshold": threshold if threshold is not None else "calibrated to baseline size",
        "target_false_flag_rate": TARGET_FALSE_FLAG_RATE, "score_scale": "log1p", "mad_scale": MAD_SCALE,
        "baseline": "same calendar month in other years, coverage-complete months only (leave-one-out)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harmonized-dir", type=Path, default=Path("data/processed/harmonized"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/analytics"))
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=None, help="Fixed threshold; default is calibrated to the baseline size")
    args = parser.parse_args()
    files = sorted(args.harmonized_dir.glob("monthly_*km.csv"))
    if not files:
        raise SystemExit(f"No monthly_*km.csv in {args.harmonized_dir}")
    summary = [run(f, args.output_dir, min_samples=args.min_samples, threshold=args.threshold) for f in files]
    atomic.write_text(args.output_dir / "analytics_metadata.json", json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
