"""Tests that outputs are written atomically and that unreadable files give a clear, retryable 503."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from data_pipeline import atomic


def test_atomic_writes_round_trip_and_leave_no_temp_files(tmp_path: Path) -> None:
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    atomic.to_csv(frame, tmp_path / "sub" / "t.csv", index=False)  # creates the folder
    atomic.to_parquet(frame, tmp_path / "t.parquet", index=False)
    atomic.write_text(tmp_path / "t.json", '{"k": 1}')
    atomic.write_bytes(tmp_path / "t.bin", b"abc")
    assert pd.read_csv(tmp_path / "sub" / "t.csv").equals(frame) and pd.read_parquet(tmp_path / "t.parquet").equals(frame)
    assert (tmp_path / "t.json").read_text() == '{"k": 1}' and (tmp_path / "t.bin").read_bytes() == b"abc"
    assert not [p for p in tmp_path.rglob("*") if p.name.endswith(".tmp")]


def test_failed_write_keeps_the_previous_file_intact(tmp_path: Path) -> None:
    target = tmp_path / "data.csv"
    atomic.write_text(target, "old,content\n")

    class Boom:
        def to_csv(self, *_a, **_k) -> None:
            raise RuntimeError("disk full")

    with pytest.raises(RuntimeError):
        atomic.to_csv(Boom(), target)  # type: ignore[arg-type]
    assert target.read_text() == "old,content\n"  # readers still see the complete old file
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]  # and no half-written leftovers


def test_replace_retries_when_the_target_is_briefly_locked(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "locked.txt"
    atomic.write_text(target, "v1")
    real, calls = os.replace, {"n": 0}

    def flaky(src, dst):  # Windows refuses to replace a file that another process has open for a moment
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("in use")
        return real(src, dst)

    monkeypatch.setattr(atomic.os, "replace", flaky)
    monkeypatch.setattr(atomic, "REPLACE_PAUSE", 0)
    atomic.write_text(target, "v2")
    assert target.read_text() == "v2" and calls["n"] == 3


def test_api_reports_unreadable_data_as_a_retryable_503(tmp_path: Path) -> None:
    base = tmp_path / "data" / "processed" / "harmonized"
    base.mkdir(parents=True)
    (base / "cell_days_5km.parquet").write_bytes(b"PAR1 this is half written")  # what a reader sees mid-write
    (base / "monthly_5km.csv").write_text("region,month\n")
    client = TestClient(create_app(tmp_path))
    ranged = client.get("/api/map/cells", params={"start": "2018-01-01", "end": "2018-01-31"})
    assert ranged.status_code == 503 and "may be updating" in ranged.json()["detail"]
    assert "Traceback" not in ranged.text and str(tmp_path) not in ranged.text  # no internals or paths leaked
    series = client.get("/api/series", params={"start": "2018-01-01", "end": "2018-01-31"})
    assert series.status_code == 503
