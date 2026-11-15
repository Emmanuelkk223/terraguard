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
from data_pipeline.countries import DEFAULT_BOUNDARIES, NAME_BY_ISO3, ORDER as WA_COUNTRY_ORDER, REGION_NAME as WA_NAME, ROLE_BY_NAME, country_bounds
from data_pipeline.harmonize import cell_centres
from data_pipeline.report import build_blocks, to_html, to_markdown

from backend.app.hotspot_routes import register as register_hotspot_routes

Grid = Literal["1km", "2km", "5km"]
Sensor = Literal["harmonized", "steady", "modis", "viirs"]
GRID_KM = {"1km": 1.0, "2km": 2.0, "5km": 5.0}
MAX_MAP_CELLS = 20000
METADATA = "harmonized/harmonization_metadata.json"
CACHE_LIMIT = 48
GHANA_BOX = (-3.26, 4.74, 1.20, 11.17)  # west, south, east, north: the area the detailed Ghana dataset covers


def register(app: FastAPI, store: Any, jsonable: Any) -> None:
    """Attach the harmonized endpoints; ``store`` is the app's DataStore."""
    cache: dict[tuple, pd.DataFrame] = {}

    # Two datasets: "ghana" (full detail: 1, 2 and 5 km, 16 regions) and "wa" (all of West Africa, 5 km, by country).
    # Ghana is always served from its own dataset; everything else comes from the West Africa one when it exists.
    def prefix(scope: str) -> str:
        return "" if scope == "ghana" else "wa/"

    def wa_available() -> bool:
        return store.exists("wa/harmonized/monthly_5km.csv") and store.exists("wa/analytics/calendar_5km.csv")

    def national_name(scope: str) -> str:
        return "Ghana" if scope == "ghana" else WA_NAME

    def analytics(kind: str, grid: str, scope: str = "ghana") -> pd.DataFrame:
        return store.csv(f"{prefix(scope)}analytics/{kind}_{grid}.csv")

    def known_regions(grid: str, scope: str = "ghana") -> set[str]:
        return set(analytics("calendar", grid, scope)["region"].unique())

    def scope_for(region: str | None, bbox_text: str | None) -> str:
        if not wa_available():
            return "ghana"
        bbox = parsed_bbox(bbox_text)
        if bbox is not None:
            west, south, east, north = bbox
            inside = west >= GHANA_BOX[0] and south >= GHANA_BOX[1] and east <= GHANA_BOX[2] and north <= GHANA_BOX[3]
            return "ghana" if inside else "wa"
        if not region or region == "Ghana" or region in known_regions("5km", "ghana"):
            return "ghana"
        return "wa"

    def check_grid(grid: str, scope: str) -> None:
        if scope == "wa" and grid != "5km":
            raise HTTPException(422, "Outside Ghana only the 5 km grid is available; Ghana has 1, 2 and 5 km.")

    def check_region(grid: str, region: str | None, scope: str | None = None) -> None:
        scope = scope or scope_for(region, None)
        if region and region not in known_regions(grid, scope):
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

    def cell_days_table(grid: str, scope: str = "ghana") -> pd.DataFrame:
        return store.parquet(f"{prefix(scope)}harmonized/cell_days_{grid}.parquet")

    def national_monthly(grid: str, scope: str = "ghana") -> pd.DataFrame:
        return store.csv(f"{prefix(scope)}harmonized/monthly_{grid}.csv")

    def tokens(grid: str, scope: str = "ghana") -> tuple:
        """Cache key component that changes when the underlying files are regenerated."""
        return tuple(
            (store.base / name).stat().st_mtime if store.exists(name) else None
            for name in (f"{prefix(scope)}harmonized/cell_days_{grid}.parquet", f"{prefix(scope)}harmonized/monthly_{grid}.csv")
        )

    def on_demand_calendar(grid: str, region: str | None, sensor: str, bbox: tuple | None, scope: str = "ghana") -> pd.DataFrame:
        key = ("calendar", scope, grid, region, sensor, bbox, tokens(grid, scope))
        if key not in cache:
            if len(cache) >= CACHE_LIMIT:
                cache.pop(next(iter(cache)))
            try:
                cache[key] = area_calendar(
                    cell_days_table(grid, scope), GRID_KM[grid], national_monthly(grid, scope),
                    view=sensor, region=None if bbox else region, bbox=bbox, national_name=national_name(scope),
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return cache[key]

    def calendar_frame(grid: str, region: str, sensor: str, bbox_text: str | None) -> pd.DataFrame:
        """The calendar for the requested view and area (precomputed when it is the default view)."""
        bbox = parsed_bbox(bbox_text)
        scope = scope_for(region, bbox_text)
        check_grid(grid, scope)
        if bbox is None:
            check_region(grid, region, scope)
            if sensor == "harmonized":
                frame = analytics("calendar", grid, scope)
                return frame[frame["region"] == region]
            if store.exists(f"{prefix(scope)}analytics/calendar_{sensor}_{grid}.csv"):  # precomputed for named areas
                frame = analytics(f"calendar_{sensor}", grid, scope)
                return frame[frame["region"] == region]
        return on_demand_calendar(grid, region, sensor, bbox, scope)

    def area_label(region: str, bbox_text: str | None) -> str:
        return CUSTOM_LABEL if bbox_text else region

    @app.get("/api/boundaries")
    def boundaries(scope: Literal["ghana", "wa"] = "ghana") -> Any:
        """Ghana ADM1 outline, or the sixteen national outlines with scope=wa (geoBoundaries, simplified)."""
        path = store.base.parent / "reference" / ("WA_ADM0.geojson" if scope == "wa" else "GHA_ADM1.geojson")
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

    def quality_summary(grid: str) -> dict[str, Any]:
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

    @app.get("/api/quality")
    def quality(grid: Grid = "5km") -> dict[str, Any]:
        """Data-quality summary: records, exclusions, missing values, coverage and sensor mix."""
        return quality_summary(grid)

    @app.get("/api/model-comparison")
    def model_comparison() -> dict[str, Any]:
        """Baseline vs Isolation Forest comparison (see data_pipeline/model_comparison.py)."""
        return store.json("analytics/model_comparison.json")

    @app.get("/api/sensitivity")
    def sensitivity() -> dict[str, Any]:
        """Sensitivity of national results to grid size, platform set and quality filters."""
        return store.json("analytics/sensitivity.json")

    @app.get("/api/environment/rainfall")
    def environment_rainfall(region: str = "Ghana") -> dict[str, Any]:
        """Monthly rainfall (NASA POWER, coarse gridded) and its percentile among the same calendar month in other years."""
        table = store.csv("environment/rainfall_monthly.csv")
        if region not in set(table["region"].unique()):
            raise HTTPException(422, f"No rainfall context for '{region}' (available for Ghana and its named regions)")
        return {"region": region, "unit": "mm/day and mm/month", "data": jsonable(table[table["region"] == region])}

    @app.get("/api/environment/association")
    def environment_association() -> dict[str, Any]:
        """Descriptive rank correlations between burning and rainfall anomalies. Association, not causation."""
        return store.json("environment/rainfall_association.json")

    @app.get("/api/regions")
    def regions(grid: Grid = "5km") -> dict[str, Any]:
        names = sorted(known_regions(grid))
        return {"regions": ["Ghana"] + [n for n in names if n != "Ghana"]}

    @app.get("/api/areas")
    def areas() -> dict[str, Any]:
        """Every selectable area, grouped and ordered: Ghana first, then its regions, then West Africa."""
        ghana_regions = [n for n in sorted(known_regions("5km")) if n != "Ghana"]
        boxes: dict[str, list[float]] = {}
        wa_file = store.base.parent / "reference" / "WA_ADM0.geojson"
        if wa_available() and wa_file.is_file():
            boxes = country_bounds(wa_file)
        boxes["Ghana"] = [-3.3, 4.7, 1.3, 11.2]
        boxes[WA_NAME] = [-25.6, 4.0, 16.3, 27.6]
        groups = [
            {"label": "Ghana", "areas": [{"name": "Ghana", "grids": ["1km", "2km", "5km"], "bbox": boxes["Ghana"]}]},
            {"label": "Ghana regions", "areas": [{"name": n, "grids": ["1km", "2km", "5km"]} for n in ghana_regions]},
        ]
        if wa_available():
            have = known_regions("5km", "wa")
            others = [n for n in WA_COUNTRY_ORDER if n != "Ghana" and n in have]
            groups.append({"label": "West Africa", "areas": [{"name": WA_NAME, "grids": ["5km"], "bbox": boxes[WA_NAME]}]})
            groups.append({"label": "Neighbouring countries",
                           "areas": [{"name": n, "grids": ["5km"], "bbox": boxes.get(n)} for n in others if ROLE_BY_NAME[n] == "neighbour"]})
            groups.append({"label": "Other West African countries",
                           "areas": [{"name": n, "grids": ["5km"], "bbox": boxes.get(n)} for n in others if ROLE_BY_NAME[n] != "neighbour"]})
        return {"default": "Ghana", "west_africa_available": wa_available(), "groups": [g for g in groups if g["areas"]]}

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
            scope = scope_for(region, None)
            check_grid(grid, scope)
            check_region(grid, region, scope)
            frame = analytics("seasonal", grid, scope)
            frame = frame[frame["region"] == region]
        else:
            frame = seasonal_summary(calendar_frame(grid, region, sensor, bbox))
        return {"grid": grid, "region": area_label(region, bbox), "data": jsonable(frame)}

    @app.get("/api/seasonal/regions")
    def seasonal_regions(grid: Grid = "5km", scope: Literal["ghana", "wa"] = "ghana") -> dict[str, Any]:
        """Seasonal statistics for every region at once (harmonized view), for regional comparison."""
        if scope == "wa" and not wa_available():
            raise HTTPException(503, "West Africa data has not been processed")
        check_grid(grid, scope)
        return {"grid": grid, "scope": scope, "data": jsonable(analytics("seasonal", grid, scope))}

    @app.get("/api/annual")
    def annual(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized",
               bbox: str | None = None) -> dict[str, Any]:
        if sensor == "harmonized" and not bbox:
            scope = scope_for(region, None)
            check_grid(grid, scope)
            check_region(grid, region, scope)
            frame = analytics("annual", grid, scope)
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
        scope = scope_for(region, bbox_text)
        check_grid(grid, scope)
        path = f"{prefix(scope)}harmonized/cell_days_{grid}.parquet"
        if not store.exists(path):
            raise HTTPException(503, f"Analytical dataset '{path}' is not available")
        try:
            frame = pd.read_parquet(store.base / path, filters=[("date", ">=", first), ("date", "<=", last)])
        except Exception as exc:  # being rewritten or corrupt: a retryable condition, not a server crash
            raise HTTPException(503, f"Analytical dataset '{path}' could not be read; it may be updating. Retry in a moment.") from exc
        bbox = parsed_bbox(bbox_text)
        if bbox is None:
            check_region(grid, region, scope)
        return select_cells(frame, GRID_KM[grid], region=None if bbox else region, bbox=bbox, national=national_name(scope))

    def aggregate_cells(frame: pd.DataFrame, grid: str, sensor: str) -> pd.DataFrame:
        columns = ["grid_x", "grid_y", "active_days", "modis_detections", "viirs_detections",
                   "days_both", "longitude", "latitude"]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        keys = ["grid_x", "grid_y"]
        if sensor == "harmonized":
            in_view = frame
        elif sensor == "steady":
            viirs_steady = frame["viirs_steady_detections"] if "viirs_steady_detections" in frame else frame["viirs_detections"]
            in_view = frame[(frame["modis_detections"] > 0) | (viirs_steady > 0)]
        else:
            in_view = frame[frame[f"{sensor}_detections"] > 0]
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
            "# software: TerraGuard, developed with AI-tool assistance (Claude Code); see README, section 'Built with AI assistance'",
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

    def report_blocks(grid: str, region: str, sensor: str, bbox: str | None, start: date | None, end: date | None) -> list:
        frame = calendar_frame(grid, region, sensor, bbox).copy()
        flagged = frame["status"].isin(["unusually_high", "unusually_low"])
        for view in ("modis", "viirs"):
            other = calendar_frame(grid, region, view, bbox).set_index(["year", "month"])["status"]
            frame[f"{view}_status"] = [other.get((y, m)) if f else None for y, m, f in zip(frame["year"], frame["month"], flagged)]
        period = series = None
        if start is not None or end is not None:
            first, last = period_range(start, end)
            period = (first.date().isoformat(), last.date().isoformat())
            series = series_frame(grid, region, sensor, bbox, first, last, "day" if (last - first).days < 1100 else "week")
        meta = store.json(METADATA) if store.exists(METADATA) else None
        quality = quality_summary(grid) if store.exists("metadata.json") else None
        return build_blocks(frame, area=area_label(region, bbox) + (f" ({bbox})" if bbox else ""), sensor=sensor, grid=grid,
                            meta=meta, period=period, period_series=series, quality=quality)

    def period_range(start: date | None, end: date | None) -> tuple[pd.Timestamp, pd.Timestamp]:
        if start is None or end is None:
            raise HTTPException(422, "Provide both start and end dates for a period")
        return period(start, end, None, None)

    @app.get("/api/export/report.md")
    def export_report_md(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
                         start: date | None = None, end: date | None = None) -> Response:
        text = to_markdown(report_blocks(grid, region, sensor, bbox, start, end))
        safe = area_label(region, bbox).replace(" ", "_")
        return Response(text, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="terraguard_report_{safe}_{sensor}_{grid}.md"'})

    @app.get("/api/export/report.html")
    def export_report_html(grid: Grid = "5km", region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None,
                           start: date | None = None, end: date | None = None) -> Response:
        """Self-contained printable report; open it and use Print > Save as PDF."""
        return Response(to_html(report_blocks(grid, region, sensor, bbox, start, end)), media_type="text/html")

    @app.get("/api/export/series.csv")
    def export_series(start: date, end: date, interval: Literal["day", "week"] = "day", grid: Grid = "5km",
                      region: str = "Ghana", sensor: Sensor = "harmonized", bbox: str | None = None) -> Response:
        first, last = period(start, end, None, None)
        frame = series_frame(grid, region, sensor, bbox, first, last, interval)
        return csv_response(frame, f"terraguard_{interval}_{first.date()}_{last.date()}_{sensor}_{grid}.csv",
                            {"area": describe_area(region, bbox), "sensor view": sensor, "grid": grid,
                             "interval": interval, "period": f"{first.date()} to {last.date()}"})

    register_hotspot_routes(app, store, jsonable, {
        "parsed_bbox": parsed_bbox, "check_region": check_region, "cell_days_table": cell_days_table,
        "calendar_frame": calendar_frame, "area_label": area_label, "scope_for": scope_for,
        "national_name": national_name, "check_grid": check_grid,
    })

    @app.get("/api/bridge-validation")
    def bridge_validation() -> dict[str, Any]:
        """Hold-out back-test of the 2002-2011 bridge (see data_pipeline/bridge.py)."""
        return store.json("analytics/bridge_validation.json")


__all__ = ["register", "VIEW_COLUMN"]
