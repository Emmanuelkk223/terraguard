"""West Africa extension: country assignment, month grouping and the Ghana-first API routing (TEST DATA)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from data_pipeline.calendar_analytics import run
from data_pipeline.countries import COUNTRIES, ORDER, Countries, bounding_box, country_bounds
from data_pipeline.harmonize import archive_coverage, harmonized_cell_days, monthly_summary, sensor_cell_days
from data_pipeline.westafrica import build_mapping, complete_regions, month_groups

REFERENCE = Path(__file__).resolve().parents[1] / "data" / "reference"
PLATFORMS = ("Terra", "Aqua", "Suomi-NPP")
COVERED = {"MODIS_SP": [["2000-11-01", "2025-12-31"]], "VIIRS_SNPP_SP": [["2012-01-20", "2025-12-31"]]}


def test_ghana_is_first_then_neighbours_then_the_rest() -> None:
    assert ORDER[0] == "Ghana"
    assert ORDER[1:4] == ["Côte d'Ivoire", "Togo", "Burkina Faso"]
    assert len(COUNTRIES) == 16 and len(set(ORDER)) == 16
    assert ORDER[4:] == sorted(ORDER[4:], key=lambda n: n)  # the rest alphabetical


def test_points_are_assigned_to_the_right_country() -> None:
    countries = Countries(REFERENCE / "WA_ADM0.geojson")
    lon = np.array([-0.2, 3.4, -4.0, -12.0, -40.0, 2.1])
    lat = np.array([5.6, 6.45, 5.3, 8.5, 5.0, 13.5])
    assert list(countries.country_for(lon, lat)) == ["Ghana", "Nigeria", "Côte d'Ivoire", "Sierra Leone", "", "Niger"]


def test_download_area_covers_every_country_and_ghana_box_sits_inside() -> None:
    west, south, east, north = bounding_box(REFERENCE / "WA_ADM0.geojson")
    assert west < -25 and east > 15 and south < 4.5 and north > 27
    bounds = country_bounds(REFERENCE / "WA_ADM0.geojson")
    assert len(bounds) == 16 and bounds["Ghana"][0] > west


def test_raw_files_are_grouped_by_the_month_their_window_starts() -> None:
    files = [Path(f"MODIS_SP_2020-12-28_2021-01-01.csv"), Path("MODIS_SP_2021-01-02_2021-01-06.csv"), Path("MODIS_SP_2021-02-01_2021-02-05.csv")]
    groups = month_groups(files)
    assert list(groups) == ["2020-12", "2021-01", "2021-02"] and len(groups["2021-01"]) == 1


def test_a_cell_takes_the_country_with_most_of_its_detections(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    rows = [("2020-01-01", 1, 1, "MODIS", "Togo", 5), ("2020-01-02", 1, 1, "MODIS", "Ghana", 2), ("2020-01-01", 2, 2, "VIIRS", "Ghana", 3)]
    pd.DataFrame(rows, columns=["date", "grid_x", "grid_y", "sensor", "country", "detections"]).assign(
        date=lambda d: pd.to_datetime(d["date"])).to_parquet(work / "agg_MODIS_SP_2020-01.parquet", index=False)
    mapping = build_mapping(work).set_index(["grid_x", "grid_y"])["region"]
    assert mapping[(1, 1)] == "Togo" and mapping[(2, 2)] == "Ghana"


def test_every_country_gets_every_month_even_when_quiet() -> None:
    months = pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"])
    national = pd.DataFrame({"region": "West Africa", "month": months, "active_cell_days": [9, 8, 7], "modis_cell_days": [9, 8, 7],
                             "coverage_ok": True})
    togo = pd.DataFrame({"region": "Togo", "month": months[[0]], "active_cell_days": [4], "modis_cell_days": [4]})
    result = complete_regions(pd.concat([national, togo], ignore_index=True), "West Africa")
    quiet = result[(result["region"] == "Togo")].sort_values("month")
    assert list(quiet["active_cell_days"]) == [4, 0, 0] and quiet["coverage_ok"].all()


# ---- API: Ghana first, other countries from the West Africa dataset ----

def _observations(country_boxes: dict[str, tuple[float, float]]) -> pd.DataFrame:
    rows = []
    for year in range(2003, 2026):
        for month in (1, 2, 12):
            for name, (lat, lon) in country_boxes.items():
                for i in range(3 + (year % 3)):
                    rows.append((lat + i * 0.1, lon, f"{year}-{month:02d}-10 10:30", "MODIS", "Aqua", name))
                    if year >= 2012:
                        rows.append((lat + i * 0.1, lon, f"{year}-{month:02d}-10 13:30", "VIIRS", "Suomi-NPP", name))
    frame = pd.DataFrame(rows, columns=["latitude", "longitude", "acq_datetime", "sensor", "platform", "country"])
    frame["acq_datetime"] = pd.to_datetime(frame["acq_datetime"])
    frame["frp"] = 1.0
    return frame


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    base = tmp_path / "data" / "processed"
    (tmp_path / "data" / "reference").mkdir(parents=True)
    for name in ("GHA_ADM1.geojson", "WA_ADM0.geojson"):
        shutil.copy(REFERENCE / name, tmp_path / "data" / "reference" / name)
    for scope, areas, national, prefix in (
        ("ghana", {"Ashanti": (6.7, -1.6), "Northern": (9.4, -0.8)}, "Ghana", ""),
        ("wa", {"Ghana": (6.7, -1.6), "Nigeria": (9.0, 7.5), "Togo": (8.0, 1.0)}, "West Africa", "wa/"),
    ):
        obs = _observations(areas)
        cell_days = harmonized_cell_days(sensor_cell_days(obs, 5.0))
        cells = obs.assign(grid=lambda d: d["latitude"].round(0))
        cell_days["region"] = ["Nigeria" if y > 150 else ("Togo" if y > 140 else "Ghana") for y in cell_days["grid_y"]] if scope == "wa" \
            else ["Northern" if y > 160 else "Ashanti" for y in cell_days["grid_y"]]
        months = cell_days["date"].dt.to_period("M").dt.start_time
        monthly = monthly_summary(cell_days, archive=archive_coverage(months, COVERED, PLATFORMS), national_name=national)
        for grid in (("1km", "2km", "5km") if scope == "ghana" else ("5km",)):
            folder = base / (prefix + "harmonized")
            folder.mkdir(parents=True, exist_ok=True)
            cell_days.to_parquet(folder / f"cell_days_{grid}.parquet", index=False)
            monthly.to_csv(folder / f"monthly_{grid}.csv", index=False)
            run(folder / f"monthly_{grid}.csv", base / (prefix + "analytics"), min_samples=5)
        (base / (prefix + "metadata.json")).write_text(json.dumps({"products": {
            "MODIS_SP": {"covered_ranges": [["2000-11-01", "2025-12-31"]]},
            "VIIRS_SNPP_SP": {"covered_ranges": [["2012-01-20", "2025-11-20"]]}}}), encoding="utf-8")
        if scope == "wa":
            for product, sensor in (("MODIS_SP", "MODIS"), ("VIIRS_SNPP_SP", "VIIRS")):
                folder = base / "wa" / "observations" / product
                folder.mkdir(parents=True)
                part = obs[obs["sensor"] == sensor].assign(satellite="x", confidence="n", confidence_class="nominal", daynight="D", source_product=product)
                part.to_parquet(folder / "all.parquet", index=False)
    return TestClient(create_app(tmp_path))


def test_areas_list_ghana_first_then_its_regions_then_west_africa(client: TestClient) -> None:
    body = client.get("/api/areas").json()
    assert body["default"] == "Ghana" and body["west_africa_available"]
    labels = [g["label"] for g in body["groups"]]
    assert labels[:3] == ["Ghana", "Ghana regions", "West Africa"]
    assert body["groups"][0]["areas"][0]["grids"] == ["1km", "2km", "5km"]
    assert body["groups"][2]["areas"][0]["grids"] == ["5km"]
    assert "Nigeria" in [a["name"] for g in body["groups"] for a in g["areas"]]


def test_ghana_keeps_its_full_detail_and_other_countries_are_five_km(client: TestClient) -> None:
    assert client.get("/api/calendar", params={"region": "Ghana", "grid": "1km"}).status_code == 200
    assert client.get("/api/calendar", params={"region": "Ashanti", "grid": "2km"}).status_code == 200
    nigeria = client.get("/api/calendar", params={"region": "Nigeria", "grid": "5km"})
    assert nigeria.status_code == 200 and nigeria.json()["data"][0]["region"] == "Nigeria"
    refused = client.get("/api/calendar", params={"region": "Nigeria", "grid": "1km"})
    assert refused.status_code == 422 and "5 km" in refused.json()["detail"]
    assert client.get("/api/calendar", params={"region": "West Africa", "grid": "5km"}).status_code == 200
    assert client.get("/api/calendar", params={"region": "Atlantis", "grid": "5km"}).status_code == 422


def test_a_box_outside_ghana_is_served_from_the_west_africa_data(client: TestClient) -> None:
    abuja = client.get("/api/calendar", params={"bbox": "6.5,8.5,8.5,9.5", "grid": "5km"})
    assert abuja.status_code == 200 and abuja.json()["region"] == "Custom area" and abuja.json()["total"] > 0
    assert client.get("/api/calendar", params={"bbox": "6.5,8.5,8.5,9.5", "grid": "2km"}).status_code == 422
    kumasi = client.get("/api/calendar", params={"bbox": "-2.0,6.0,-1.0,7.5", "grid": "1km"})
    assert kumasi.status_code == 200  # inside Ghana: full detail


def test_map_cells_series_and_hotspots_work_for_another_country(client: TestClient) -> None:
    cells = client.get("/api/map/cells", params={"region": "Nigeria", "grid": "5km", "year": 2020, "month": 1}).json()
    assert cells["features"]
    series = client.get("/api/series", params={"region": "Togo", "grid": "5km", "start": "2020-01-01", "end": "2020-01-31"})
    assert series.status_code == 200
    hotspots = client.get("/api/hotspots/preview", params={"region": "Nigeria", "start": "2020-01-01", "end": "2020-01-31"}).json()
    assert hotspots["rows"] > 0 and set(hotspots["by_sensor"]) == {"MODIS", "VIIRS"}
    table = client.get("/api/export/hotspots.csv", params={"region": "Nigeria", "start": "2020-01-01", "end": "2020-01-31"}).text
    assert "Nigeria" in table and "Togo" not in table


def test_current_comparison_and_this_month_mode_for_west_africa(client: TestClient) -> None:
    body = client.get("/api/current-comparison", params={"region": "Nigeria", "grid": "5km", "mode": "month"}).json()
    assert body["mode"] == "month" and body["as_of"] == "2025-11-20" and body["current"]["window_start"] == "2025-11-01"


def test_boundaries_scope_returns_the_sixteen_outlines(client: TestClient) -> None:
    assert len(client.get("/api/boundaries", params={"scope": "wa"}).json()["features"]) == 16
    assert client.get("/api/boundaries").json()["features"]
