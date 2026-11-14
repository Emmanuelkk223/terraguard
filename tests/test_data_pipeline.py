import json
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.pipeline import (
    aggregate_observations,
    filter_to_boundary,
    load_geojson_geometry,
    parse_acquisition_datetime,
    validate_observations,
)
from data_pipeline.analyze import build_summary
from data_pipeline.historical import seasonal_baseline, spatial_activity, temporal_activity
from data_pipeline.acquire import download_historical_area, download_recent_area


def test_timestamp_parser_handles_firms_hhmm_values():
    result = parse_acquisition_datetime(["2024-01-02"], ["35"])
    assert result.iloc[0] == pd.Timestamp("2024-01-02 00:35:00")


def test_validation_reports_invalid_rows_and_duplicates():
    frame = pd.DataFrame(
        {
            "latitude": [7.0, 95.0, 7.0],
            "longitude": [-1.0, -1.0, -1.0],
            "acq_datetime": [pd.Timestamp("2024-01-01")] * 3,
            "satellite": ["N", "N", "N"],
            "instrument": ["VIIRS", "VIIRS", "VIIRS"],
            "source_product": ["VIIRS_SNPP", "VIIRS_SNPP", "VIIRS_SNPP"],
        }
    )
    valid, exclusions = validate_observations(frame)
    assert len(valid) == 1
    assert set(exclusions["reason"]) == {"invalid_latitude", "duplicate_observation"}


def test_boundary_filter_excludes_neighbouring_points(tmp_path):
    boundary = tmp_path / "ghana.geojson"
    boundary.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[-2, 5], [1, 5], [1, 10], [-2, 10], [-2, 5]]
                ],
            }
        ),
        encoding="utf-8",
    )
    frame = pd.DataFrame(
        {
            "latitude": [7.0, 7.0],
            "longitude": [0.0, 2.0],
        }
    )
    retained, exclusions = filter_to_boundary(frame, load_geojson_geometry(boundary))
    assert len(retained) == 1
    assert exclusions.iloc[0]["reason"] == "outside_ghana_boundary"


def test_aggregation_preserves_sensor_identity():
    frame = pd.DataFrame(
        {
            "latitude": [7.0, 7.01],
            "longitude": [-1.0, -1.01],
            "acq_datetime": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "sensor": ["MODIS", "VIIRS"],
            "frp": [10.0, 20.0],
        }
    )
    summary = aggregate_observations(frame, period="week", cell_size_km=5)
    assert set(summary["sensor"]) == {"MODIS", "VIIRS"}
    assert summary["observation_count"].sum() == 2


def test_exploratory_summary_reports_observations_not_fire_counts():
    summary = build_summary(
        pd.DataFrame(
            {
                "acq_datetime": ["2024-01-01T12:00:00"],
                "sensor": ["VIIRS"],
                "confidence": ["nominal"],
                "frp": [12.5],
            }
        )
    )
    assert summary["observation_count"] == 1
    assert summary["by_year"] == {"2024": 1}
    assert summary["frp"]["median"] == 12.5


def test_temporal_activity_includes_zero_periods_without_merging_sensors():
    observations = pd.DataFrame(
        {
            "acq_datetime": pd.to_datetime(["2024-01-01", "2024-01-03"]),
            "sensor": ["MODIS", "VIIRS"],
            "latitude": [7.0, 7.0],
            "longitude": [-1.0, -1.0],
            "frp": [10.0, 20.0],
        }
    )
    result = temporal_activity(observations, period="day")
    assert len(result) == 6
    empty = result.loc[
        (result["period_start"] == pd.Timestamp("2024-01-02"))
        & (result["sensor"] == "MODIS")
    ].iloc[0]
    assert empty["observation_count"] == 0
    assert not empty["has_observations"]


def test_weekly_period_starts_and_empty_rows_align():
    observations = pd.DataFrame(
        {
            "acq_datetime": pd.to_datetime(["2024-01-01", "2024-01-15"]),
            "sensor": ["VIIRS", "VIIRS"],
            "latitude": [7.0, 7.0],
            "longitude": [-1.0, -1.0],
            "frp": [10.0, 20.0],
        }
    )
    result = temporal_activity(observations, period="week")
    assert result["period_start"].tolist() == list(
        pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"])
    )
    assert result["has_observations"].tolist() == [True, False, True]


def test_spatial_activity_keeps_sensor_rows_separate():
    observations = pd.DataFrame(
        {
            "acq_datetime": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "sensor": ["MODIS", "VIIRS"],
            "latitude": [7.0, 7.0],
            "longitude": [-1.0, -1.0],
            "frp": [10.0, 20.0],
        }
    )
    result = spatial_activity(observations)
    assert set(result["sensor"]) == {"MODIS", "VIIRS"}
    assert result["observation_count"].tolist() == [1, 1]


def test_seasonal_baseline_is_leave_one_out_and_requires_history():
    activity = pd.DataFrame(
        {
            "period_start": pd.to_datetime(
                ["2020-01-06", "2021-01-04", "2022-01-03", "2023-01-02"]
            ),
            "sensor": ["VIIRS"] * 4,
            "cell_id": ["cell"] * 4,
            "month": [1] * 4,
            "observation_count": [1, 1, 1, 10],
        }
    )
    result = seasonal_baseline(activity, min_samples=3, threshold=3.5)
    high = result.iloc[-1]
    assert high["baseline_sample_count"] == 3
    assert high["baseline_median"] == 1
    assert high["candidate_unusual"]
    insufficient = seasonal_baseline(activity.iloc[:2], min_samples=3)
    assert not insufficient["baseline_eligible"].any()


def test_seasonal_baseline_handles_multiple_groups():
    activity = pd.DataFrame(
        {
            "period_start": pd.to_datetime(
                ["2020-01-06", "2021-01-04", "2020-01-06", "2021-01-04"]
            ),
            "sensor": ["VIIRS", "VIIRS", "MODIS", "MODIS"],
            "cell_id": ["a", "a", "b", "b"],
            "month": [1, 1, 1, 1],
            "observation_count": [1, 1, 1, 9],
        }
    )
    result = seasonal_baseline(activity, min_samples=1)
    assert result.loc[result["sensor"] == "MODIS", "candidate_unusual"].any()


def test_recent_area_configuration_rejects_historical_range():
    with pytest.raises(ValueError, match="between 1 and 5"):
        download_recent_area(
            map_key="key",
            source="VIIRS_SNPP_NRT",
            area="-3.26,4.74,1.20,11.17",
            days=6,
            output_dir=Path("data/raw"),
        )