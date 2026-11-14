from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import create_app


def _write_fixture(root: Path) -> None:
    analysis = root / "data" / "processed" / "analysis"
    anomalies = root / "data" / "processed" / "anomalies"
    analysis.mkdir(parents=True)
    anomalies.mkdir(parents=True)
    (root / "data" / "processed" / "metadata.json").write_text(
        json.dumps({"observation_counts_by_sensor": {"VIIRS": 2}}), encoding="utf-8"
    )
    (analysis / "historical_analysis_metadata.json").write_text(
        json.dumps({"candidate_unusual_count": 1}), encoding="utf-8"
    )
    (anomalies / "anomaly_experiment_metadata.json").write_text(
        json.dumps({"comparison": {"rows_evaluated": 1}}), encoding="utf-8"
    )
    temporal = pd.DataFrame(
        [
            {"period_start": "2024-01-01", "sensor": "VIIRS", "observation_count": 2, "frp_sum": 10.0, "frp_mean": 5.0, "has_observations": True},
            {"period_start": "2024-02-01", "sensor": "VIIRS", "observation_count": 0, "frp_sum": 0.0, "frp_mean": None, "has_observations": False},
        ]
    )
    for interval in ("day", "week", "month"):
        temporal.to_csv(analysis / f"historical_{interval}.csv", index=False)
    pd.DataFrame(
        [{"cell_id": "x", "sensor": "VIIRS", "observation_count": 2, "latitude_mean": 6.0, "longitude_mean": -1.0, "frp_sum": 10.0, "first_observation": "2024-01-01", "last_observation": "2024-01-01"}]
    ).to_csv(analysis / "historical_spatial.csv", index=False)
    pd.DataFrame(
        [{"period_start": "2024-01-01", "sensor": "VIIRS", "cell_id": "x", "observation_count": 2, "candidate_unusual": True}]
    ).to_csv(analysis / "seasonal_baseline.csv", index=False)
    pd.DataFrame(
        [{"period_start": "2024-01-01", "sensor": "VIIRS", "flagged_by": "both_methods", "ml_anomaly_score": 0.4, "explanation": "candidate"}]
    ).to_csv(anomalies / "anomaly_candidates.csv", index=False)
    pd.DataFrame(
        [{"latitude": 6.0, "longitude": -1.0, "acq_datetime": "2024-01-01T01:00:00", "sensor": "VIIRS"}]
    ).to_csv(root / "data" / "processed" / "observations.csv", index=False)


def test_health_and_metadata(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/metadata").status_code == 200


def test_temporal_filters_and_pagination(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    response = TestClient(create_app(tmp_path)).get(
        "/api/temporal/month",
        params={"start_date": "2024-01-01", "end_date": "2024-01-01", "page_size": 1},
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1
    assert response.json()["data"][0]["observation_count"] == 2


def test_invalid_date_range_and_empty_result(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/temporal/day", params={"start_date": "2024-02-01", "end_date": "2024-01-01"}).status_code == 422
    empty = client.get("/api/anomalies", params={"method": "statistical_baseline_only"})
    assert empty.status_code == 200
    assert empty.json()["pagination"]["total"] == 0


def test_spatial_is_valid_geojson(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    body = TestClient(create_app(tmp_path)).get("/api/spatial").json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["geometry"]["type"] == "Point"
    assert body["crs"]["properties"]["name"] == "EPSG:4326"


def test_missing_dataset_is_explicit(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health").json()["status"] == "degraded"
    assert client.get("/api/metadata").status_code == 503