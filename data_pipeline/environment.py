"""Rainfall context from NASA POWER, and its (descriptive) association with burning activity.

Data: NASA POWER monthly "Precipitation Corrected" (PRECTOTCORR, mm/day), a coarse gridded product
(about 0.5 x 0.625 degrees), sampled at one representative point inside each region. It is context, not a
region-wide measurement: rainfall varies a lot within a region.

Only two things are computed, both descriptive:
  * where a month's rainfall ranks among the same calendar month in other years (a percentile), and
  * the rank correlation between burning anomalies and rainfall anomalies at several lags.
Correlation is not causation: rainfall can suppress burning, promote fuel growth for later months, or both,
and many other factors act. Nothing here establishes a cause.

Raw API responses are saved unchanged under data/raw/environment/.
"""

from __future__ import annotations

import argparse
import calendar
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import atomic
from .regions import DEFAULT_ADM1, GhanaRegions

POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=PRECTOTCORR&community=AG"
    "&longitude={lon:.4f}&latitude={lat:.4f}&start={start}&end={end}&format=JSON"
)
PARAMETER = "PRECTOTCORR"
LAGS = (0, 1, 2, 3)
MIN_PAIRS = 36  # fewer paired months than this and no association is reported


def region_points(regions: GhanaRegions) -> dict[str, tuple[float, float]]:
    """A representative (lon, lat) inside each region polygon."""
    return {name: (geom.representative_point().x, geom.representative_point().y) for name, geom in zip(regions.names, regions.geoms)}


def fetch_point(lon: float, lat: float, start: int, end: int, opener: Callable = urllib.request.urlopen) -> dict:
    with opener(POWER_URL.format(lon=lon, lat=lat, start=start, end=end), timeout=90) as response:
        return json.load(response)


def parse_power(payload: dict) -> pd.DataFrame:
    """Monthly rows (year, month, rainfall_mm_per_day); the month-13 annual value and fill values are dropped."""
    fill = payload.get("header", {}).get("fill_value", -999.0)
    values = payload["properties"]["parameter"][PARAMETER]
    rows = []
    for key, value in values.items():
        year, month = int(key[:4]), int(key[4:])
        if month == 13 or value is None or value == fill:
            continue
        rows.append({"year": year, "month": month, "rainfall_mm_per_day": float(value)})
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["days"] = [calendar.monthrange(y, m)[1] for y, m in zip(frame["year"], frame["month"])]
        frame["rainfall_mm"] = frame["rainfall_mm_per_day"] * frame["days"]
    return frame


def build_rainfall_table(payloads: dict[str, dict], areas: dict[str, float]) -> pd.DataFrame:
    """One row per area-month. 'Ghana' is the area-weighted mean of the regions' rainfall."""
    frames = []
    for name, payload in payloads.items():
        frame = parse_power(payload)
        frame.insert(0, "region", name)
        frames.append(frame)
    regional = pd.concat(frames, ignore_index=True)
    weights = regional["region"].map(areas)
    national = (
        regional.assign(w=weights, wr=regional["rainfall_mm_per_day"] * weights)
        .groupby(["year", "month"], as_index=False)
        .agg(wr=("wr", "sum"), w=("w", "sum"), days=("days", "first"))
    )
    national["rainfall_mm_per_day"] = national["wr"] / national["w"]
    national["rainfall_mm"] = national["rainfall_mm_per_day"] * national["days"]
    national.insert(0, "region", "Ghana")
    table = pd.concat([national[["region", "year", "month", "rainfall_mm_per_day", "days", "rainfall_mm"]], regional], ignore_index=True)
    table["rain_percentile"] = table.groupby(["region", "month"])["rainfall_mm_per_day"].rank(pct=True).round(3)
    table["rain_median_mm_per_day"] = table.groupby(["region", "month"])["rainfall_mm_per_day"].transform("median").round(3)
    return table.sort_values(["region", "year", "month"]).reset_index(drop=True)


def _anomaly(series: pd.Series, months: pd.Series, *, log: bool) -> pd.Series:
    values = np.log1p(series) if log else series
    return values - values.groupby(months).transform("median")


