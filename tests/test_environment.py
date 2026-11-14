"""Tests for rainfall context. Payloads are hand-built TEST DATA shaped like NASA POWER responses."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_pipeline.environment import association, build_rainfall_table, parse_power, region_points, run
from data_pipeline.regions import GhanaRegions


def _payload(rain_by_month: dict[str, float], fill: float = -999.0) -> dict:
    values = dict(rain_by_month)
    for year in sorted({k[:4] for k in values}):
        values[f"{year}13"] = 99.0  # annual value, must be ignored
    return {"header": {"fill_value": fill}, "properties": {"parameter": {"PRECTOTCORR": values}}}


def test_parse_power_drops_annual_and_fill_values_and_converts_units() -> None:
    frame = parse_power(_payload({"202401": 1.0, "202402": -999.0, "202403": 2.0}))
    assert list(frame["month"]) == [1, 3]  # fill value dropped, annual (13) dropped
    assert frame.loc[frame["month"] == 1, "rainfall_mm"].iloc[0] == 31.0  # 1.0 mm/day x 31 days
    assert frame.loc[frame["month"] == 3, "rainfall_mm"].iloc[0] == 62.0


def _series(scale: float = 1.0, wet_year: int | None = None) -> dict[str, float]:
    base = [0.3, 0.8, 2.0, 3.5, 4.5, 6.0, 4.0, 3.0, 5.0, 4.0, 1.5, 0.4]
    return {f"{y}{m:02d}": base[m - 1] * scale * (6 if (y, m) == (wet_year, 12) else 1) for y in range(2012, 2026) for m in range(1, 13)}


def test_percentile_and_national_weighted_mean() -> None:
    payloads = {"A": _payload(_series(1.0, wet_year=2025)), "B": _payload(_series(2.0))}
    table = build_rainfall_table(payloads, {"A": 3.0, "B": 1.0})
    dec25 = table[(table["region"] == "A") & (table["year"] == 2025) & (table["month"] == 12)].iloc[0]
    assert dec25["rain_percentile"] == 1.0  # wettest December in the record
    national = table[(table["region"] == "Ghana") & (table["year"] == 2013) & (table["month"] == 3)].iloc[0]
    assert abs(national["rainfall_mm_per_day"] - (2.0 * 3 + 4.0 * 1) / 4) < 1e-9  # area-weighted
    assert set(table["region"]) == {"A", "B", "Ghana"}


def _calendar(rain: pd.DataFrame, effect: float) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    season = np.array([300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280], dtype=float)
    rows = []
    for r in rain[rain["region"] == "A"].itertuples():
        wet = np.log(r.rainfall_mm / rain[(rain["region"] == "A") & (rain["month"] == r.month)]["rainfall_mm"].median())
        value = season[r.month - 1] * np.exp(effect * wet + rng.normal(0, 0.03))
        rows.append({"region": "A", "year": r.year, "month": r.month, "coverage_ok": True, "active_cell_days": value})
    return pd.DataFrame(rows)


def test_association_recovers_a_planted_negative_relationship_and_reports_n() -> None:
    rng = np.random.default_rng(9)
    series = {k: v * float(np.exp(rng.normal(0, 0.5))) for k, v in _series().items()}  # varied rainfall
    table = build_rainfall_table({"A": _payload(series)}, {"A": 1.0})
    negative = association(_calendar(table, effect=-0.6), table)["A"]
    assert negative["lag0"]["spearman"] < -0.5 and negative["lag0"]["n"] == 168
    none = association(_calendar(table, effect=0.0), table)["A"]
    assert abs(none["lag0"]["spearman"]) < 0.3  # no planted relationship, no strong correlation


def test_too_few_months_gives_no_correlation() -> None:
    table = build_rainfall_table({"A": _payload({f"2024{m:02d}": float(m) for m in range(1, 13)})}, {"A": 1.0})
    cal = pd.DataFrame({"region": "A", "year": 2024, "month": range(1, 13), "coverage_ok": True, "active_cell_days": range(10, 22)})
    assert association(cal, table)["A"]["lag0"]["spearman"] is None


def test_run_saves_raw_responses_once_and_never_refetches(tmp_path: Path) -> None:
    calls: list[tuple[float, float]] = []

    def fake_fetch(lon: float, lat: float, start: int, end: int) -> dict:
        calls.append((round(lon, 2), round(lat, 2)))
        return _payload(_series())

    cal = tmp_path / "calendar.csv"
    pd.DataFrame({"region": "Ghana", "year": 2020, "month": range(1, 13), "coverage_ok": True,
                  "active_cell_days": range(100, 112)}).to_csv(cal, index=False)
    first = run(Path("data/reference/GHA_ADM1.geojson"), tmp_path / "raw", tmp_path / "out", cal, fetch=fake_fetch)
    assert len(calls) == 16 and len(list((tmp_path / "raw").glob("power_*.json"))) == 16
    second = run(Path("data/reference/GHA_ADM1.geojson"), tmp_path / "raw", tmp_path / "out", cal, fetch=fake_fetch)
    assert len(calls) == 16  # raw files are immutable: no refetch
    assert (tmp_path / "out" / "rainfall_monthly.csv").exists() and first["sample_points"] == second["sample_points"]
    assert any("not causation" in n for n in first["notes"])
    json.dumps(first, allow_nan=False)


def test_sample_points_fall_inside_ghana() -> None:
    regions = GhanaRegions()
    points = region_points(regions)
    lon = np.array([p[0] for p in points.values()])
    lat = np.array([p[1] for p in points.values()])
    assert len(points) == 16 and regions.inside_country(lon, lat).all()
    assert (regions.region_for(lon, lat) == np.array(list(points))).all()  # each point lies in its own region
