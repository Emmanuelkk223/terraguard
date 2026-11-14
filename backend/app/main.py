"""Read-only TerraGuard analytical API.

Serves generated CSV/JSON artifacts under ``<root>/data/processed``. It never
acquires data, reruns analysis, or merges sensor records.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.harmonized_routes import register as register_harmonized_routes
from backend.app.places_routes import register as register_places_routes

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_PAGE_SIZE = 1000

Interval = Literal["day", "week", "month"]

METADATA_FILES = {
    "source": "metadata.json",
    "historical_analysis": "analysis/historical_analysis_metadata.json",
    "anomaly_experiment": "anomalies/anomaly_experiment_metadata.json",
}
REQUIRED_FOR_HEALTH = ("metadata.json", "analysis/historical_day.csv")


class DataStore:
    """Cached, mtime-aware access to generated artifacts."""

    def __init__(self, root: Path) -> None:
        self.base = Path(root) / "data" / "processed"
        self._cache: dict[str, tuple[float, Any]] = {}

    def exists(self, relative: str) -> bool:
        return (self.base / relative).is_file()

    def _load(self, relative: str, reader: Any) -> Any:
        path = self.base / relative
        if not path.is_file():
            # Generic message: never expose filesystem paths.
            raise HTTPException(503, f"Analytical dataset '{relative}' is not available")
        mtime = path.stat().st_mtime
        cached = self._cache.get(relative)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            value = reader(path)
        except Exception as exc:  # a file being rewritten, truncated or corrupt: report it, never cache it
            raise HTTPException(
                503, f"Analytical dataset '{relative}' could not be read; it may be updating. Retry in a moment."
            ) from exc
        self._cache[relative] = (mtime, value)
        return value

    def csv(self, relative: str) -> pd.DataFrame:
        return self._load(relative, pd.read_csv)

    def parquet(self, relative: str) -> pd.DataFrame:
        return self._load(relative, pd.read_parquet)

    def json(self, relative: str) -> Any:
        return self._load(relative, lambda p: json.loads(p.read_text(encoding="utf-8")))


def _jsonable(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Records with NaN/NaT converted to None so the JSON is standards-valid."""
    cleaned = frame.astype(object).where(frame.notna(), None)
    records = cleaned.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and not math.isfinite(value):
                record[key] = None
            elif hasattr(value, "item"):  # numpy scalar
                record[key] = value.item()
    return records


def _check_range(start: date | None, end: date | None) -> None:
    if start and end and end < start:
        raise HTTPException(422, "end_date must not be earlier than start_date")


def _filter(
    frame: pd.DataFrame,
    *,
    date_column: str | None,
    start: date | None,
    end: date | None,
    sensor: str | None,
) -> pd.DataFrame:
    _check_range(start, end)
    result = frame
    if sensor and "sensor" in result:
        result = result[result["sensor"].astype("string").str.upper() == sensor.upper()]
    if date_column and date_column in result and (start or end):
        days = pd.to_datetime(result[date_column], errors="coerce").dt.normalize()
        keep = pd.Series(True, index=result.index)
        if start:
            keep &= days >= pd.Timestamp(start)
        if end:
            keep &= days <= pd.Timestamp(end)
        result = result[keep]
    return result


def _page(frame: pd.DataFrame, page: int, page_size: int) -> dict[str, Any]:
    total = len(frame)
    pages = math.ceil(total / page_size) if total else 0
    window = frame.iloc[(page - 1) * page_size : page * page_size]
    return {
        "data": _jsonable(window),
        "pagination": {"page": page, "page_size": page_size, "total": total, "pages": pages},
    }


def create_app(root: Path | str = REPO_ROOT) -> FastAPI:
    store = DataStore(Path(root))
    app = FastAPI(
        title="TerraGuard Analytical API",
        version="0.1.0",
        description=(
            "Read-only access to generated satellite active-fire analytics. "
            "Counts are detection records, not unique fires; sensors are never summed."
        ),
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        available = {name: store.exists(name) for name in REQUIRED_FOR_HEALTH}
        harmonized = {
            name: store.exists(name)
            for name in ("harmonized/harmonization_metadata.json", "analytics/calendar_5km.csv")
        }
        return {
            "status": "ok" if all(available.values()) or all(harmonized.values()) else "degraded",
            "datasets": {**available, **harmonized},
        }

    @app.get("/api/metadata")
    def metadata() -> dict[str, Any]:
        result: dict[str, Any] = {"source": store.json(METADATA_FILES["source"])}
        for key in ("historical_analysis", "anomaly_experiment"):
            if store.exists(METADATA_FILES[key]):
                result[key] = store.json(METADATA_FILES[key])
        return result

    @app.get("/api/temporal/{interval}")
    def temporal(
        interval: Interval,
        start_date: date | None = None,
        end_date: date | None = None,
        sensor: str | None = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    ) -> dict[str, Any]:
        frame = _filter(
            store.csv(f"analysis/historical_{interval}.csv"),
            date_column="period_start", start=start_date, end=end_date, sensor=sensor,
        )
        return _page(frame, page, page_size)

    @app.get("/api/spatial")
    def spatial(
        sensor: str | None = None,
        cell_id: str | None = None,
    ) -> dict[str, Any]:
        frame = store.csv("analysis/historical_spatial.csv")
        frame = _filter(frame, date_column=None, start=None, end=None, sensor=sensor)
        if cell_id:
            frame = frame[frame["cell_id"] == cell_id]
        features = []
        for record in _jsonable(frame):
            lon, lat = record.get("longitude_mean"), record.get("latitude_mean")
            if lon is None or lat is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": record,
                }
            )
        return {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features,
        }

    @app.get("/api/baselines")
    def baselines(
        start_date: date | None = None,
        end_date: date | None = None,
        sensor: str | None = None,
        cell_id: str | None = None,
        candidates_only: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    ) -> dict[str, Any]:
        frame = _filter(
            store.csv("analysis/seasonal_baseline.csv"),
            date_column="period_start", start=start_date, end=end_date, sensor=sensor,
        )
        if cell_id and "cell_id" in frame:
            frame = frame[frame["cell_id"] == cell_id]
        if candidates_only and "candidate_unusual" in frame:
            frame = frame[frame["candidate_unusual"].astype(str).str.lower() == "true"]
        return _page(frame, page, page_size)

    @app.get("/api/anomalies")
    def anomalies(
        start_date: date | None = None,
        end_date: date | None = None,
        sensor: str | None = None,
        method: str | None = Query(None, description="Matches the 'flagged_by' label"),
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    ) -> dict[str, Any]:
        frame = _filter(
            store.csv("anomalies/anomaly_candidates.csv"),
            date_column="period_start", start=start_date, end=end_date, sensor=sensor,
        )
        if method and "flagged_by" in frame:
            frame = frame[frame["flagged_by"] == method]
        return _page(frame, page, page_size)

    @app.get("/api/hotspots")
    def hotspots(
        start_date: date | None = None,
        end_date: date | None = None,
        sensor: str | None = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    ) -> dict[str, Any]:
        frame = _filter(
            store.csv("observations.csv"),
            date_column="acq_datetime", start=start_date, end=end_date, sensor=sensor,
        )
        return _page(frame, page, page_size)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    register_harmonized_routes(app, store, _jsonable)
    register_places_routes(app, store)
    return app


app = create_app()