def association(calendar_frame: pd.DataFrame, rainfall: pd.DataFrame) -> dict[str, object]:
    """Rank correlations between burning anomalies and rainfall anomalies (same month and lagged)."""
    out: dict[str, object] = {}
    for area, burn in calendar_frame[calendar_frame["coverage_ok"].astype(bool)].groupby("region"):
        rain = rainfall[rainfall["region"] == area]
        if rain.empty:
            continue
        frame = pd.DataFrame({"year": burn["year"].to_numpy(), "month": burn["month"].to_numpy(),
                              "burn": burn["scored_cell_days" if "scored_cell_days" in burn else "active_cell_days"].to_numpy(float)})
        rain = rain.assign(date=pd.to_datetime(dict(year=rain["year"], month=rain["month"], day=1))).set_index("date").sort_index()
        frame["date"] = pd.to_datetime(dict(year=frame["year"], month=frame["month"], day=1))
        frame = frame.set_index("date").sort_index()
        frame["burn_anom"] = _anomaly(frame["burn"], frame["month"], log=True)
        rain["rain_anom"] = _anomaly(rain["rainfall_mm"], rain["month"], log=True)
        entries: dict[str, object] = {}
        for lag in LAGS:
            shifted = rain["rain_anom"].shift(lag, freq="MS")
            entries[f"lag{lag}"] = _entry(frame["burn_anom"], shifted)
        prev3 = rain["rainfall_mm"].rolling(3).sum().shift(1, freq="MS")
        prev3_anom = _anomaly(prev3.dropna(), prev3.dropna().index.month.to_series(index=prev3.dropna().index), log=True)
        entries["previous_three_months"] = _entry(frame["burn_anom"], prev3_anom)
        out[str(area)] = entries
    return out


def _entry(burn: pd.Series, rain: pd.Series) -> dict[str, object]:
    pairs = pd.concat([burn.rename("b"), rain.rename("r")], axis=1).dropna()
    if len(pairs) < MIN_PAIRS or pairs["b"].nunique() < 3 or pairs["r"].nunique() < 3:
        return {"spearman": None, "n": int(len(pairs))}
    return {"spearman": round(float(pairs["b"].rank().corr(pairs["r"].rank())), 3), "n": int(len(pairs))}


def run(adm1: Path, raw_dir: Path, processed_dir: Path, calendar_csv: Path, *, start: int = 2012, end: int = 2025,
        fetch: Callable[[float, float, int, int], dict] = fetch_point) -> dict[str, object]:
    regions = GhanaRegions(adm1)
    points = region_points(regions)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, dict] = {}
    for name, (lon, lat) in points.items():
        path = raw_dir / f"power_{name.replace(' ', '_')}_{start}_{end}.json"
        if path.exists():  # raw responses are immutable; never refetch
            payloads[name] = json.loads(path.read_text(encoding="utf-8"))
            continue
        payload = fetch(lon, lat, start, end)
        atomic.write_text(path, json.dumps(payload))
        payloads[name] = payload
    table = build_rainfall_table(payloads, {n: g.area for n, g in zip(regions.names, regions.geoms)})
    processed_dir.mkdir(parents=True, exist_ok=True)
    atomic.to_csv(table, processed_dir / "rainfall_monthly.csv", index=False)
    result = association(pd.read_csv(calendar_csv), table)
    report = {
        "source": "NASA POWER monthly point API, parameter PRECTOTCORR (precipitation corrected, mm/day)",
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sample_points": {n: {"longitude": round(p[0], 4), "latitude": round(p[1], 4)} for n, p in points.items()},
        "association": result,
        "method": "Spearman rank correlation of log burning anomaly (vs same-calendar-month median) with log rainfall anomaly, "
                  f"months with full coverage; reported only with at least {MIN_PAIRS} paired months.",
        "notes": [
            "Rainfall is a coarse (about 0.5 x 0.625 degree) gridded product sampled at one point per region; it is context, not a regional measurement.",
            "National rainfall is the area-weighted mean of the 16 regional points.",
            "Association is not causation: rainfall can suppress burning, build fuel for later months, or both, and many other factors act.",
            "Several lags are shown; with many comparisons a few moderate correlations can arise by chance.",
        ],
    }
    atomic.write_text(processed_dir / "rainfall_association.json", json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adm1", type=Path, default=DEFAULT_ADM1)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/environment"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/environment"))
    parser.add_argument("--calendar", type=Path, default=Path("data/processed/analytics/calendar_5km.csv"))
    args = parser.parse_args()
    report = run(args.adm1, args.raw_dir, args.processed_dir, args.calendar)
    nat = report["association"].get("Ghana", {})
    print("Ghana association (Spearman, n):", {k: (v["spearman"], v["n"]) for k, v in nat.items()})


if __name__ == "__main__":
    main()
