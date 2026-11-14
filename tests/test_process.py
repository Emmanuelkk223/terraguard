"""Tests for multi-product processing.

The rows below are tiny hand-written TEST FIXTURES that exercise code paths.
They are not NASA measurements and support no scientific conclusion.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_pipeline.pipeline import add_derived_fields
from data_pipeline.process import group_files_by_product, process

MODIS_HEADER = "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,type\n"
VIIRS_HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight,type\n"


def _write(root: Path) -> None:
    (root / "MODIS_SP_2024-01-10_2024-01-14.csv").write_text(
        MODIS_HEADER
        + "7.0,-1.0,300,1,1,2024-01-10,204,Aqua,MODIS,29,61.03,290,5.0,N,0\n"
        + "7.1,-1.1,300,1,1,2024-01-10,204,Terra,MODIS,30,61.03,290,5.0,N,0\n"
        + "7.2,-1.2,300,1,1,2024-01-10,1330,Terra,MODIS,80,61.03,290,5.0,D,2\n"
        + "7.2,-1.2,300,1,1,2024-01-10,1330,Terra,MODIS,80,61.03,290,5.0,D,2\n",  # exact duplicate
        encoding="utf-8",
    )
    (root / "VIIRS_NOAA20_SP_2024-01-10_2024-01-14.csv").write_text(
        VIIRS_HEADER
        + "7.0,-1.0,330,0.4,0.4,2024-01-10,39,N20,VIIRS,l,2,290,1.0,N,0\n"
        + "95.0,-1.0,330,0.4,0.4,2024-01-10,39,N20,VIIRS,h,2,290,1.0,N,0\n",  # invalid latitude
        encoding="utf-8",
    )
    (root / "notes.csv").write_text("ignore,me\n", encoding="utf-8")


def test_groups_files_by_product_and_ignores_others(tmp_path: Path) -> None:
    _write(tmp_path)
    assert set(group_files_by_product(tmp_path)) == {"MODIS_SP", "VIIRS_NOAA20_SP"}


def test_confidence_classes_are_product_specific() -> None:
    frame = pd.DataFrame(
        {
            "sensor": ["MODIS", "MODIS", "MODIS", "VIIRS", "VIIRS", "VIIRS"],
            "satellite": ["Aqua", "Terra", "Terra", "N", "N20", "N21"],
            "confidence": ["29", "30", "80", "l", "n", "h"],
            "type": [0, 0, 2, 0, 0, 3],
        }
    )
    out = add_derived_fields(frame)
    assert out["confidence_class"].tolist() == ["low", "nominal", "high", "low", "nominal", "high"]
    assert out["platform"].tolist() == ["Aqua", "Terra", "Terra", "Suomi-NPP", "NOAA-20", "NOAA-21"]
    assert out["is_presumed_vegetation_fire"].tolist() == [True, True, False, True, True, False]
    assert out["confidence"].tolist() == ["29", "30", "80", "l", "n", "h"]  # original kept


def test_process_keeps_sensors_separate_and_logs_exclusions(tmp_path: Path) -> None:
    raw, out = tmp_path / "raw", tmp_path / "out"
    raw.mkdir()
    _write(raw)
    meta = process(raw, out)
    assert meta["products"]["MODIS_SP"]["retained_records"] == 3  # duplicate removed
    assert meta["products"]["MODIS_SP"]["exclusions_by_reason"] == {"duplicate_observation": 1}
    assert meta["products"]["VIIRS_NOAA20_SP"]["exclusions_by_reason"] == {"invalid_latitude": 1}
    assert meta["observation_counts_by_sensor"] == {"MODIS": 3, "VIIRS": 1}
    assert "bounding box only" in meta["spatial_filter"]

    modis = pd.read_parquet(out / "observations" / "MODIS_SP.parquet")
    assert set(modis["sensor"]) == {"MODIS"} and set(modis["source_product"]) == {"MODIS_SP"}
    assert modis["acq_datetime"].min() == pd.Timestamp("2024-01-10 02:04")  # HHMM 204 -> 02:04 UTC


def test_covered_ranges_merge_contiguous_windows(tmp_path: Path) -> None:
    from data_pipeline.process import covered_ranges

    names = ["MODIS_SP_2024-01-01_2024-01-05.csv", "MODIS_SP_2024-01-06_2024-01-10.csv", "MODIS_SP_2024-01-16_2024-01-20.csv"]
    assert covered_ranges([Path(n) for n in names]) == [["2024-01-01", "2024-01-10"], ["2024-01-16", "2024-01-20"]]


def test_overpass_drift_reports_median_daytime_hour(tmp_path: Path) -> None:
    from data_pipeline.validation import overpass_drift

    frame = pd.DataFrame({
        "acq_datetime": pd.to_datetime(["2019-01-01 10:00", "2019-01-02 11:00", "2019-01-03 12:00", "2019-01-03 01:00"]),
        "platform": ["Terra"] * 4, "daynight": ["D", "D", "D", "N"],
    })
    frame.to_parquet(tmp_path / "x.parquet", index=False)
    assert overpass_drift(tmp_path) == {"Terra": {2019: 11.0}}  # night record ignored
