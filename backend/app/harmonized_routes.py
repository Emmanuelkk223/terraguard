"""Routes serving the harmonized calendar, map cells, series, quality and CSV exports.

Every analytic endpoint accepts a sensor view (``harmonized``, ``modis``, ``viirs``) and an
area, either a named region or a custom ``bbox=west,south,east,north``. The default view of a
named region is served from precomputed files; anything else is computed on demand from the
same cell-day table with the same code, and cached.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

from data_pipeline.area_analytics import (
    CUSTOM_LABEL, VIEW_COLUMN, activity_series, area_calendar, parse_bbox, select_cells,
)
from data_pipeline.calendar_analytics import annual_summary, seasonal_summary
from data_pipeline.harmonize import cell_centres

Grid = Literal["1km", "2km", "5km"]
Sensor = Literal["harmonized", "modis", "viirs"]
GRID_KM = {"1km": 1.0, "2km": 2.0, "5km": 5.0}
MAX_MAP_CELLS = 20000
METADATA = "harmonized/harmonization_metadata.json"
CACHE_LIMIT = 48


def register(app: FastAPI, store: Any, jsonable: Any) -> None:
    """Attach the harmonized endpoints; ``store`` is the app's DataStore."""
    cache: dict[tuple, pd.DataFrame] = {}

    def analytics(kind: str, grid: str) -> pd.DataFrame:
        return store.csv(f"analytics/{kind}_{grid}.csv")

    def known_regions(grid: str) -> set[str]:
        return set(analytics("calendar", grid)["region"].unique())

    def check_region(grid: str, region: str | None) -> None:
        if region and region not in known_regions(grid):
            raise HTTPException(422, f"Unknown region '{region}'")

    def parsed_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
        if not bbox:
            return None
        try:
            return parse_bbox(bbox)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def check_years(start_year: int | None, end_year: int | None) -> None:
        if start_year and end_year and end_year < start_year:
            raise HTTPException(422, "end_year must not be earlier than start_year")

    def year_filter(frame: pd.DataFrame, start_year: int | None, end_year: int | None) -> pd.DataFrame:
        check_years(start_year, end_year)
        if start_year:
            frame = frame[frame["year"] >= start_year]
        if end_year:
            frame = frame[frame["year"] <= end_year]
        return frame

    def cell_days_table(grid: str) -> pd.DataFrame:
        return store.parquet(f"harmonized/cell_days_{grid}.parquet")

    def national_monthly(grid: str) -> pd.DataFrame:
        return store.csv(f"harmonized/monthly_{grid}.csv")

    def tokens(grid: str) -> tuple:
        """Cache key component that changes when the underlying files are regenerated."""
        return tuple(
            (store.base / name).stat().st_mtime if store.exists(name) else None
            for name in (f"harmonized/cell_days_{grid}.parquet", f"harmonized/monthly_{grid}.csv")
        )

    def on_demand_calendar(grid: str, region: str | None, sensor: str, bbox: tuple | None) -> pd.DataFrame:
        key = ("calendar", grid, region, sensor, bbox, tokens(grid))
        if key not in cache:
            if len(cache) >= CACHE_LIMIT:
                cache.pop(next(iter(cache)))
            try:
                cache[key] = area_calendar(
                    cell_days_table(grid), GRID_KM[grid], national_monthly(grid),
                    view=sensor, region=None if bbox else region, bbox=bbox,
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return cache[key]

    def calendar_frame(grid: str, region: str, sensor: str, bbox_text: str | None) -> pd.DataFrame:
        """The calendar for the requested view and area (precomputed when it is the default view)."""
        bbox = parsed_bbox(bbox_text)
        if bbox is None:
            check_region(grid, region)
            if sensor == "harmonized":
                frame = analytics("calendar", grid)
                return frame[frame["region"] == region]
        return on_demand_calendar(grid, region, sensor, bbox)

    def area_label(region: str, bbox_text: str | None) -> str:
        return CUSTOM_LABEL if bbox_text else region

    @app.get("/api/boundaries")
    def boundaries() -> Any:
        """Ghana ADM1 outline (geoBoundaries, simplified; CC BY-SA 2.0)."""
        path = store.base.parent / "reference" / "GHA_ADM1.geojson"
        if not path.is_file():
            raise HTTPException(503, "Reference boundaries are not available")
        return Response(path.read_text(encoding="utf-8"), media_type="application/geo+json")

    @app.get("/api/harmonization")
    def harmonization() -> dict[str, Any]:
        result: dict[str, Any] = {"harmonization": store.json(METADATA)}
        if store.exists("analytics/analytics_metadata.json"):
            result["analytics"] = store.json("analytics/analytics_metadata.json")
        return result

    @app.get("/api/validation")
    def validation() -> dict[str, Any]:
        """Sensor-agreement statistics and overpass-time drift (see data_pipeline/validation.py)."""
        return store.json("analytics/validation.json")

    @app.get("/api/quality")
    def quality(grid: Grid = "5km") -> dict[str, Any]:
        """Data-quality summary: records, exclusions, missing values, coverage and sensor mix."""
        processing = store.json("metadata.json")
        harmonized = store.json(METADATA)
        national = national_monthly(grid)
        national = national[national["region"] == "Ghana"]
        complete = national["coverage_ok"].astype(bool)
        platforms: dict[str, int] = {}
        for info in processing.get("products", {}).values():
            for name, count in info.get("records_by_platform", {}).items():
                platforms[name] = platforms.get(name, 0) + int(count)
        keep = ("source_files", "loaded_records", "retained_records", "exclusions_by_reason", "missing_values",
                "earliest_observation", "latest_observation", "covered_ranges", "records_by_confidence_class",
                "non_vegetation_type_records")
        return {
            "products": {
                name: {k: info[k] for k in keep if k in info}
                for name, info in processing.get("products", {}).items()
            },
            "records_by_platform": platforms,
            "harmonization": {
                "observations_used": harmonized.get("observations_used"),
                "observations_outside_ghana_excluded": harmonized.get("observations_outside_ghana_excluded"),
                "platforms": harmonized.get("platforms"),
                "coverage_rule": harmonized.get("coverage_rule"),
                "spatial_clip": harmonized.get("spatial_clip"),
            },
            "coverage": {
                "months_total": int(len(national)),
                "months_complete": int(complete.sum()),
                "incomplete_months": [str(m)[:7] for m in national.loc[~complete, "month"]],
            },
        }

    @app.get("/api/model-comparison")
    def model_comparison() -> dict[str, Any]:
        """Baseline vs Isolation Forest comparison (see data_pipeline/model_comparison.py)."""
        return store.json("analytics/model_comparison.json")

    @app.get("/api/regions")
    def regions(grid: Grid = "5km") -> dict[str, Any]:
        names = sorted(known_regions(grid))
        return {"regions": ["Ghana"] + [n for n in names if n != "Ghana"]}

    @app.get("/api/calendar")
    def calendar_rows(
        grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
        start_year: int | None = Query(None, ge=1990, le=2100),
        end_year: int | None = Query(None, ge=1990, le=2100),
    ) -> dict[str, Any]:
        frame = year_filter(calendar_frame(grid, region, sensor, bbox), start_year, end_year)
        return {"grid": grid, "region": area_label(region, bbox), "sensor": sensor,
                "total": len(frame), "data": jsonable(frame)}

    @app.get("/api/calendar/anomalies")
    def calendar_anomalies(
        grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
        direction: Literal["high", "low"] | None = None,
    ) -> dict[str, Any]:
        frame = calendar_frame(grid, region, sensor, bbox)
        flagged = frame[frame["status"].isin(["unusually_high", "unusually_low"])]
        if direction:
            flagged = flagged[flagged["status"] == f"unusually_{direction}"]
        flagged = flagged.reindex(flagged["robust_score"].abs().sort_values(ascending=False).index).copy()
        # Cross-sensor corroboration: is the same month also unusual in each sensor's own series?
        for view in ("modis", "viirs"):
            other = calendar_frame(grid, region, view, bbox).set_index(["year", "month"])["status"]
            flagged[f"{view}_status"] = [other.get((y, m)) for y, m in zip(flagged["year"], flagged["month"])]
        return {"total": len(flagged), "data": jsonable(flagged)}

    @app.get("/api/seasonal")
    def seasonal(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized",
                 bbox: str | None = None) -> dict[str, Any]:
        if sensor == "harmonized" and not bbox:
            check_region(grid, region)
            frame = analytics("seasonal", grid)
            frame = frame[frame["region"] == region]
        else:
            frame = seasonal_summary(calendar_frame(grid, region, sensor, bbox))
        return {"grid": grid, "region": area_label(region, bbox), "data": jsonable(frame)}

    @app.get("/api/seasonal/regions")
    def seasonal_regions(grid: Grid = "5km") -> dict[str, Any]:
        """Seasonal statistics for every region at once (harmonized view), for regional comparison."""
        return {"grid": grid, "data": jsonable(analytics("seasonal", grid))}

    @app.get("/api/annual")
    def annual(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized",
               bbox: str | None = None) -> dict[str, Any]:
        if sensor == "harmonized" and not bbox:
            check_region(grid, region)
            frame = analytics("annual", grid)
            frame = frame[frame["region"] == region]
        else:
            frame = annual_summary(calendar_frame(grid, region, sensor, bbox))
        return {"grid": grid, "region": area_label(region, bbox), "data": jsonable(frame)}

    # ---- date-range cell data (map, exports, series) ----

    def period(start: date | None, end: date | None, year: int | None, month: int | None) -> tuple[pd.Timestamp, pd.Timestamp]:
        if start is None and end is None and year and month:
            first = pd.Timestamp(year=year, month=month, day=1)
            return first, first + pd.offsets.MonthEnd(0)
        if start is None or end is None:
            raise HTTPException(422, "Provide start and end dates (or year and month)")
        if end < start:
            raise HTTPException(422, "end must not be earlier than start")
        return pd.Timestamp(start), pd.Timestamp(end)

    def cells_in_period(grid: str, first: pd.Timestamp, last: pd.Timestamp, region: str | None,
                        bbox_text: str | None) -> pd.DataFrame:
        path = f"harmonized/cell_days_{grid}.parquet"
        if not store.exists(path):
            raise HTTPException(503, f"Analytical dataset '{path}' is not available")
        frame = pd.read_parquet(store.base / path, filters=[("date", ">=", first), ("date", "<=", last)])
        bbox = parsed_bbox(bbox_text)
        if bbox is None:
            check_region(grid, region)
        return select_cells(frame, GRID_KM[grid], region=None if bbox else region, bbox=bbox)

    def aggregate_cells(frame: pd.DataFrame, grid: str, sensor: str) -> pd.DataFrame:
        columns = ["grid_x", "grid_y", "active_days", "modis_detections", "viirs_detections",
                   "days_both", "longitude", "latitude"]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        keys = ["grid_x", "grid_y"]
        in_view = frame if sensor == "harmonized" else frame[frame[f"{sensor}_detections"] > 0]
        active = in_view.groupby(keys, observed=True)["date"].nunique().rename("active_days")
        sums = (
            frame.assign(is_both=frame["occupied_by"] == "both")
            .groupby(keys, observed=True)
            .agg(modis_detections=("modis_detections", "sum"), viirs_detections=("viirs_detections", "sum"),
                 days_both=("is_both", "sum"))
        )
        cells = pd.concat([active, sums], axis=1, join="inner").reset_index()
        return cell_centres(cells, GRID_KM[grid])

    @app.get("/api/map/cells")
    def map_cells(
        grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
        start: date | None = None, end: date | None = None,
        year: int | None = Query(None, ge=1990, le=2100), month: int | None = Query(None, ge=1, le=12),
    ) -> dict[str, Any]:
        first, last = period(start, end, year, month)
        cells = aggregate_cells(cells_in_period(grid, first, last, region, bbox), grid, sensor)
        truncated = len(cells) > MAX_MAP_CELLS
        if truncated:
            cells = cells.nlargest(MAX_MAP_CELLS, "active_days")
        features = [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
             "properties": {k: r[k] for k in ("active_days", "modis_detections", "viirs_detections", "days_both")}}
            for r in jsonable(cells)
        ]
        return {
            "type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features, "truncated": truncated,
            "period": [first.date().isoformat(), last.date().isoformat()],
            "note": "Cell centres; active_days = days in the period with at least one detection in the chosen sensor view.",
        }

    def series_frame(grid: str, region: str, sensor: str, bbox_text: str | None, first: pd.Timestamp,
                     last: pd.Timestamp, interval: str) -> pd.DataFrame:
        selected = cells_in_period(grid, first, last, region, bbox_text)
        try:
            return activity_series(selected, first, last, interval, view=sensor)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/series")
    def series(
        start: date, end: date, interval: Literal["day", "week"] = "day", grid: Grid = "5km",
        region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
    ) -> dict[str, Any]:
        first, last = period(start, end, None, None)
        frame = series_frame(grid, region, sensor, bbox, first, last, interval)
        return {"interval": interval, "sensor": sensor, "area": area_label(region, bbox), "data": jsonable(frame)}

    # ---- exports ----

    def csv_response(frame: pd.DataFrame, filename: str, header: dict[str, Any]) -> Response:
        meta = store.json(METADATA) if store.exists(METADATA) else {}
        lines = [
            "# TerraGuard export",
            "# source: NASA FIRMS standard-processing MODIS and VIIRS active-fire detections",
            f"# harmonization: {meta.get('harmonization_method', 'n/a')} version {meta.get('harmonization_version', 'n/a')}",
            "# note: counts are satellite detections or active cell-days, not unique fires; sensors are not calibrated to each other",
        ] + [f"# {k}: {v}" for k, v in header.items()]
        body = "\n".join(lines) + "\n" + frame.to_csv(index=False)
        return Response(body, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    def describe_area(region: str, bbox_text: str | None) -> str:
        return f"custom bounding box (west,south,east,north) {bbox_text}" if bbox_text else region

    @app.get("/api/export/calendar.csv")
    def export_calendar(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized",
                        bbox: str | None = None, start_year: int | None = None, end_year: int | None = None) -> Response:
        frame = year_filter(calendar_frame(grid, region, sensor, bbox), start_year, end_year)
        years = f"{frame['year'].min()}-{frame['year'].max()}" if len(frame) else "none"
        safe = area_label(region, bbox).replace(" ", "_")
        return csv_response(frame, f"terraguard_calendar_{safe}_{sensor}_{grid}.csv",
                            {"area": describe_area(region, bbox), "sensor view": sensor, "grid": grid, "years": years})

    @app.get("/api/export/cells.csv")
    def export_cells(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
                     start: date | None = None, end: date | None = None,
                     year: int | None = Query(None, ge=1990, le=2100), month: int | None = Query(None, ge=1, le=12)) -> Response:
        first, last = period(start, end, year, month)
        cells = aggregate_cells(cells_in_period(grid, first, last, region, bbox), grid, sensor)
        label = f"{first.date()}_{last.date()}"
        return csv_response(cells, f"terraguard_cells_{label}_{sensor}_{grid}.csv",
                            {"area": describe_area(region, bbox), "sensor view": sensor, "grid": grid,
                             "period": f"{first.date()} to {last.date()}"})

    @app.get("/api/export/series.csv")
    def export_series(start: date, end: date, interval: Literal["day", "week"] = "day", grid: Grid = "5km",
                      region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None) -> Response:
        first, last = period(start, end, None, None)
        frame = series_frame(grid, region, sensor, bbox, first, last, interval)
        return csv_response(frame, f"terraguard_{interval}_{first.date()}_{last.date()}_{sensor}_{grid}.csv",
                            {"area": describe_area(region, bbox), "sensor view": sensor, "grid": grid,
                             "interval": interval, "period": f"{first.date()} to {last.date()}"})


__all__ = ["register", "VIEW_COLUMN"]
