"""API tests for harmonized endpoints.

Fixtures are tiny hand-written TEST DATA pushed through the real pipeline
functions; they are not NASA measurements.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import create_app
from data_pipeline.calendar_analytics import run
from data_pipeline.harmonize import harmonized_cell_days, monthly_summary, sensor_cell_days


def _build(root: Path) -> None:
    rows = []
    for year, n in zip(range(2015, 2021), (3, 4, 5, 4, 3, 12)):
        for i in range(n):  # n distinct cells on one day each January
            rows.append((7.0 + i * 0.1, -1.0, f"{year}-01-10 02:04", "MODIS", "Aqua", 5.0, "nominal", True))
            rows.append((7.0 + i * 0.1, -1.0, f"{year}-01-10 13:30", "VIIRS", "Suomi-NPP", 1.0, "nominal", True))
    obs = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform",
                                      "frp", "confidence_class", "is_presumed_vegetation_fire"])
    obs["acq_datetime"] = pd.to_datetime(obs["acq_datetime"])
    cell_days = harmonized_cell_days(sensor_cell_days(obs, 5.0))
    cell_days["region"] = "Northern"
    harmonized = root / "data" / "processed" / "harmonized"
    harmonized.mkdir(parents=True)
    cell_days.to_parquet(harmonized / "cell_days_5km.parquet", index=False)
    monthly = monthly_summary(cell_days, min_coverage=0.0)
    monthly.to_csv(harmonized / "monthly_5km.csv", index=False)
    (harmonized / "harmonization_metadata.json").write_text(
        json.dumps({"harmonization_method": "test", "harmonization_version": "T-0"}), encoding="utf-8")
    run(harmonized / "monthly_5km.csv", root / "data" / "processed" / "analytics", min_samples=5)


def test_calendar_regions_and_filters(tmp_path: Path) -> None:
    _build(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/regions").json()["regions"] == ["Ghana", "Northern"]
    body = client.get("/api/calendar", params={"region": "Northern", "start_year": 2019}).json()
    assert [r["year"] for r in body["data"]] == [2019, 2020]
    assert client.get("/api/calendar", params={"region": "Atlantis"}).status_code == 422
    assert client.get("/api/calendar", params={"start_year": 2020, "end_year": 2019}).status_code == 422
    assert client.get("/api/calendar", params={"grid": "3km"}).status_code == 422


def test_anomaly_endpoint_explains_the_flag(tmp_path: Path) -> None:
    _build(tmp_path)
    flagged = TestClient(create_app(tmp_path)).get("/api/calendar/anomalies", params={"direction": "high"}).json()
    assert flagged["total"] >= 1
    top = flagged["data"][0]
    assert top["year"] == 2020 and "historical median" in top["explanation"]


def test_map_cells_and_exports(tmp_path: Path) -> None:
    _build(tmp_path)
    client = TestClient(create_app(tmp_path))
    cells = client.get("/api/map/cells", params={"year": 2020, "month": 1, "region": "Northern"}).json()
    assert cells["type"] == "FeatureCollection" and len(cells["features"]) >= 1
    assert cells["features"][0]["geometry"]["type"] == "Point"
    empty = client.get("/api/map/cells", params={"year": 2012, "month": 6}).json()
    assert empty["features"] == []  # empty period is a valid empty result, not an error

    export = client.get("/api/export/calendar.csv", params={"region": "Northern"})
    assert export.headers["content-type"].startswith("text/csv")
    assert "# area: Northern" in export.text and "version T-0" in export.text
    parsed = pd.read_csv(io.StringIO(export.text), comment="#")
    assert set(parsed["region"]) == {"Northern"} and len(parsed) == 6
    assert client.get("/api/export/cells.csv", params={"year": 2020, "month": 1}).status_code == 200


def test_harmonized_endpoints_report_missing_data(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/calendar").status_code == 503
    assert client.get("/api/map/cells", params={"year": 2020, "month": 1}).status_code == 503
