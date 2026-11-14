"""Tests for the summary report. Inputs are hand-built TEST DATA (code logic only)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data_pipeline.calendar_analytics import build_calendar
from data_pipeline.report import build_blocks, to_html, to_markdown

SEASON = np.array([300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280], dtype=float)


def _calendar(spike: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    rows = []
    for year in range(2012, 2026):
        for month in range(1, 13):
            value = SEASON[month - 1] * (1 + rng.normal(0, 0.04)) * (0.2 if spike and (year, month) == (2025, 12) else 1)
            rows.append({"region": "Test <area>", "month": f"{year}-{month:02d}-01", "coverage_ok": not (year == 2012 and month == 1),
                         "active_cell_days": value, "modis_cell_days": value * 0.3, "viirs_cell_days": value * 0.8,
                         "both_cell_days": value * 0.1, "modis_detections": value, "viirs_detections": value * 3})
    return build_calendar(pd.DataFrame(rows))


def _blocks(**kw):
    return build_blocks(_calendar(), area="Test <area> & co", sensor="harmonized", grid="5km",
                        meta={"harmonization": {"harmonization_method": "M", "harmonization_version": "V1", "platforms": ["Aqua"]}},
                        generated=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc), **kw)


def test_report_contains_headline_season_annual_flags_and_limits() -> None:
    md = to_markdown(_blocks())
    for expected in ("# TerraGuard summary report", "## Headline figures", "## Seasonal pattern", "## Annual totals",
                     "## Unusual months", "Dec 2025", "## Limitations", "## Provenance", "version V1", "2026-01-02 03:04 UTC"):
        assert expected in md, expected
    assert "Burning season" in md and "not a confirmed or unique fire" in md
    assert "partial (11/12 months)" in md  # 2012 lacks one covered month
    assert "not unique fires" in md or "not an emergency alert" in md


def test_html_is_self_contained_and_escapes_untrusted_text() -> None:
    html = to_html(_blocks())
    assert html.startswith("<!doctype html>") and "<style>" in html and "@media print" in html
    assert "Test &lt;area&gt; &amp; co" in html and "Test <area>" not in html  # escaped
    assert "<script" not in html and "http" not in html.split("<body>")[0]  # no external resources or scripts


def test_report_for_empty_coverage_is_honest() -> None:
    cal = _calendar()
    cal["coverage_ok"] = False
    md = to_markdown(build_blocks(cal, area="X", sensor="viirs", grid="1km"))
    assert "no months with full satellite record coverage" in md and "## Limitations" in md


def test_period_section_appears_only_with_a_period() -> None:
    series = pd.DataFrame({"period_start": ["2025-12-01", "2025-12-02"], "value": [5, 9], "modis_cell_days": [2, 3],
                           "viirs_cell_days": [4, 7], "both_cell_days": [1, 1]})
    assert "Selected period" not in to_markdown(_blocks())
    md = to_markdown(_blocks(period=("2025-12-01", "2025-12-02"), period_series=series))
    assert "Selected period: 2025-12-01 to 2025-12-02" in md and "| Active cell-days | 14 |" in md


def test_corroboration_column_only_when_available() -> None:
    cal = _calendar()
    assert "Also unusual in" not in to_markdown(build_blocks(cal, area="X", sensor="harmonized", grid="5km"))
    cal["modis_status"] = "unusually_low"
    cal["viirs_status"] = "typical"
    md = to_markdown(build_blocks(cal, area="X", sensor="harmonized", grid="5km"))
    assert "Also unusual in" in md and "MODIS only" in md
