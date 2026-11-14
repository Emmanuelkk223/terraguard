"""Does harmonization make MODIS and VIIRS more comparable than raw counts?

For the national monthly series (complete-coverage months only) this compares:

* rank correlation (Spearman) between MODIS and VIIRS, for raw detection counts
  and for cell-days, on the raw series and on the *deseasonalised* series
  (log ratio to each calendar month's median). Deseasonalising matters: both
  sensors follow the dry/wet seasons, which inflates raw correlation, so the
  deseasonalised figure is the discriminating test of shared year-to-year signal;
* stability of the VIIRS / MODIS ratio over time (coefficient of variation).

These are descriptive checks of agreement between two instruments, not accuracy
against ground truth, which does not exist for this task.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _deseasonalise(values: pd.Series, month: pd.Series) -> pd.Series:
    median = values.groupby(month).transform("median")
    return np.log((values + 1.0) / (median + 1.0))


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    if len(a) < 5:
        return None
    return float(a.rank().corr(b.rank()))


def _cv(values: pd.Series) -> float | None:
    values = values.replace([np.inf, -np.inf], np.nan).dropna()
    if len(values) < 5 or values.mean() == 0:
        return None
    return float(values.std(ddof=1) / values.mean())


def validate_grid(monthly: pd.DataFrame) -> dict[str, object]:
    national = monthly[(monthly["region"] == "Ghana") & monthly["coverage_ok"].astype(bool)].copy()
    national["month_start"] = pd.to_datetime(national["month"])
    national["cal_month"] = national["month_start"].dt.month
    national = national[(national["modis_detections"] > 0) & (national["modis_cell_days"] > 0)]
    pairs = {
        "raw_detections": ("modis_detections", "viirs_detections"),
        "cell_days": ("modis_cell_days", "viirs_cell_days"),
    }
    result: dict[str, object] = {"months": int(len(national))}
    for name, (m, v) in pairs.items():
        result[name] = {
            "spearman_raw_series": _spearman(national[m], national[v]),
            "spearman_deseasonalised": _spearman(
                _deseasonalise(national[m], national["cal_month"]),
                _deseasonalise(national[v], national["cal_month"]),
            ),
            "ratio_viirs_over_modis_mean": float((national[v] / national[m]).mean()),
            "ratio_cv": _cv(national[v] / national[m]),
        }
    share = national["both_cell_days"] / national["active_cell_days"]
    by_year = share.groupby(national["month_start"].dt.year).mean()
    result["agreement_share_both_by_year"] = {int(k): round(float(v), 4) for k, v in by_year.items()}
    return result


def overpass_drift(observations_dir: Path) -> dict[str, dict[int, float]]:
    """Median UTC hour of daytime detections per platform and year.

    A proxy for local overpass time (Ghana is near 0 degrees longitude, so UTC is
    close to local solar time). Orbit drift shifts what each platform can see,
    which can create apparent trends that are not changes in fire.
    """
    parts = []
    for path in sorted(observations_dir.glob("*.parquet")):
        d = pd.read_parquet(path, columns=["acq_datetime", "platform", "daynight"])
        d = d[d["daynight"] == "D"]
        parts.append(pd.DataFrame({
            "year": d["acq_datetime"].dt.year, "platform": d["platform"],
            "hour": d["acq_datetime"].dt.hour + d["acq_datetime"].dt.minute / 60,
        }))
    table = pd.concat(parts).groupby(["platform", "year"])["hour"].median().round(2)
    return {str(p): {int(y): float(v) for y, v in g.droplevel(0).items()} for p, g in table.groupby(level=0)}


def run(harmonized_dir: Path, observations_dir: Path, output: Path) -> dict[str, object]:
    report: dict[str, object] = {"grids": {}}
    for path in sorted(harmonized_dir.glob("monthly_*km.csv")):
        report["grids"][path.stem.removeprefix("monthly_")] = validate_grid(pd.read_csv(path))
    if observations_dir.exists():
        report["overpass_hour_by_year"] = overpass_drift(observations_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harmonized-dir", type=Path, default=Path("data/processed/harmonized"))
    parser.add_argument("--observations-dir", type=Path, default=Path("data/processed/observations"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analytics/validation.json"))
    args = parser.parse_args()
    print(json.dumps(run(args.harmonized_dir, args.observations_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
