"""Tests for the sensitivity analysis. Fixtures are hand-built TEST DATA (code logic only)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data_pipeline.harmonize import archive_coverage, harmonize, STABLE_PLATFORMS
from data_pipeline.sensitivity import burning_season, describe_months, run, summarise


def test_describe_months_handles_wraparound_and_gaps() -> None:
    assert describe_months([11, 12, 1, 2]) == "Nov-Feb"
    assert describe_months([3]) == "Mar"
    assert describe_months([1, 2, 6, 7]) == "Jan-Feb, Jun-Jul"
    assert describe_months(list(range(1, 13))) == "all year"


def test_burning_season_uses_a_fraction_of_the_peak() -> None:
    seasonal = pd.DataFrame({"month": range(1, 13), "median": [300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280]})
    season = burning_season(seasonal, 0.5)
    assert season["months"] == [1, 2, 3, 11, 12] and season["label"] == "Nov-Mar" and season["peak_month"] == 1
    assert 0.6 < season["share_of_year"] < 0.9
    assert burning_season(pd.DataFrame({"month": [1, 2], "median": [0, 0]})) is None


def _monthly(scale: float = 1.0, bump: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    season = np.array([300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280], dtype=float)
    rows = []
    for year in range(2012, 2026):
        for month in range(1, 13):
            value = season[month - 1] * scale * (1 + rng.normal(0, 0.04)) * (bump if (year, month) == (2023, 1) else 1)
            rows.append({"region": "Ghana", "month": f"{year}-{month:02d}-01", "coverage_ok": True,
                         "active_cell_days": value, "modis_cell_days": value * 0.3, "viirs_cell_days": value * 0.8,
                         "both_cell_days": value * 0.1, "modis_detections": value, "viirs_detections": value * 3})
    return pd.DataFrame(rows)


def test_summarise_reports_correlation_with_default_and_flags() -> None:
    default, series = summarise(_monthly(), None)
    assert default["correlation_with_default"] is None and default["complete_months"] == 168
    assert default["burning_season"]["peak_month"] == 1
    same, _ = summarise(_monthly(scale=2.0), series)
    assert same["correlation_with_default_deseasonalised"] is not None and same["correlation_with_default"] > 0.99
    spiked, _ = summarise(_monthly(bump=6.0), series)
    assert any(f.startswith("2023-01") for f in spiked["flagged_months"])
    assert not any(f.startswith("2023-01") for f in default["flagged_months"])


def test_run_covers_default_grid_and_filter_scenarios(tmp_path: Path) -> None:
    rows = []
    for year in range(2013, 2021):
        for month in (1, 2, 7):
            for i in range(6 + (year % 3)):
                lat = 6.8 + i * 0.12
                for sensor, platform, conf, day in (("MODIS", "Aqua", "high", 10), ("VIIRS", "Suomi-NPP", "nominal", 11),
                                                    ("VIIRS", "NOAA-20", "low", 12)):
                    rows.append((lat, -1.0, pd.Timestamp(f"{year}-{month:02d}-{day} 12:00"), sensor, platform, 5.0, conf, True))
    obs = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform", "frp",
                                      "confidence_class", "is_presumed_vegetation_fire"])
    obs_dir, harm_dir = tmp_path / "observations", tmp_path / "harmonized"
    obs_dir.mkdir()
    obs.to_parquet(obs_dir / "all.parquet", index=False)
    covered = {"MODIS_SP": [["2012-01-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-12-31"]],
               "VIIRS_NOAA20_SP": [["2018-04-01", "2025-12-31"]]}
    from data_pipeline.regions import GhanaRegions
    harmonize(sorted(obs_dir.glob("*.parquet")), harm_dir, cell_sizes_km=(1.0, 2.0, 5.0), regions=GhanaRegions(),
              platforms=STABLE_PLATFORMS, covered_ranges=covered)
    report = run(obs_dir, harm_dir, covered)
    names = set(report["scenarios"])
    assert {"default_5km", "grid_1km", "grid_2km", "all_platforms", "confidence_nominal", "confidence_high", "vegetation_only"} <= names
    totals = {n: s["total_active_cell_days"] for n, s in report["scenarios"].items()}
    assert totals["confidence_high"] <= totals["confidence_nominal"] <= totals["default_5km"]  # stricter filters keep less
    assert totals["all_platforms"] >= totals["default_5km"]  # more platforms can only add cell-days
    assert totals["grid_1km"] >= totals["grid_2km"] >= totals["default_5km"]  # finer cells, more cell-days
    json.dumps(report, allow_nan=False)  # strict JSON for the API
    assert any("ground truth" in n for n in report["notes"])
