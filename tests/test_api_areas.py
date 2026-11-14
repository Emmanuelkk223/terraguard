"""API tests: sensor views, custom bounding boxes, date ranges, series, quality, exports.

Fixtures are tiny hand-written TEST DATA pushed through the real pipeline functions.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from data_pipeline.calendar_analytics import run
from data_pipeline.harmonize import archive_coverage, harmonized_cell_days, monthly_summary, sensor_cell_days

PLATFORMS = ("Terra", "Aqua", "Suomi-NPP")
COVERED = {"MODIS_SP": [["2012-01-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-12-31"]]}


def _observations() -> pd.DataFrame:
    rows = []
    for year in range(2013, 2021):
        for month in (1, 2, 7):
            n = 4 + (year % 3) + (100 if (year == 2018 and month == 1) else 0)
            for i in range(n):
                stamp = f"{year}-{month:02d}-10 02:04"
                rows.append((9.0 + i * 0.1, -1.0, stamp, "MODIS", "Aqua", 5.0, "nominal", True))
                rows.append((9.0 + i * 0.1, -1.0, stamp.replace("02:04", "13:30"), "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
            if month != 7:
                rows.append((5.6, -0.2, f"{year}-{month:02d}-12 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
    obs = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform",
                                      "frp", "confidence_class", "is_presumed_vegetation_fire"])
    obs["acq_datetime"] = pd.to_datetime(obs["acq_datetime"])
    return obs


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    cell_days = harmonized_cell_days(sensor_cell_days(_observations(), 5.0))
    cell_days["region"] = ["South" if y < 140 else "North" for y in cell_days["grid_y"]]
    months = cell_days["date"].dt.to_period("M").dt.start_time
    monthly = monthly_summary(cell_days, archive=archive_coverage(months, COVERED, PLATFORMS))
    base = tmp_path / "data" / "processed"
    (base / "harmonized").mkdir(parents=True)
    cell_days.to_parquet(base / "harmonized" / "cell_days_5km.parquet", index=False)
    monthly.to_csv(base / "harmonized" / "monthly_5km.csv", index=False)
    (base / "harmonized" / "harmonization_metadata.json").write_text(json.dumps({
        "harmonization_method": "test", "harmonization_version": "T-0", "observations_used": 123,
        "observations_outside_ghana_excluded": 7, "platforms": list(PLATFORMS),
        "coverage_rule": "archive", "spatial_clip": "test"}), encoding="utf-8")
    run(base / "harmonized" / "monthly_5km.csv", base / "analytics", min_samples=5)
    (base / "metadata.json").write_text(json.dumps({"products": {"MODIS_SP": {
        "source_files": 3, "loaded_records": 10, "retained_records": 9,
        "exclusions_by_reason": {"duplicate_observation": 1}, "missing_values": {"frp": 0, "confidence": 2},
        "records_by_platform": {"Aqua": 9}, "covered_ranges": [["2012-01-01", "2025-12-31"]]}}}), encoding="utf-8")
    return TestClient(create_app(tmp_path))


def test_sensor_views_change_the_series(client: TestClient) -> None:
    both = client.get("/api/calendar", params={"region": "North"}).json()["data"]
    modis = client.get("/api/calendar", params={"region": "North", "sensor": "modis"}).json()["data"]
    assert len(both) == len(modis) > 0
    assert {r["view"] for r in modis} == {"modis"}
    row_b = next(r for r in both if r["year"] == 2018 and r["month"] == 1)
    row_m = next(r for r in modis if r["year"] == 2018 and r["month"] == 1)
    assert row_m["active_cell_days"] == row_b["modis_cell_days"]
    assert client.get("/api/calendar", params={"sensor": "radar"}).status_code == 422


def test_custom_bbox_calendar_seasonal_annual_and_validation(client: TestClient) -> None:
    box = "-3.0,8.0,1.0,25.0"
    cal = client.get("/api/calendar", params={"bbox": box}).json()
    assert cal["region"] == "Custom area" and cal["total"] > 0
    jan_2018 = next(r for r in cal["data"] if r["year"] == 2018 and r["month"] == 1)
    assert jan_2018["status"] == "unusually_high"
    assert client.get("/api/seasonal", params={"bbox": box}).json()["data"]
    assert client.get("/api/annual", params={"bbox": box}).json()["data"]
    for bad in ("1,2,3", "5,0,1,10", "a,b,c,d"):
        assert client.get("/api/calendar", params={"bbox": bad}).status_code == 422
    empty = client.get("/api/calendar", params={"bbox": "100,10,101,11"}).json()
    assert empty["total"] > 0 and all(r["active_cell_days"] == 0 for r in empty["data"])  # zeros, not an error


def test_anomalies_report_cross_sensor_corroboration(client: TestClient) -> None:
    flagged = client.get("/api/calendar/anomalies", params={"region": "North", "direction": "high"}).json()["data"]
    assert flagged and flagged[0]["year"] == 2018
    assert "modis_status" in flagged[0] and "viirs_status" in flagged[0]
    assert flagged[0]["modis_status"] == "unusually_high" and flagged[0]["viirs_status"] == "unusually_high"


def test_map_cells_by_date_range_sensor_and_bbox(client: TestClient) -> None:
    month = client.get("/api/map/cells", params={"year": 2018, "month": 1}).json()
    ranged = client.get("/api/map/cells", params={"start": "2018-01-01", "end": "2018-01-31"}).json()
    assert len(month["features"]) == len(ranged["features"]) > 0 and ranged["period"] == ["2018-01-01", "2018-01-31"]
    narrow = client.get("/api/map/cells", params={"start": "2018-01-13", "end": "2018-01-31"}).json()
    assert narrow["features"] == []  # nothing detected after the 12th: a valid empty result, not an error
    boxed = client.get("/api/map/cells", params={"start": "2018-01-01", "end": "2018-01-31", "bbox": "-1.5,5.0,1.0,6.5"}).json()
    assert 0 < len(boxed["features"]) < len(ranged["features"])
    modis = client.get("/api/map/cells", params={"start": "2018-01-01", "end": "2018-01-31", "sensor": "modis"}).json()
    assert 0 < len(modis["features"]) < len(ranged["features"])  # the southern cell is VIIRS-only
    assert client.get("/api/map/cells", params={"start": "2018-02-01", "end": "2018-01-01"}).status_code == 422
    assert client.get("/api/map/cells").status_code == 422


def test_series_day_and_week(client: TestClient) -> None:
    daily = client.get("/api/series", params={"start": "2018-01-01", "end": "2018-01-31"}).json()
    assert len(daily["data"]) == 31 and sum(r["value"] for r in daily["data"]) > 0
    weekly = client.get("/api/series", params={"start": "2018-01-01", "end": "2018-01-31", "interval": "week"}).json()
    assert sum(r["value"] for r in weekly["data"]) == sum(r["value"] for r in daily["data"])
    assert client.get("/api/series", params={"start": "2013-01-01", "end": "2020-12-31"}).status_code == 422  # too long for daily
    assert client.get("/api/series", params={"start": "2013-01-01", "end": "2020-12-31", "interval": "week"}).status_code == 200


def test_quality_endpoint(client: TestClient) -> None:
    body = client.get("/api/quality").json()
    assert body["products"]["MODIS_SP"]["missing_values"]["confidence"] == 2
    assert body["records_by_platform"] == {"Aqua": 9}
    assert body["coverage"]["months_total"] > 0 and "incomplete_months" in body["coverage"]
    assert body["coverage"]["months_complete"] == body["coverage"]["months_total"]  # fixture archive covers every month
    assert body["coverage"]["incomplete_months"] == []
    assert body["harmonization"]["observations_outside_ghana_excluded"] == 7


def test_exports_carry_area_sensor_and_period(client: TestClient) -> None:
    cal = client.get("/api/export/calendar.csv", params={"bbox": "-3,8,1,25", "sensor": "viirs"})
    assert "# area: custom bounding box (west,south,east,north) -3,8,1,25" in cal.text and "# sensor view: viirs" in cal.text
    parsed = pd.read_csv(io.StringIO(cal.text), comment="#")
    assert set(parsed["region"]) == {"Custom area"}
    cells = client.get("/api/export/cells.csv", params={"start": "2018-01-01", "end": "2018-01-31", "sensor": "modis"})
    assert "# period: 2018-01-01 to 2018-01-31" in cells.text
    series = client.get("/api/export/series.csv", params={"start": "2018-01-01", "end": "2018-01-31", "interval": "week"})
    assert "# interval: week" in series.text and len(pd.read_csv(io.StringIO(series.text), comment="#")) >= 4


def test_model_comparison_endpoint_serves_the_report_or_503(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/model-comparison").status_code == 503  # not generated yet
    report = {"pooled": {"areas": 1}, "notes": ["No ground-truth labels exist."]}
    (tmp_path / "data" / "processed" / "analytics" / "model_comparison.json").write_text(json.dumps(report), encoding="utf-8")
    response = client.get("/api/model-comparison")
    assert response.status_code == 200 and response.json() == report


def test_model_comparison_report_is_strict_json() -> None:
    import json as _json
    from data_pipeline.model_comparison import compare
    report = compare(pd.concat([_series_for_comparison("A"), _series_for_comparison("B")]))
    text = _json.dumps(report, allow_nan=False)  # raises if any NaN/inf slipped through
    assert "synthetic_injection" in text


def _series_for_comparison(region: str) -> pd.DataFrame:
    import numpy as np
    season = np.array([300, 280, 200, 120, 60, 30, 25, 30, 50, 90, 180, 280], dtype=float)
    rows = [{"region": region, "year": y, "month": m, "coverage_ok": True, "active_cell_days": season[m - 1],
             "modis_cell_days": season[m - 1] * 0.3, "viirs_cell_days": season[m - 1] * 0.9}
            for y in range(2012, 2026) for m in range(1, 13)]
    return pd.DataFrame(rows)  # perfectly flat per month: exercises the unscorable / NaN paths
