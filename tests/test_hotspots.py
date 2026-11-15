"""API tests: individual hotspot download and the current-period comparison (hand-written TEST DATA)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from data_pipeline.calendar_analytics import run
from data_pipeline.harmonize import archive_coverage, harmonized_cell_days, monthly_summary, sensor_cell_days

PLATFORMS = ("Terra", "Aqua", "Suomi-NPP")
COVERED = {"MODIS_SP": [["2000-11-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-11-20"]]}
REFERENCE = Path(__file__).resolve().parents[1] / "data" / "reference" / "GHA_ADM1.geojson"
COLUMNS = ["acq_datetime", "latitude", "longitude", "sensor", "satellite", "platform", "confidence",
           "confidence_class", "frp", "daynight", "source_product"]


def _observations() -> pd.DataFrame:
    rows = []
    for year in range(2003, 2026):
        for month in range(1, 13):
            n = 2 + (year + month) % 4
            for i in range(n):
                day = 5 + i
                lat, lon = 7.0 + i * 0.05, -1.5 + (month % 3) * 0.1
                rows.append((f"{year}-{month:02d}-{day:02d} 10:30", lat, lon, "MODIS", "Aqua", "Aqua", "70", "nominal", 12.0, "D", "MODIS_SP"))
                if year >= 2012:
                    rows.append((f"{year}-{month:02d}-{day:02d} 13:30", lat, lon, "VIIRS", "N", "Suomi-NPP", "n", "nominal", 3.0, "D", "VIIRS_SNPP_SP"))
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["acq_datetime"] = pd.to_datetime(frame["acq_datetime"])
    return frame


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    obs = _observations()
    base = tmp_path / "data" / "processed"
    (base / "observations").mkdir(parents=True)
    (tmp_path / "data" / "reference").mkdir(parents=True)
    shutil.copy(REFERENCE, tmp_path / "data" / "reference" / "GHA_ADM1.geojson")
    obs[obs["sensor"] == "MODIS"].to_parquet(base / "observations" / "MODIS_SP.parquet", index=False)
    obs[obs["sensor"] == "VIIRS"].to_parquet(base / "observations" / "VIIRS_SNPP_SP.parquet", index=False)
    cell_days = harmonized_cell_days(sensor_cell_days(obs[obs["platform"].isin(PLATFORMS)].assign(
        frp=1.0, confidence_class="nominal", is_presumed_vegetation_fire=True), 5.0))
    cell_days["region"] = "Ashanti"
    months = cell_days["date"].dt.to_period("M").dt.start_time
    monthly = monthly_summary(cell_days, archive=archive_coverage(months, COVERED, PLATFORMS))
    (base / "harmonized").mkdir(parents=True)
    cell_days.to_parquet(base / "harmonized" / "cell_days_5km.parquet", index=False)
    monthly.to_csv(base / "harmonized" / "monthly_5km.csv", index=False)
    (base / "harmonized" / "harmonization_metadata.json").write_text(json.dumps({
        "harmonization_method": "test", "harmonization_version": "T-0", "observations_used": 1,
        "observations_outside_ghana_excluded": 0, "platforms": list(PLATFORMS)}), encoding="utf-8")
    run(base / "harmonized" / "monthly_5km.csv", base / "analytics", min_samples=5)
    (base / "metadata.json").write_text(json.dumps({"products": {
        "MODIS_SP": {"covered_ranges": [["2000-11-01", "2025-12-31"]]},
        "VIIRS_SNPP_SP": {"covered_ranges": [["2012-01-20", "2025-11-20"]]}}}), encoding="utf-8")
    return TestClient(create_app(tmp_path))


def test_hotspot_preview_counts_detections_by_sensor(client: TestClient) -> None:
    body = client.get("/api/hotspots/preview", params={"start": "2020-01-01", "end": "2020-01-31", "region": "Ghana"}).json()
    assert body["rows"] > 0 and not body["too_large"]
    assert set(body["by_sensor"]) == {"MODIS", "VIIRS"}


def test_hotspot_csv_lists_individual_detections_with_provenance(client: TestClient) -> None:
    response = client.get("/api/export/hotspots.csv", params={"start": "2020-01-01", "end": "2020-03-31", "sensor": "modis"})
    assert response.status_code == 200 and "attachment" in response.headers["content-disposition"]
    assert "not a confirmed or unique fire" in response.text
    table = pd.read_csv(io.StringIO(response.text), comment="#")
    assert set(table["sensor"]) == {"MODIS"}
    assert {"datetime_utc", "latitude", "longitude", "confidence", "frp_mw", "region"} <= set(table.columns)
    assert table["datetime_utc"].min() >= "2020-01-01" and table["datetime_utc"].max() < "2020-04-01"


def test_hotspots_before_viirs_exist_are_modis_only(client: TestClient) -> None:
    table = pd.read_csv(io.StringIO(client.get("/api/export/hotspots.csv", params={"start": "2005-01-01", "end": "2005-12-31"}).text), comment="#")
    assert len(table) > 0 and set(table["sensor"]) == {"MODIS"}


def test_hotspot_bbox_filters_and_validates(client: TestClient) -> None:
    inside = client.get("/api/hotspots/preview", params={"start": "2020-01-01", "end": "2020-12-31", "bbox": "-2,6,-1,8"}).json()["rows"]
    outside = client.get("/api/hotspots/preview", params={"start": "2020-01-01", "end": "2020-12-31", "bbox": "0.5,10,1,11"}).json()["rows"]
    assert inside > 0 and outside == 0
    assert client.get("/api/hotspots/preview", params={"start": "2020-01-01", "end": "2020-12-31", "bbox": "x"}).status_code == 422
    assert client.get("/api/hotspots/preview", params={"start": "2020-02-01", "end": "2020-01-01"}).status_code == 422
    assert client.get("/api/hotspots/preview", params={"start": "2020-01-01", "end": "2020-02-01", "sensor": "radar"}).status_code == 422


def test_hotspot_download_limit_is_explicit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.hotspot_routes as routes

    monkeypatch.setattr(routes, "MAX_HOTSPOT_ROWS", 5)
    params = {"start": "2015-01-01", "end": "2020-12-31"}
    assert client.get("/api/hotspots/preview", params=params).json()["too_large"] is True
    response = client.get("/api/export/hotspots.csv", params=params)
    assert response.status_code == 422 and "download limit" in response.json()["detail"]


def test_current_comparison_ranks_the_latest_window_against_earlier_years(client: TestClient) -> None:
    body = client.get("/api/current-comparison", params={"grid": "5km", "window_days": 30}).json()
    assert body["as_of"] == "2025-11-20"  # the earlier of the two archives' end dates
    assert body["current"]["year"] == 2025
    assert body["history"][0]["year"] == 2002 or body["history"][0]["year"] >= 2003
    assert 1 <= body["rank_among_years"] <= body["years_compared"]
    assert any(h["estimated"] for h in body["history"]) and not any(h["estimated"] for h in body["history"] if h["year"] >= 2012)
    modis = client.get("/api/current-comparison", params={"sensor": "modis"}).json()
    assert modis["as_of"] == "2025-12-31" and not any(h["estimated"] for h in modis["history"])


def test_current_comparison_validates_input(client: TestClient) -> None:
    assert client.get("/api/current-comparison", params={"window_days": 3}).status_code == 422
    assert client.get("/api/current-comparison", params={"sensor": "radar"}).status_code == 422
    assert client.get("/api/current-comparison", params={"region": "Atlantis"}).status_code == 422


def test_the_combined_comparison_is_made_on_the_steady_set(client: TestClient) -> None:
    body = client.get("/api/current-comparison", params={"grid": "5km"}).json()
    assert body["basis"] == "steady set" and "all_satellites_value" in body["current"]
    assert body["current"]["all_satellites_value"] >= body["current"]["value"]
    assert client.get("/api/current-comparison", params={"grid": "5km", "sensor": "modis"}).json()["basis"] == "sensor view"
